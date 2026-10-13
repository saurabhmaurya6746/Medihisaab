"""Sales POS API: keyboard-first counter billing, FEFO auto-selection, Schedule H1, split tender, and held bills."""

from datetime import date, datetime, timezone
import json
import math
import sqlite3
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse, PlainTextResponse

from .dependencies import get_current_user, get_db, require_role, verify_license_allows_writes, license_write_guard
from .schemas import (
    CalculatedDraftLine,
    CreateHeldBillRequest,
    HeldBillResponse,
    PaginatedData,
    PaymentAllocationInput,
    PrintInvoiceRequest,
    PrintInvoiceResponse,
    SaleCheckoutRequest,
    SaleDraftCalculationRequest,
    SaleDraftCalculationResponse,
    SaleInvoiceResponse,
    SaleItemResponse,
    SaleLineInput,
    SalePaymentResponse,
    ScheduleH1Input,
    ScheduleH1RecordResponse,
    SubstituteMedicineResponse,
    SuccessResponse,
)
from ..printing.service import default_printer_service
from ..security.roles import UserRole, has_permission

router = APIRouter(prefix="/api/v1/sales", tags=["Sales & POS Counter Billing"])

billing_guard = Depends(require_role(UserRole.ADMIN, UserRole.PHARMACIST, UserRole.CASHIER))


def _get_fiscal_year(dt: Optional[date] = None) -> str:
    """Return Indian fiscal year string (e.g. '2026-27')."""
    d = dt or datetime.now(timezone.utc).date()
    year = d.year
    if d.month >= 4:
        next_yy = str(year + 1)[-2:]
        return f"{year}-{next_yy}"
    prev_yy = str(year)[-2:]
    return f"{year - 1}-{prev_yy}"


def _fetch_invoice_dict(invoice_id: int, db: sqlite3.Connection) -> SaleInvoiceResponse:
    """Fetch complete sale invoice, lines, schedule H1 records, and payments."""
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT si.*, u.full_name AS creator_name
        FROM sale_invoices si
        LEFT JOIN users u ON u.id = si.created_by
        WHERE si.id = ?;
        """,
        (invoice_id,),
    )
    inv = cursor.fetchone()
    if not inv:
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sale invoice #{invoice_id} not found.",
        )

    # Fetch items
    cursor.execute(
        """
        SELECT si.*, m.brand_name AS medicine_name, m.dosage_form, m.generic_salt, m.is_schedule_h1,
               mb.batch_number, mb.expiry_date, mb.pack_size
        FROM sale_items si
        JOIN medicines m ON m.id = si.medicine_id
        JOIN medicine_batches mb ON mb.id = si.batch_id
        WHERE si.sale_invoice_id = ?
        ORDER BY si.id ASC;
        """,
        (invoice_id,),
    )
    item_rows = cursor.fetchall()

    # Fetch Schedule H1 records
    cursor.execute(
        """
        SELECT * FROM schedule_h1_records
        WHERE sale_item_id IN (SELECT id FROM sale_items WHERE sale_invoice_id = ?);
        """,
        (invoice_id,),
    )
    h1_map = {r["sale_item_id"]: r for r in cursor.fetchall()}

    # Fetch payments
    cursor.execute(
        """
        SELECT * FROM sale_payments
        WHERE sale_invoice_id = ?
        ORDER BY id ASC;
        """,
        (invoice_id,),
    )
    payment_rows = cursor.fetchall()
    cursor.close()

    items = []
    for ir in item_rows:
        h1_row = h1_map.get(ir["id"])
        h1_obj = None
        if h1_row:
            h1_obj = ScheduleH1RecordResponse(
                id=h1_row["id"],
                sale_item_id=h1_row["sale_item_id"],
                sale_invoice_id=invoice_id,
                invoice_no=inv["invoice_no"],
                patient_name=h1_row["patient_name"],
                patient_address=h1_row["patient_address"],
                doctor_name=h1_row["doctor_name"],
                doctor_address=h1_row["doctor_address"],
                medicine_name=h1_row["medicine_name"],
                batch_number=h1_row["batch_number"],
                quantity_units=h1_row["quantity_units"],
                dispensed_date=h1_row["dispensed_date"],
                created_at=h1_row["created_at"],
            )

        items.append(
            SaleItemResponse(
                id=ir["id"],
                sale_invoice_id=ir["sale_invoice_id"],
                medicine_id=ir["medicine_id"],
                medicine_name=ir["medicine_name"],
                dosage_form=ir["dosage_form"],
                generic_salt=ir["generic_salt"],
                is_schedule_h1=bool(ir["is_schedule_h1"]),
                batch_id=ir["batch_id"],
                batch_number=ir["batch_number"],
                expiry_date=ir["expiry_date"],
                pack_size=ir["pack_size"],
                quantity_units=ir["quantity_units"],
                unit_mrp_paise=ir["unit_mrp_paise"],
                unit_rate_paise=ir["unit_rate_paise"],
                discount_percent=float(ir["discount_percent"]),
                taxable_amount_paise=ir["taxable_amount_paise"],
                gst_rate=float(ir["gst_rate"]),
                cgst_amount_paise=ir["cgst_amount_paise"],
                sgst_amount_paise=ir["sgst_amount_paise"],
                total_amount_paise=ir["total_amount_paise"],
                schedule_h1_record=h1_obj,
                created_at=ir["created_at"],
            )
        )

    payments = [
        SalePaymentResponse(
            id=pr["id"],
            sale_invoice_id=pr["sale_invoice_id"],
            payment_mode=pr["payment_mode"],
            amount_paise=pr["amount_paise"],
            reference_note=pr["reference_note"],
            created_at=pr["created_at"],
        )
        for pr in payment_rows
    ]

    return SaleInvoiceResponse(
        id=inv["id"],
        invoice_no=inv["invoice_no"],
        fiscal_year=inv["fiscal_year"],
        sequence_number=inv["sequence_number"],
        customer_id=inv["customer_id"],
        customer_name=inv["customer_name"],
        customer_phone=inv["customer_phone"],
        doctor_name=inv["doctor_name"],
        doctor_address=inv["doctor_address"],
        subtotal_taxable_paise=inv["subtotal_taxable_paise"],
        total_cgst_paise=inv["total_cgst_paise"],
        total_sgst_paise=inv["total_sgst_paise"],
        total_igst_paise=inv["total_igst_paise"],
        discount_paise=inv["discount_paise"],
        round_off_paise=inv["round_off_paise"],
        grand_total_paise=inv["grand_total_paise"],
        payment_mode=inv["payment_mode"],
        cash_tendered_paise=inv["cash_tendered_paise"],
        change_returned_paise=inv["change_returned_paise"],
        status=inv["status"],
        notes=inv["notes"],
        created_by=inv["created_by"],
        creator_name=inv["creator_name"],
        created_at=inv["created_at"],
        updated_at=inv["updated_at"],
        items=items,
        payments=payments,
    )


# ==========================================
# 1. MEDICINE & BARCODE SEARCH
# ==========================================

@router.get("/search-medicines", dependencies=[billing_guard])
def search_medicines_for_billing(
    query: Optional[str] = Query(None, description="Search term for name or salt"),
    barcode: Optional[str] = Query(None, description="Exact barcode from scanner"),
    limit: int = Query(25, ge=1, le=100),
    db: sqlite3.Connection = Depends(get_db),
):
    """Fast medicine catalog search for counter billing with FEFO batch recommendation."""
    cursor = db.cursor()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    conditions = ["m.is_active = 1"]
    params: List[Any] = []

    if barcode and barcode.strip():
        conditions.append("m.barcode = ?")
        params.append(barcode.strip())
    elif query and query.strip():
        term = f"%{query.strip()}%"
        conditions.append("(m.brand_name LIKE ? OR m.generic_salt LIKE ? OR m.barcode LIKE ?)")
        params.extend([term, term, term])

    where_clause = f"WHERE {' AND '.join(conditions)}"

    # Fetch medicines with aggregate stock
    sql = f"""
        SELECT m.id, m.brand_name, m.generic_salt, m.dosage_form, m.pack_size,
               m.hsn_code, m.gst_rate, m.is_schedule_h1, m.rack_location, m.barcode,
               COALESCE(SUM(CASE WHEN mb.is_active = 1 AND mb.expiry_date > '{today_str}' THEN mb.current_quantity ELSE 0 END), 0) AS total_available_stock
        FROM medicines m
        LEFT JOIN medicine_batches mb ON mb.medicine_id = m.id
        {where_clause}
        GROUP BY m.id
        ORDER BY m.brand_name ASC
        LIMIT ?;
    """
    params.append(limit)
    cursor.execute(sql, params)
    med_rows = cursor.fetchall()

    results = []
    for med in med_rows:
        # Get recommended FEFO batch
        cursor.execute(
            f"""
            SELECT id, batch_number, expiry_date, mrp_paise, current_quantity, pack_size
            FROM medicine_batches
            WHERE medicine_id = ? AND is_active = 1 AND current_quantity > 0 AND expiry_date > ?
            ORDER BY expiry_date ASC, current_quantity DESC
            LIMIT 1;
            """,
            (med["id"], today_str),
        )
        fefo_row = cursor.fetchone()

        fefo_batch = None
        if fefo_row:
            p_size = fefo_row["pack_size"] or 1
            unit_mrp = (fefo_row["mrp_paise"] + p_size // 2) // p_size
            fefo_batch = {
                "id": fefo_row["id"],
                "batch_number": fefo_row["batch_number"],
                "expiry_date": fefo_row["expiry_date"],
                "mrp_paise": fefo_row["mrp_paise"],
                "unit_mrp_paise": unit_mrp,
                "current_quantity": fefo_row["current_quantity"],
            }

        results.append(
            {
                "id": med["id"],
                "brand_name": med["brand_name"],
                "generic_salt": med["generic_salt"],
                "dosage_form": med["dosage_form"],
                "pack_size": med["pack_size"],
                "hsn_code": med["hsn_code"],
                "gst_rate": float(med["gst_rate"]),
                "is_schedule_h1": bool(med["is_schedule_h1"]),
                "rack_location": med["rack_location"],
                "barcode": med["barcode"],
                "total_available_stock": med["total_available_stock"],
                "fefo_batch": fefo_batch,
            }
        )

    cursor.close()
    return SuccessResponse(data=results)


# ==========================================
# 2. FEFO BATCH AVAILABILITY
# ==========================================

@router.get("/batches", dependencies=[billing_guard])
def list_medicine_batches_fefo(
    medicine_id: int = Query(..., description="Medicine ID"),
    include_out_of_stock: bool = Query(False, description="Include zero-quantity batches"),
    include_expired: bool = Query(False, description="Include expired batches"),
    db: sqlite3.Connection = Depends(get_db),
):
    """Retrieve all batches for a medicine sorted strictly by FEFO (earliest expiry first)."""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cursor = db.cursor()

    # Verify medicine
    cursor.execute("SELECT id, brand_name, is_active FROM medicines WHERE id = ?;", (medicine_id,))
    med = cursor.fetchone()
    if not med:
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medicine #{medicine_id} not found.",
        )

    conditions = ["medicine_id = ?", "is_active = 1"]
    params: List[Any] = [medicine_id]

    if not include_out_of_stock:
        conditions.append("current_quantity > 0")

    if not include_expired:
        conditions.append("expiry_date > ?")
        params.append(today_str)

    where_sql = f"WHERE {' AND '.join(conditions)}"

    cursor.execute(
        f"""
        SELECT * FROM medicine_batches
        {where_sql}
        ORDER BY expiry_date ASC, current_quantity DESC;
        """,
        params,
    )
    rows = cursor.fetchall()
    cursor.close()

    items = []
    for r in rows:
        is_expired = r["expiry_date"] <= today_str
        is_available = (not is_expired) and (r["current_quantity"] > 0) and bool(r["is_active"])
        p_size = r["pack_size"] or 1
        unit_mrp = (r["mrp_paise"] + p_size // 2) // p_size

        items.append(
            {
                "id": r["id"],
                "medicine_id": r["medicine_id"],
                "batch_number": r["batch_number"],
                "expiry_date": r["expiry_date"],
                "mrp_paise": r["mrp_paise"],
                "unit_mrp_paise": unit_mrp,
                "purchase_rate_paise": r["purchase_rate_paise"],
                "pack_size": r["pack_size"],
                "current_quantity": r["current_quantity"],
                "reserved_quantity": r["reserved_quantity"],
                "is_expired": is_expired,
                "is_available": is_available,
                "is_active": bool(r["is_active"]),
            }
        )

    return SuccessResponse(data=items)


# ==========================================
# 3. SUBSTITUTE MEDICINE FINDER (F3)
# ==========================================

@router.get("/substitutes", response_model=SuccessResponse[List[SubstituteMedicineResponse]], dependencies=[billing_guard])
def find_substitutes(
    medicine_id: Optional[int] = Query(None, description="Original requested medicine ID"),
    generic_salt: Optional[str] = Query(None, description="Generic composition string"),
    dosage_form: Optional[str] = Query(None, description="Dosage form"),
    db: sqlite3.Connection = Depends(get_db),
):
    """Find in-stock substitute medicines with identical generic salt composition and dosage form."""
    cursor = db.cursor()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    target_salt = generic_salt
    target_form = dosage_form
    exclude_id = medicine_id

    if medicine_id is not None:
        cursor.execute("SELECT generic_salt, dosage_form FROM medicines WHERE id = ?;", (medicine_id,))
        med = cursor.fetchone()
        if med:
            target_salt = target_salt or med["generic_salt"]
            target_form = target_form or med["dosage_form"]

    if not target_salt:
        cursor.close()
        return SuccessResponse(data=[])

    conditions = ["m.is_active = 1", "LOWER(TRIM(m.generic_salt)) = LOWER(TRIM(?))"]
    params: List[Any] = [target_salt]

    if target_form:
        conditions.append("m.dosage_form = ?")
        params.append(target_form.upper())

    if exclude_id is not None:
        conditions.append("m.id != ?")
        params.append(exclude_id)

    where_sql = f"WHERE {' AND '.join(conditions)}"

    sql = f"""
        SELECT m.id, m.brand_name, m.generic_salt, m.dosage_form, m.pack_size,
               m.rack_location, m.is_schedule_h1, m.gst_rate,
               COALESCE(SUM(CASE WHEN mb.is_active = 1 AND mb.expiry_date > '{today_str}' THEN mb.current_quantity ELSE 0 END), 0) AS total_stock_units,
               COUNT(DISTINCT CASE WHEN mb.is_active = 1 AND mb.expiry_date > '{today_str}' AND mb.current_quantity > 0 THEN mb.id END) AS available_batches_count
        FROM medicines m
        LEFT JOIN medicine_batches mb ON mb.medicine_id = m.id
        {where_sql}
        GROUP BY m.id
        HAVING total_stock_units > 0
        ORDER BY total_stock_units DESC, m.brand_name ASC;
    """
    cursor.execute(sql, params)
    rows = cursor.fetchall()

    results = []
    for r in rows:
        # Find FEFO recommended batch
        cursor.execute(
            f"""
            SELECT id, batch_number, expiry_date, mrp_paise
            FROM medicine_batches
            WHERE medicine_id = ? AND is_active = 1 AND current_quantity > 0 AND expiry_date > ?
            ORDER BY expiry_date ASC, current_quantity DESC
            LIMIT 1;
            """,
            (r["id"], today_str),
        )
        b = cursor.fetchone()

        results.append(
            SubstituteMedicineResponse(
                id=r["id"],
                brand_name=r["brand_name"],
                generic_salt=r["generic_salt"],
                dosage_form=r["dosage_form"],
                pack_size=r["pack_size"],
                rack_location=r["rack_location"],
                is_schedule_h1=bool(r["is_schedule_h1"]),
                gst_rate=float(r["gst_rate"]),
                total_stock_units=r["total_stock_units"],
                recommended_batch_id=b["id"] if b else None,
                recommended_batch_number=b["batch_number"] if b else None,
                recommended_expiry_date=b["expiry_date"] if b else None,
                recommended_mrp_paise=b["mrp_paise"] if b else None,
                available_batches_count=r["available_batches_count"],
            )
        )

    cursor.close()
    return SuccessResponse(data=results)


# ==========================================
# 4. SALE DRAFT CALCULATION
# ==========================================

def _calculate_sale_draft(
    lines: List[SaleLineInput],
    discount_paise: int,
    round_off_paise: int,
    db: sqlite3.Connection,
) -> SaleDraftCalculationResponse:
    """Perform pure in-memory mathematical calculation of lines, FEFO selection, discounts, and GST back-calculation."""
    cursor = db.cursor()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    calc_lines: List[CalculatedDraftLine] = []
    subtotal_taxable_paise = 0
    total_cgst_paise = 0
    total_sgst_paise = 0
    total_lines_amount_paise = 0
    requires_schedule_h1 = False
    missing_schedule_h1_count = 0

    for idx, line in enumerate(lines, 1):
        # 1. Fetch medicine
        cursor.execute(
            "SELECT id, brand_name, dosage_form, generic_salt, pack_size, gst_rate, is_schedule_h1, is_active FROM medicines WHERE id = ?;",
            (line.medicine_id,),
        )
        med = cursor.fetchone()
        if not med:
            cursor.close()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Medicine #{line.medicine_id} not found.",
            )
        if not med["is_active"]:
            cursor.close()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Medicine '{med['brand_name']}' is deactivated and cannot be sold.",
            )

        med_is_h1 = bool(med["is_schedule_h1"])
        if med_is_h1:
            requires_schedule_h1 = True
            if not line.schedule_h1 or not line.schedule_h1.patient_name.strip() or not line.schedule_h1.doctor_name.strip():
                missing_schedule_h1_count += 1

        # 2. Identify batch (manual or FEFO)
        if line.batch_id:
            cursor.execute("SELECT * FROM medicine_batches WHERE id = ?;", (line.batch_id,))
            batch = cursor.fetchone()
            if not batch:
                cursor.close()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Batch #{line.batch_id} not found.",
                )
            if batch["medicine_id"] != med["id"]:
                cursor.close()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Batch #{line.batch_id} does not belong to medicine '{med['brand_name']}'.",
                )
        else:
            # Auto FEFO pick
            cursor.execute(
                f"""
                SELECT * FROM medicine_batches
                WHERE medicine_id = ? AND is_active = 1 AND current_quantity > 0 AND expiry_date > ?
                ORDER BY expiry_date ASC, current_quantity DESC
                LIMIT 1;
                """,
                (med["id"], today_str),
            )
            batch = cursor.fetchone()
            if not batch:
                cursor.close()
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"No active, non-expired stock available for medicine '{med['brand_name']}'.",
                )

        # Batch validations
        if not batch["is_active"]:
            cursor.close()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Batch '{batch['batch_number']}' for medicine '{med['brand_name']}' is inactive.",
            )
        if batch["expiry_date"] <= today_str:
            cursor.close()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Cannot dispense expired batch '{batch['batch_number']}' (Expired on {batch['expiry_date']}).",
            )
        if batch["current_quantity"] < line.quantity_units:
            cursor.close()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Insufficient stock for batch '{batch['batch_number']}'. Available: {batch['current_quantity']}, Requested: {line.quantity_units}.",
            )

        pack_size = batch["pack_size"] or med["pack_size"] or 1
        unit_mrp = (batch["mrp_paise"] + pack_size // 2) // pack_size
        unit_rate = line.unit_rate_paise if line.unit_rate_paise is not None else unit_mrp

        gross_paise = line.quantity_units * unit_rate
        disc_pct = line.discount_percent
        line_discount_paise = (gross_paise * int(round(disc_pct * 100)) + 5000) // 10000
        line_total_paise = gross_paise - line_discount_paise

        # Back-calculate GST from retail MRP inclusive total
        gst_r = float(med["gst_rate"])
        if gst_r <= 0.0:
            taxable_paise = line_total_paise
            cgst_paise = 0
            sgst_paise = 0
        else:
            gst_basis_points = int(round(gst_r * 100))
            taxable_paise = (line_total_paise * 10000 * 2 + (10000 + gst_basis_points)) // (
                (10000 + gst_basis_points) * 2
            )
            tax_paise = line_total_paise - taxable_paise
            cgst_paise = tax_paise // 2
            sgst_paise = tax_paise - cgst_paise

        subtotal_taxable_paise += taxable_paise
        total_cgst_paise += cgst_paise
        total_sgst_paise += sgst_paise
        total_lines_amount_paise += line_total_paise

        # Near expiry check: within 90 days
        exp_date_obj = datetime.strptime(batch["expiry_date"], "%Y-%m-%d").date()
        today_date_obj = datetime.now(timezone.utc).date()
        is_near = (exp_date_obj - today_date_obj).days <= 90

        calc_lines.append(
            CalculatedDraftLine(
                medicine_id=med["id"],
                medicine_name=med["brand_name"],
                dosage_form=med["dosage_form"],
                generic_salt=med["generic_salt"],
                is_schedule_h1=med_is_h1,
                batch_id=batch["id"],
                batch_number=batch["batch_number"],
                expiry_date=batch["expiry_date"],
                pack_size=pack_size,
                available_stock_units=batch["current_quantity"],
                quantity_units=line.quantity_units,
                unit_mrp_paise=unit_mrp,
                unit_rate_paise=unit_rate,
                discount_percent=disc_pct,
                discount_amount_paise=line_discount_paise,
                taxable_amount_paise=taxable_paise,
                gst_rate=gst_r,
                cgst_amount_paise=cgst_paise,
                sgst_amount_paise=sgst_paise,
                total_amount_paise=line_total_paise,
                is_near_expiry=is_near,
                schedule_h1=line.schedule_h1,
            )
        )

    cursor.close()

    inv_discount = min(discount_paise, total_lines_amount_paise)
    grand_total = total_lines_amount_paise - inv_discount + round_off_paise
    grand_total = max(0, grand_total)

    return SaleDraftCalculationResponse(
        lines=calc_lines,
        subtotal_taxable_paise=subtotal_taxable_paise,
        total_cgst_paise=total_cgst_paise,
        total_sgst_paise=total_sgst_paise,
        total_tax_paise=total_cgst_paise + total_sgst_paise,
        discount_paise=inv_discount,
        round_off_paise=round_off_paise,
        grand_total_paise=grand_total,
        requires_schedule_h1=requires_schedule_h1,
        missing_schedule_h1_count=missing_schedule_h1_count,
    )


@router.post("/draft-calculate", response_model=SuccessResponse[SaleDraftCalculationResponse], dependencies=[billing_guard])
def calculate_sale_draft(
    payload: SaleDraftCalculationRequest,
    db: sqlite3.Connection = Depends(get_db),
):
    """Calculate commercial math, pro-rata tablet prices, taxes, and FEFO picks without mutating DB."""
    if not payload.lines:
        return SuccessResponse(
            data=SaleDraftCalculationResponse(
                lines=[],
                subtotal_taxable_paise=0,
                total_cgst_paise=0,
                total_sgst_paise=0,
                total_tax_paise=0,
                discount_paise=0,
                round_off_paise=0,
                grand_total_paise=0,
                requires_schedule_h1=False,
                missing_schedule_h1_count=0,
            )
        )

    draft = _calculate_sale_draft(
        payload.lines,
        payload.discount_paise or 0,
        payload.round_off_paise or 0,
        db,
    )
    return SuccessResponse(data=draft)


# ==========================================
# 5. ATOMIC SALE CHECKOUT & COMMIT
# ==========================================

@router.post("/checkout", response_model=SuccessResponse[SaleInvoiceResponse], status_code=status.HTTP_201_CREATED, dependencies=[billing_guard])
def checkout_sale(
    payload: SaleCheckoutRequest,
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Atomically commit a counter sale invoice, deduct FEFO batch stock, record H1, and log payments."""
    if not payload.lines:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Sale bill must contain at least one line item.",
        )

    # License Status Enforcement: After grace expires, restrict new commercial sales while preserving read-only historical access
    verify_license_allows_writes(request)

    # Check if cash day-book session for today is already CLOSED
    today_date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cursor_check = db.cursor()
    cursor_check.execute("SELECT status FROM cash_sessions WHERE session_date = ?;", (today_date_str,))
    session_row = cursor_check.fetchone()
    if session_row and session_row["status"] == "CLOSED":
        cursor_check.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cash day-book for today ({today_date_str}) has been closed. No further sales can be processed.",
        )
    cursor_check.close()

    # 1. First run the draft calculation to validate medicines, batches, stock, and math
    draft = _calculate_sale_draft(
        payload.lines,
        payload.discount_paise or 0,
        payload.round_off_paise or 0,
        db,
    )

    # 2. Schedule H1 RBAC and mandatory field verification
    if draft.requires_schedule_h1:
        # Check RBAC authority
        if not has_permission(current_user["role"], "DISPENSE_SCHEDULE_H1"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Dispensing Schedule H1 medicines requires Pharmacist or Admin authorization. Operator '{current_user['username']}' lacks this permission.",
            )

        # Check that all H1 items have mandatory patient and doctor details
        for idx, line in enumerate(draft.lines, 1):
            if line.is_schedule_h1:
                h1 = line.schedule_h1
                if not h1 or not h1.patient_name.strip() or not h1.patient_address.strip() or not h1.doctor_name.strip():
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Line #{idx} ('{line.medicine_name}') contains a Schedule H1 medicine. Patient Name, Patient Address, and Doctor Name are mandatory statutory requirements.",
                    )

    # 3. Payment allocations and credit limit validation
    payment_mode = payload.payment_mode
    grand_total_paise = draft.grand_total_paise
    cash_tendered_paise = payload.cash_tendered_paise or (grand_total_paise if payment_mode == "CASH" else 0)
    change_returned_paise = 0

    allocations: List[Dict[str, Any]] = []

    if payment_mode == "SPLIT":
        if not payload.payments:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Payment allocations must be provided for SPLIT payment mode.",
            )
        sum_allocated = sum(p.amount_paise for p in payload.payments)
        if sum_allocated != grand_total_paise:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Split payment total ({sum_allocated} paise) does not match invoice grand total ({grand_total_paise} paise).",
            )
        cash_alloc = sum(p.amount_paise for p in payload.payments if p.payment_mode == "CASH")
        if cash_alloc > 0:
            if cash_tendered_paise < cash_alloc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Cash tendered ({cash_tendered_paise} paise) is less than cash split allocation ({cash_alloc} paise).",
                )
            change_returned_paise = cash_tendered_paise - cash_alloc

        for p in payload.payments:
            allocations.append({
                "payment_mode": p.payment_mode,
                "amount_paise": p.amount_paise,
                "reference_note": p.reference_note,
            })
    elif payment_mode == "CASH":
        if cash_tendered_paise < grand_total_paise:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Cash tendered ({cash_tendered_paise} paise) is less than invoice grand total ({grand_total_paise} paise).",
            )
        change_returned_paise = cash_tendered_paise - grand_total_paise
        allocations.append({
            "payment_mode": "CASH",
            "amount_paise": grand_total_paise,
            "reference_note": "Cash Tender",
        })
    elif payment_mode in ("UPI", "CARD"):
        cash_tendered_paise = grand_total_paise
        change_returned_paise = 0
        allocations.append({
            "payment_mode": payment_mode,
            "amount_paise": grand_total_paise,
            "reference_note": f"{payment_mode} Payment",
        })
    elif payment_mode == "KHATA":
        if not payload.customer_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Customer profile is mandatory for Khata (credit) billing.",
            )
        allocations.append({
            "payment_mode": "KHATA",
            "amount_paise": grand_total_paise,
            "reference_note": "Khata Credit",
        })

    # Validate customer khata limit if any KHATA allocation is present
    khata_total_paise = sum(a["amount_paise"] for a in allocations if a["payment_mode"] == "KHATA")
    customer_row = None
    if khata_total_paise > 0:
        if not payload.customer_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Customer profile is mandatory when a Khata payment allocation is present.",
            )
        cursor = db.cursor()
        cursor.execute("SELECT * FROM customers WHERE id = ?;", (payload.customer_id,))
        customer_row = cursor.fetchone()
        cursor.close()
        if not customer_row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Customer #{payload.customer_id} does not exist.",
            )
        if not customer_row["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Customer '{customer_row['name']}' is inactive.",
            )

        new_bal = customer_row["current_balance_paise"] + khata_total_paise
        if new_bal > customer_row["credit_limit_paise"]:
            limit_rs = customer_row["credit_limit_paise"] / 100
            curr_rs = customer_row["current_balance_paise"] / 100
            req_rs = khata_total_paise / 100
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Customer credit limit exceeded! Limit: Rs. {limit_rs:.2f}, Current Balance: Rs. {curr_rs:.2f}, Added Khata: Rs. {req_rs:.2f}.",
            )

    # 4. Atomic Database Transaction
    now = datetime.now(timezone.utc)
    now_str = now.isoformat()
    dispensed_date_str = now.strftime("%Y-%m-%d")
    fiscal_yr = _get_fiscal_year(now.date())

    cursor = db.cursor()
    cursor.execute("BEGIN IMMEDIATE;")
    try:
        # Re-check and lock batches to prevent negative stock
        for line in draft.lines:
            cursor.execute(
                "SELECT current_quantity, is_active, expiry_date FROM medicine_batches WHERE id = ?;",
                (line.batch_id,),
            )
            locked_batch = cursor.fetchone()
            if not locked_batch:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Batch #{line.batch_id} not found during commit.",
                )
            if not locked_batch["is_active"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Batch '{line.batch_number}' is inactive.",
                )
            if locked_batch["expiry_date"] <= dispensed_date_str:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Batch '{line.batch_number}' expired on {locked_batch['expiry_date']}.",
                )
            if locked_batch["current_quantity"] < line.quantity_units:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Stock deficit for batch '{line.batch_number}'. Requested: {line.quantity_units}, Available: {locked_batch['current_quantity']}.",
                )

        # Generate sequence and invoice number
        cursor.execute(
            "SELECT COALESCE(MAX(sequence_number), 0) + 1 FROM sale_invoices WHERE fiscal_year = ?;",
            (fiscal_yr,),
        )
        seq_num = cursor.fetchone()[0]
        invoice_no = f"INV/{fiscal_yr}/{str(seq_num).zfill(5)}"

        # Resolve customer display info
        cust_id = payload.customer_id
        cust_name = payload.customer_name
        cust_phone = payload.customer_phone
        cust_gstin = None
        if cust_id:
            if customer_row:
                cust_name = cust_name or customer_row["name"]
                cust_phone = cust_phone or customer_row["phone"]
                try:
                    cust_gstin = customer_row["gstin"]
                except (IndexError, KeyError):
                    cust_gstin = None
            else:
                cursor.execute("SELECT name, phone, gstin FROM customers WHERE id = ?;", (cust_id,))
                c_info = cursor.fetchone()
                if c_info:
                    cust_name = cust_name or c_info["name"]
                    cust_phone = cust_phone or c_info["phone"]
                    try:
                        cust_gstin = c_info["gstin"]
                    except (IndexError, KeyError):
                        cust_gstin = None

        # Insert sale_invoices
        cursor.execute(
            """
            INSERT INTO sale_invoices (
                invoice_no, fiscal_year, sequence_number, customer_id, customer_name, customer_phone,
                customer_gstin, doctor_name, doctor_address, subtotal_taxable_paise, total_cgst_paise, total_sgst_paise,
                total_igst_paise, discount_paise, round_off_paise, grand_total_paise, payment_mode,
                cash_tendered_paise, change_returned_paise, status, notes, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'COMPLETED', ?, ?, ?, ?);
            """,
            (
                invoice_no,
                fiscal_yr,
                seq_num,
                cust_id,
                cust_name,
                cust_phone,
                cust_gstin,
                payload.doctor_name,
                payload.doctor_address,
                draft.subtotal_taxable_paise,
                draft.total_cgst_paise,
                draft.total_sgst_paise,
                0,  # intra-state counter sales default to IGST 0
                draft.discount_paise,
                draft.round_off_paise,
                grand_total_paise,
                payment_mode,
                cash_tendered_paise,
                change_returned_paise,
                payload.notes,
                current_user["id"],
                now_str,
                now_str,
            ),
        )
        sale_invoice_id = cursor.lastrowid

        # Insert sale_items, deduct batch inventory, record inventory ledger, and record Schedule H1
        for line in draft.lines:
            cursor.execute(
                """
                INSERT INTO sale_items (
                    sale_invoice_id, medicine_id, batch_id, quantity_units, unit_mrp_paise,
                    unit_rate_paise, discount_percent, taxable_amount_paise, gst_rate,
                    cgst_amount_paise, sgst_amount_paise, total_amount_paise, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    sale_invoice_id,
                    line.medicine_id,
                    line.batch_id,
                    line.quantity_units,
                    line.unit_mrp_paise,
                    line.unit_rate_paise,
                    line.discount_percent,
                    line.taxable_amount_paise,
                    line.gst_rate,
                    line.cgst_amount_paise,
                    line.sgst_amount_paise,
                    line.total_amount_paise,
                    now_str,
                ),
            )
            sale_item_id = cursor.lastrowid

            # Schedule H1 register
            if line.is_schedule_h1 and line.schedule_h1:
                cursor.execute(
                    """
                    INSERT INTO schedule_h1_records (
                        sale_item_id, patient_name, patient_address, doctor_name, doctor_address,
                        medicine_name, batch_number, quantity_units, dispensed_date, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        sale_item_id,
                        line.schedule_h1.patient_name.strip(),
                        line.schedule_h1.patient_address.strip(),
                        line.schedule_h1.doctor_name.strip(),
                        line.schedule_h1.doctor_address.strip() if line.schedule_h1.doctor_address else None,
                        line.medicine_name,
                        line.batch_number,
                        line.quantity_units,
                        dispensed_date_str,
                        now_str,
                    ),
                )

            # Deduct stock units from batch
            cursor.execute(
                """
                UPDATE medicine_batches
                SET current_quantity = current_quantity - ?, updated_at = ?
                WHERE id = ?;
                """,
                (line.quantity_units, now_str, line.batch_id),
            )

            # Fetch updated balance for ledger
            cursor.execute("SELECT current_quantity FROM medicine_batches WHERE id = ?;", (line.batch_id,))
            new_qty = cursor.fetchone()[0]

            # Record in inventory_ledger
            cursor.execute(
                """
                INSERT INTO inventory_ledger (
                    medicine_id, batch_id, transaction_type, quantity_change, quantity_balance,
                    reference_type, reference_id, notes, user_id, created_at
                ) VALUES (?, ?, 'SALE_DISPENSE', ?, ?, 'SALE_INVOICE', ?, ?, ?, ?);
                """,
                (
                    line.medicine_id,
                    line.batch_id,
                    -line.quantity_units,
                    new_qty,
                    sale_invoice_id,
                    f"POS Invoice {invoice_no}",
                    current_user["id"],
                    now_str,
                ),
            )

        # Insert payment allocations
        for alloc in allocations:
            cursor.execute(
                """
                INSERT INTO sale_payments (sale_invoice_id, payment_mode, amount_paise, reference_note, created_at)
                VALUES (?, ?, ?, ?, ?);
                """,
                (sale_invoice_id, alloc["payment_mode"], alloc["amount_paise"], alloc["reference_note"], now_str),
            )

        # If Khata used, update customer current balance and append to khata_ledger
        if khata_total_paise > 0 and cust_id:
            cursor.execute(
                """
                UPDATE customers
                SET current_balance_paise = current_balance_paise + ?
                WHERE id = ?;
                """,
                (khata_total_paise, cust_id),
            )
            # Record in khata_ledger
            cursor.execute(
                """
                INSERT INTO khata_ledger (
                    customer_id, transaction_type, entry_type, amount_paise, balance_paise,
                    reference_type, reference_id, notes, user_id, created_at
                ) VALUES (?, 'SALE_CREDIT', 'DEBIT', ?, ?, 'SALE_INVOICE', ?, ?, ?, ?);
                """,
                (
                    cust_id,
                    khata_total_paise,
                    new_bal,
                    sale_invoice_id,
                    f"Credit Sale Invoice {invoice_no}",
                    current_user["id"],
                    now_str,
                ),
            )

        # If held bill was converted to sale, delete the held bill
        if payload.held_bill_id:
            cursor.execute("DELETE FROM held_bills WHERE id = ?;", (payload.held_bill_id,))

        cursor.execute("COMMIT;")
    except HTTPException:
        db.execute("ROLLBACK;")
        raise
    except Exception as e:
        db.execute("ROLLBACK;")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Atomic sale commit failed: {e}",
        ) from e
    finally:
        cursor.close()

    # Retrieve committed invoice object
    invoice_resp = _fetch_invoice_dict(sale_invoice_id, db)

    # 5. Decoupled Print Dispatch (Safe: printer failures do not roll back completed sale)
    try:
        default_printer_service.print_invoice(invoice_resp.model_dump())
    except Exception as print_err:
        # Intentionally logged and ignored; sale remains safely committed
        pass

    return SuccessResponse(
        data=invoice_resp,
        message=f"Sale committed successfully as {invoice_no}",
    )


# ==========================================
# 6. INVOICE LISTING & RETRIEVAL
# ==========================================

@router.get("/invoices", response_model=SuccessResponse[PaginatedData[SaleInvoiceResponse]], dependencies=[billing_guard])
def list_sale_invoices(
    query: Optional[str] = Query(None, description="Search by invoice number or customer name/phone"),
    from_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: sqlite3.Connection = Depends(get_db),
):
    """List historical sales invoices with pagination and search."""
    conditions = []
    params: List[Any] = []

    if query and query.strip():
        term = f"%{query.strip()}%"
        conditions.append("(si.invoice_no LIKE ? OR si.customer_name LIKE ? OR si.customer_phone LIKE ?)")
        params.extend([term, term, term])

    if from_date:
        conditions.append("si.created_at >= ?")
        params.append(f"{from_date}T00:00:00")

    if to_date:
        conditions.append("si.created_at <= ?")
        params.append(f"{to_date}T23:59:59")

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    cursor = db.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM sale_invoices si {where_sql};", params)
    total = cursor.fetchone()[0]

    offset = (page - 1) * page_size
    cursor.execute(
        f"""
        SELECT si.id FROM sale_invoices si
        {where_sql}
        ORDER BY si.id DESC
        LIMIT ? OFFSET ?;
        """,
        params + [page_size, offset],
    )
    id_rows = cursor.fetchall()
    cursor.close()

    items = [_fetch_invoice_dict(r["id"], db) for r in id_rows]
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return SuccessResponse(
        data=PaginatedData(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)
    )


@router.get("/invoices/{id}", response_model=SuccessResponse[SaleInvoiceResponse], dependencies=[billing_guard])
def get_sale_invoice(
    id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    """Retrieve full sale invoice details by ID."""
    return SuccessResponse(data=_fetch_invoice_dict(id, db))


# ==========================================
# 7. PRINTING & REPRINT ENDPOINTS
# ==========================================

@router.post("/invoices/{id}/print", response_model=SuccessResponse[PrintInvoiceResponse], dependencies=[billing_guard])
def print_invoice_endpoint(
    id: int,
    payload: PrintInvoiceRequest,
    db: sqlite3.Connection = Depends(get_db),
):
    """Reprint an existing sale invoice (ESC/POS thermal or laser)."""
    inv = _fetch_invoice_dict(id, db)
    result = default_printer_service.print_invoice(
        inv.model_dump(),
        printer_type=payload.printer_type,
        printer_name=payload.printer_name,
    )
    return SuccessResponse(
        data=PrintInvoiceResponse(
            printed=result.success,
            printer_type=result.printer_type,
            message=result.message,
        )
    )


@router.get("/invoices/{id}/receipt", response_class=PlainTextResponse, dependencies=[billing_guard])
def get_receipt_text_preview(
    id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    """Preview ESC/POS receipt in readable text format."""
    inv = _fetch_invoice_dict(id, db)
    raw_bytes = default_printer_service.generate_receipt_bytes(inv.model_dump())
    # Decode printable characters for preview
    text = raw_bytes.decode("ascii", errors="replace")
    return PlainTextResponse(text)


@router.get("/invoices/{id}/html", response_class=HTMLResponse, dependencies=[billing_guard])
def get_laser_invoice_html_view(
    id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    """Render full A4 tax invoice HTML ready for browser window.print()."""
    inv = _fetch_invoice_dict(id, db)
    html_content = default_printer_service.generate_invoice_html(inv.model_dump())
    return HTMLResponse(content=html_content)


# ==========================================
# 8. HELD BILLS (PARK & RECALL)
# ==========================================

@router.post("/held-bills", response_model=SuccessResponse[HeldBillResponse], status_code=status.HTTP_201_CREATED, dependencies=[billing_guard, license_write_guard])
def hold_bill(
    payload: CreateHeldBillRequest,
    db: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Park an active billing cart into held queue (Ctrl+H)."""
    now = datetime.now(timezone.utc)
    now_str = now.isoformat()
    hold_ref = payload.hold_reference or f"HOLD-{now.strftime('%H%M%S')}"

    # Calculate subtotal and tax for quick summary display
    subtotal_paise = sum(it.get("unit_rate_paise", 0) * it.get("quantity_units", 1) for it in payload.items)
    grand_total_paise = sum(it.get("total_amount_paise", 0) for it in payload.items) or subtotal_paise

    cursor = db.cursor()
    cursor.execute(
        """
        INSERT INTO held_bills (
            hold_reference, customer_id, customer_name, customer_phone, doctor_name, doctor_address,
            items_json, subtotal_paise, total_tax_paise, grand_total_paise, notes, created_by, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            hold_ref,
            payload.customer_id,
            payload.customer_name,
            payload.customer_phone,
            payload.doctor_name,
            payload.doctor_address,
            json.dumps(payload.items),
            subtotal_paise,
            max(0, grand_total_paise - subtotal_paise),
            grand_total_paise,
            payload.notes,
            current_user["id"],
            now_str,
            now_str,
        ),
    )
    held_id = cursor.lastrowid
    db.commit()
    cursor.close()

    return SuccessResponse(
        data=HeldBillResponse(
            id=held_id,
            hold_reference=hold_ref,
            customer_id=payload.customer_id,
            customer_name=payload.customer_name,
            customer_phone=payload.customer_phone,
            doctor_name=payload.doctor_name,
            doctor_address=payload.doctor_address,
            items=payload.items,
            subtotal_paise=subtotal_paise,
            total_tax_paise=max(0, grand_total_paise - subtotal_paise),
            grand_total_paise=grand_total_paise,
            notes=payload.notes,
            created_by=current_user["id"],
            creator_name=current_user["full_name"],
            created_at=now_str,
            updated_at=now_str,
        ),
        message=f"Bill held with reference {hold_ref}",
    )


@router.get("/held-bills", response_model=SuccessResponse[List[HeldBillResponse]], dependencies=[billing_guard])
def list_held_bills(
    db: sqlite3.Connection = Depends(get_db),
):
    """List all currently parked held bills for recall (Ctrl+R)."""
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT hb.*, u.full_name AS creator_name
        FROM held_bills hb
        LEFT JOIN users u ON u.id = hb.created_by
        ORDER BY hb.id DESC;
        """
    )
    rows = cursor.fetchall()
    cursor.close()

    items = []
    for r in rows:
        items_data = json.loads(r["items_json"]) if r["items_json"] else []
        items.append(
            HeldBillResponse(
                id=r["id"],
                hold_reference=r["hold_reference"],
                customer_id=r["customer_id"],
                customer_name=r["customer_name"],
                customer_phone=r["customer_phone"],
                doctor_name=r["doctor_name"],
                doctor_address=r["doctor_address"],
                items=items_data,
                subtotal_paise=r["subtotal_paise"],
                total_tax_paise=r["total_tax_paise"],
                grand_total_paise=r["grand_total_paise"],
                notes=r["notes"],
                created_by=r["created_by"],
                creator_name=r["creator_name"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
        )

    return SuccessResponse(data=items)


@router.get("/held-bills/{id}", response_model=SuccessResponse[HeldBillResponse], dependencies=[billing_guard])
def get_held_bill(
    id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    """Retrieve specific held bill for active cart restoration."""
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT hb.*, u.full_name AS creator_name
        FROM held_bills hb
        LEFT JOIN users u ON u.id = hb.created_by
        WHERE hb.id = ?;
        """,
        (id,),
    )
    r = cursor.fetchone()
    cursor.close()
    if not r:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Held bill #{id} not found.",
        )

    return SuccessResponse(
        data=HeldBillResponse(
            id=r["id"],
            hold_reference=r["hold_reference"],
            customer_id=r["customer_id"],
            customer_name=r["customer_name"],
            customer_phone=r["customer_phone"],
            doctor_name=r["doctor_name"],
            doctor_address=r["doctor_address"],
            items=json.loads(r["items_json"]),
            subtotal_paise=r["subtotal_paise"],
            total_tax_paise=r["total_tax_paise"],
            grand_total_paise=r["grand_total_paise"],
            notes=r["notes"],
            created_by=r["created_by"],
            creator_name=r["creator_name"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
    )


@router.delete("/held-bills/{id}", response_model=SuccessResponse[bool], dependencies=[billing_guard, license_write_guard])
def delete_held_bill(
    id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    """Discard or remove a held bill."""
    cursor = db.cursor()
    cursor.execute("DELETE FROM held_bills WHERE id = ?;", (id,))
    deleted = cursor.rowcount > 0
    db.commit()
    cursor.close()
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Held bill #{id} not found.",
        )
    return SuccessResponse(data=True, message="Held bill deleted successfully.")
