"""Purchases API: draft management, validation, atomic posting, and supplier payables."""

from datetime import datetime, timezone
import math
import sqlite3
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from .dependencies import get_current_user, get_db, require_role, require_write_role
from .schemas import (
    CreatePurchaseInvoiceRequest,
    PaginatedData,
    PurchaseInvoiceLineInput,
    PurchaseInvoiceLineResponse,
    PurchaseInvoiceResponse,
    SuccessResponse,
    SupplierPayableEntryResponse,
    SupplierPayableHistoryResponse,
    UpdatePurchaseInvoiceRequest,
)
from ..security.roles import UserRole

router = APIRouter(tags=["Purchases & Supplier Payables"])

read_guard = Depends(require_role(UserRole.ADMIN, UserRole.PHARMACIST, UserRole.CASHIER))
write_guard = Depends(require_write_role(UserRole.ADMIN, UserRole.PHARMACIST))


def _calculate_line(line: PurchaseInvoiceLineInput) -> dict:
    """Calculate line totals with free schemes and GST using integer paise arithmetic."""
    total_received = line.paid_quantity + line.free_quantity
    if total_received <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Line for medicine #{line.medicine_id} must have paid_quantity + free_quantity > 0.",
        )

    # Free quantity is not charged in gross amount
    gross_paise = line.paid_quantity * line.purchase_rate_paise
    if line.discount_paise > gross_paise:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Line discount ({line.discount_paise} paise) cannot exceed gross line amount ({gross_paise} paise).",
        )
    discount_paise = line.discount_paise
    taxable_paise = gross_paise - discount_paise
    gst_basis_points = int(round(line.gst_percentage * 100))
    tax_amount_paise = (taxable_paise * gst_basis_points + 5000) // 10000
    line_total_paise = taxable_paise + tax_amount_paise

    return {
        "medicine_id": line.medicine_id,
        "batch_number": line.batch_number.strip().upper(),
        "expiry_date": line.expiry_date,
        "pack_size": line.pack_size,
        "paid_quantity": line.paid_quantity,
        "free_quantity": line.free_quantity,
        "total_received_quantity": total_received,
        "purchase_rate_paise": line.purchase_rate_paise,
        "mrp_paise": line.mrp_paise,
        "discount_paise": discount_paise,
        "gst_percentage": line.gst_percentage,
        "tax_amount_paise": tax_amount_paise,
        "line_total_paise": line_total_paise,
    }


def _fetch_invoice_with_lines(invoice_id: int, db: sqlite3.Connection) -> PurchaseInvoiceResponse:
    """Fetch complete purchase invoice and its lines."""
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT pi.*, s.name AS supplier_name, u.full_name AS creator_name
        FROM purchase_invoices pi
        JOIN suppliers s ON s.id = pi.supplier_id
        LEFT JOIN users u ON u.id = pi.created_by
        WHERE pi.id = ?;
        """,
        (invoice_id,),
    )
    inv_row = cursor.fetchone()
    if not inv_row:
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase invoice #{invoice_id} not found.",
        )

    cursor.execute(
        """
        SELECT pil.*, m.brand_name AS medicine_name, m.dosage_form
        FROM purchase_invoice_lines pil
        JOIN medicines m ON m.id = pil.medicine_id
        WHERE pil.purchase_invoice_id = ?
        ORDER BY pil.id ASC;
        """,
        (invoice_id,),
    )
    line_rows = cursor.fetchall()
    cursor.close()

    lines = [
        PurchaseInvoiceLineResponse(
            id=lr["id"],
            purchase_invoice_id=lr["purchase_invoice_id"],
            medicine_id=lr["medicine_id"],
            medicine_name=lr["medicine_name"],
            dosage_form=lr["dosage_form"],
            batch_number=lr["batch_number"],
            expiry_date=lr["expiry_date"],
            pack_size=lr["pack_size"],
            paid_quantity=lr["paid_quantity"],
            free_quantity=lr["free_quantity"],
            total_received_quantity=lr["total_received_quantity"],
            purchase_rate_paise=lr["purchase_rate_paise"],
            mrp_paise=lr["mrp_paise"],
            discount_paise=lr["discount_paise"],
            gst_percentage=float(lr["gst_percentage"]),
            tax_amount_paise=lr["tax_amount_paise"],
            line_total_paise=lr["line_total_paise"],
            created_at=lr["created_at"],
        )
        for lr in line_rows
    ]

    return PurchaseInvoiceResponse(
        id=inv_row["id"],
        supplier_id=inv_row["supplier_id"],
        supplier_name=inv_row["supplier_name"],
        supplier_invoice_number=inv_row["supplier_invoice_number"],
        invoice_date=inv_row["invoice_date"],
        entry_date=inv_row["entry_date"],
        status=inv_row["status"],
        subtotal_paise=inv_row["subtotal_paise"],
        discount_paise=inv_row["discount_paise"],
        tax_amount_paise=inv_row["tax_amount_paise"],
        grand_total_paise=inv_row["grand_total_paise"],
        payment_status=inv_row["payment_status"],
        notes=inv_row["notes"],
        created_by=inv_row["created_by"],
        creator_name=inv_row["creator_name"],
        created_at=inv_row["created_at"],
        posted_at=inv_row["posted_at"],
        updated_at=inv_row["updated_at"],
        lines=lines,
    )


# ==========================================
# 1. CREATE DRAFT PURCHASE INVOICE
# ==========================================

@router.post("/api/v1/purchases", response_model=SuccessResponse[PurchaseInvoiceResponse], status_code=status.HTTP_201_CREATED, dependencies=[write_guard])
def create_purchase_invoice(
    payload: CreatePurchaseInvoiceRequest,
    db: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new draft purchase invoice."""
    cursor = db.cursor()

    # 1. Validate supplier
    cursor.execute("SELECT id, is_active FROM suppliers WHERE id = ?;", (payload.supplier_id,))
    sup = cursor.fetchone()
    if not sup:
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Supplier #{payload.supplier_id} does not exist.",
        )
    if not sup["is_active"]:
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Supplier #{payload.supplier_id} is inactive.",
        )

    # 2. Check duplicate invoice number for supplier
    clean_inv_num = payload.supplier_invoice_number.strip().upper()
    cursor.execute(
        "SELECT id FROM purchase_invoices WHERE supplier_id = ? AND UPPER(supplier_invoice_number) = ? AND status != 'CANCELLED';",
        (payload.supplier_id, clean_inv_num),
    )
    if cursor.fetchone():
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invoice number '{clean_inv_num}' already exists for this supplier.",
        )

    # 3. Validate medicines and calculate lines
    calc_lines = []
    subtotal_paise = 0
    total_tax_paise = 0

    for l in payload.lines:
        cursor.execute("SELECT id, is_active, pack_size FROM medicines WHERE id = ?;", (l.medicine_id,))
        med = cursor.fetchone()
        if not med:
            cursor.close()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Medicine #{l.medicine_id} does not exist.",
            )
        if not med["is_active"]:
            cursor.close()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Medicine #{l.medicine_id} is inactive and cannot be purchased.",
            )
        if l.pack_size != med["pack_size"]:
            cursor.close()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Pack size {l.pack_size} for medicine #{l.medicine_id} does not match master pack size ({med['pack_size']}).",
            )
        c = _calculate_line(l)
        calc_lines.append(c)
        subtotal_paise += (c["paid_quantity"] * c["purchase_rate_paise"]) - c["discount_paise"]
        total_tax_paise += c["tax_amount_paise"]

    if payload.discount_paise > subtotal_paise:
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invoice discount ({payload.discount_paise} paise) cannot exceed subtotal ({subtotal_paise} paise).",
        )
    inv_discount_paise = payload.discount_paise
    grand_total_paise = subtotal_paise + total_tax_paise - inv_discount_paise

    now_str = datetime.now(timezone.utc).isoformat()
    entry_date = payload.entry_date or now_str[:10]

    cursor.execute("BEGIN IMMEDIATE;")
    try:
        cursor.execute(
            """
            INSERT INTO purchase_invoices (
                supplier_id, supplier_invoice_number, invoice_date, entry_date, status,
                subtotal_paise, discount_paise, tax_amount_paise, grand_total_paise, payment_status, notes,
                created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'DRAFT', ?, ?, ?, ?, 'UNPAID', ?, ?, ?, ?);
            """,
            (
                payload.supplier_id,
                clean_inv_num,
                payload.invoice_date,
                entry_date,
                subtotal_paise,
                inv_discount_paise,
                total_tax_paise,
                grand_total_paise,
                payload.notes,
                current_user["id"],
                now_str,
                now_str,
            ),
        )
        invoice_id = cursor.lastrowid

        for c in calc_lines:
            cursor.execute(
                """
                INSERT INTO purchase_invoice_lines (
                    purchase_invoice_id, medicine_id, batch_number, expiry_date, pack_size,
                    paid_quantity, free_quantity, total_received_quantity, purchase_rate_paise, mrp_paise,
                    discount_paise, gst_percentage, tax_amount_paise, line_total_paise, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    invoice_id,
                    c["medicine_id"],
                    c["batch_number"],
                    c["expiry_date"],
                    c["pack_size"],
                    c["paid_quantity"],
                    c["free_quantity"],
                    c["total_received_quantity"],
                    c["purchase_rate_paise"],
                    c["mrp_paise"],
                    c["discount_paise"],
                    c["gst_percentage"],
                    c["tax_amount_paise"],
                    c["line_total_paise"],
                    now_str,
                ),
            )

        cursor.execute("COMMIT;")
    except Exception as e:
        cursor.execute("ROLLBACK;")
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create draft purchase invoice: {e}",
        ) from e
    finally:
        cursor.close()

    return SuccessResponse(
        data=_fetch_invoice_with_lines(invoice_id, db),
        message="Draft purchase invoice created successfully.",
    )


# ==========================================
# 2. LIST PURCHASES
# ==========================================

@router.get("/api/v1/purchases", response_model=SuccessResponse[PaginatedData[PurchaseInvoiceResponse]], dependencies=[read_guard])
def list_purchases(
    supplier_id: Optional[int] = Query(None, description="Filter by supplier ID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (DRAFT, POSTED, CANCELLED)"),
    from_date: Optional[str] = Query(None, description="Filter from invoice date YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, description="Filter to invoice date YYYY-MM-DD"),
    query: Optional[str] = Query(None, description="Search by invoice number or supplier name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: sqlite3.Connection = Depends(get_db),
):
    """List purchase invoices with pagination and filters."""
    conditions = []
    params = []

    if supplier_id is not None:
        conditions.append("pi.supplier_id = ?")
        params.append(supplier_id)

    if status_filter and status_filter.strip():
        conditions.append("pi.status = ?")
        params.append(status_filter.strip().upper())

    if from_date and from_date.strip():
        conditions.append("pi.invoice_date >= ?")
        params.append(from_date.strip())

    if to_date and to_date.strip():
        conditions.append("pi.invoice_date <= ?")
        params.append(to_date.strip())

    if query and query.strip():
        term = f"%{query.strip()}%"
        conditions.append("(pi.supplier_invoice_number LIKE ? OR s.name LIKE ?)")
        params.extend([term, term])

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    cursor = db.cursor()
    count_sql = f"""
        SELECT COUNT(*)
        FROM purchase_invoices pi
        JOIN suppliers s ON s.id = pi.supplier_id
        {where_clause};
    """
    cursor.execute(count_sql, params)
    total = cursor.fetchone()[0]

    offset = (page - 1) * page_size
    list_sql = f"""
        SELECT pi.*, s.name AS supplier_name, u.full_name AS creator_name
        FROM purchase_invoices pi
        JOIN suppliers s ON s.id = pi.supplier_id
        LEFT JOIN users u ON u.id = pi.created_by
        {where_clause}
        ORDER BY pi.id DESC
        LIMIT ? OFFSET ?;
    """
    cursor.execute(list_sql, params + [page_size, offset])
    rows = cursor.fetchall()
    cursor.close()

    items = [
        PurchaseInvoiceResponse(
            id=r["id"],
            supplier_id=r["supplier_id"],
            supplier_name=r["supplier_name"],
            supplier_invoice_number=r["supplier_invoice_number"],
            invoice_date=r["invoice_date"],
            entry_date=r["entry_date"],
            status=r["status"],
            subtotal_paise=r["subtotal_paise"],
            discount_paise=r["discount_paise"],
            tax_amount_paise=r["tax_amount_paise"],
            grand_total_paise=r["grand_total_paise"],
            payment_status=r["payment_status"],
            notes=r["notes"],
            created_by=r["created_by"],
            creator_name=r["creator_name"],
            created_at=r["created_at"],
            posted_at=r["posted_at"],
            updated_at=r["updated_at"],
        )
        for r in rows
    ]

    total_pages = math.ceil(total / page_size) if total > 0 else 1
    return SuccessResponse(
        data=PaginatedData(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)
    )


# ==========================================
# 3. GET PURCHASE BY ID
# ==========================================

@router.get("/api/v1/purchases/{id}", response_model=SuccessResponse[PurchaseInvoiceResponse], dependencies=[read_guard])
def get_purchase_invoice(id: int, db: sqlite3.Connection = Depends(get_db)):
    """Retrieve full purchase invoice details and lines."""
    inv = _fetch_invoice_with_lines(id, db)
    return SuccessResponse(data=inv)


# ==========================================
# 4. EDIT DRAFT PURCHASE INVOICE
# ==========================================

@router.put("/api/v1/purchases/{id}", response_model=SuccessResponse[PurchaseInvoiceResponse], dependencies=[write_guard])
def update_purchase_invoice(
    id: int,
    payload: UpdatePurchaseInvoiceRequest,
    db: sqlite3.Connection = Depends(get_db),
):
    """Edit only a draft purchase invoice."""
    cursor = db.cursor()
    cursor.execute("SELECT * FROM purchase_invoices WHERE id = ?;", (id,))
    inv = cursor.fetchone()
    if not inv:
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase invoice #{id} not found.",
        )

    if inv["status"] != "DRAFT":
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot edit invoice #{id} because it is in '{inv['status']}' state.",
        )

    sup_id = payload.supplier_id if payload.supplier_id is not None else inv["supplier_id"]
    inv_num = (
        payload.supplier_invoice_number.strip().upper()
        if payload.supplier_invoice_number is not None
        else inv["supplier_invoice_number"]
    )

    # Check unique constraint if supplier or number changed
    if sup_id != inv["supplier_id"] or inv_num != inv["supplier_invoice_number"]:
        cursor.execute(
            "SELECT id FROM purchase_invoices WHERE supplier_id = ? AND UPPER(supplier_invoice_number) = ? AND id != ? AND status != 'CANCELLED';",
            (sup_id, inv_num, id),
        )
        if cursor.fetchone():
            cursor.close()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invoice number '{inv_num}' already exists for this supplier.",
            )

    inv_date = payload.invoice_date or inv["invoice_date"]
    entry_date = payload.entry_date or inv["entry_date"]
    notes = payload.notes if payload.notes is not None else inv["notes"]
    now_str = datetime.now(timezone.utc).isoformat()

    cursor.execute("BEGIN IMMEDIATE;")
    try:
        # If lines provided, recalculate
        if payload.lines is not None:
            if not payload.lines:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Purchase invoice must contain at least one line item.",
                )

            calc_lines = []
            subtotal_paise = 0
            total_tax_paise = 0
            for l in payload.lines:
                cursor.execute("SELECT id, is_active, pack_size FROM medicines WHERE id = ?;", (l.medicine_id,))
                med = cursor.fetchone()
                if not med:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Medicine #{l.medicine_id} does not exist.",
                    )
                if not med["is_active"]:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Medicine #{l.medicine_id} is inactive and cannot be purchased.",
                    )
                if l.pack_size != med["pack_size"]:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Pack size {l.pack_size} for medicine #{l.medicine_id} does not match master pack size ({med['pack_size']}).",
                    )
                c = _calculate_line(l)
                calc_lines.append(c)
                subtotal_paise += (c["paid_quantity"] * c["purchase_rate_paise"]) - c["discount_paise"]
                total_tax_paise += c["tax_amount_paise"]

            if payload.discount_paise is not None and payload.discount_paise > subtotal_paise:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invoice discount ({payload.discount_paise} paise) cannot exceed subtotal ({subtotal_paise} paise).",
                )
            inv_discount_paise = (
                payload.discount_paise
                if payload.discount_paise is not None
                else inv["discount_paise"]
            )
            grand_total_paise = subtotal_paise + total_tax_paise - inv_discount_paise

            cursor.execute("DELETE FROM purchase_invoice_lines WHERE purchase_invoice_id = ?;", (id,))
            for c in calc_lines:
                cursor.execute(
                    """
                    INSERT INTO purchase_invoice_lines (
                        purchase_invoice_id, medicine_id, batch_number, expiry_date, pack_size,
                        paid_quantity, free_quantity, total_received_quantity, purchase_rate_paise, mrp_paise,
                        discount_paise, gst_percentage, tax_amount_paise, line_total_paise, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        id,
                        c["medicine_id"],
                        c["batch_number"],
                        c["expiry_date"],
                        c["pack_size"],
                        c["paid_quantity"],
                        c["free_quantity"],
                        c["total_received_quantity"],
                        c["purchase_rate_paise"],
                        c["mrp_paise"],
                        c["discount_paise"],
                        c["gst_percentage"],
                        c["tax_amount_paise"],
                        c["line_total_paise"],
                        now_str,
                    ),
                )
        else:
            subtotal_paise = inv["subtotal_paise"]
            total_tax_paise = inv["tax_amount_paise"]
            inv_discount_paise = (
                min(payload.discount_paise, subtotal_paise)
                if payload.discount_paise is not None
                else inv["discount_paise"]
            )
            grand_total_paise = subtotal_paise + total_tax_paise - inv_discount_paise

        cursor.execute(
            """
            UPDATE purchase_invoices SET
                supplier_id = ?, supplier_invoice_number = ?, invoice_date = ?, entry_date = ?,
                subtotal_paise = ?, discount_paise = ?, tax_amount_paise = ?, grand_total_paise = ?, notes = ?, updated_at = ?
            WHERE id = ?;
            """,
            (
                sup_id,
                inv_num,
                inv_date,
                entry_date,
                subtotal_paise,
                inv_discount_paise,
                total_tax_paise,
                grand_total_paise,
                notes,
                now_str,
                id,
            ),
        )
        cursor.execute("COMMIT;")
    except HTTPException:
        db.execute("ROLLBACK;")
        raise
    except Exception as e:
        db.execute("ROLLBACK;")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update draft invoice: {e}",
        ) from e
    finally:
        cursor.close()

    return SuccessResponse(
        data=_fetch_invoice_with_lines(id, db),
        message="Purchase invoice updated successfully.",
    )


# ==========================================
# 5. ATOMICALLY POST PURCHASE INVOICE
# ==========================================

@router.post("/api/v1/purchases/{id}/post", response_model=SuccessResponse[PurchaseInvoiceResponse], dependencies=[write_guard])
def post_purchase_invoice(
    id: int,
    db: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Validate and atomically post a purchase invoice, inwarding batches, ledger, and payables."""
    cursor = db.cursor()
    cursor.execute("SELECT * FROM purchase_invoices WHERE id = ?;", (id,))
    inv = cursor.fetchone()
    if not inv:
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase invoice #{id} not found.",
        )

    if inv["status"] == "POSTED":
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Purchase invoice #{id} is already posted.",
        )

    if inv["status"] != "DRAFT":
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot post invoice #{id} with status '{inv['status']}'.",
        )

    # Fetch lines
    cursor.execute(
        "SELECT * FROM purchase_invoice_lines WHERE purchase_invoice_id = ? ORDER BY id ASC;",
        (id,),
    )
    lines = cursor.fetchall()
    if not lines:
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot post a purchase invoice with zero line items.",
        )

    now_str = datetime.now(timezone.utc).isoformat()
    supplier_id = inv["supplier_id"]
    grand_total_paise = inv["grand_total_paise"]

    cursor.execute("BEGIN IMMEDIATE;")
    try:
        # Recheck invoice status inside the write transaction to prevent concurrent double posting
        cursor.execute("SELECT status FROM purchase_invoices WHERE id = ?;", (id,))
        locked_inv = cursor.fetchone()
        if not locked_inv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Purchase invoice #{id} not found.",
            )
        if locked_inv["status"] == "POSTED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Purchase invoice #{id} is already posted.",
            )
        if locked_inv["status"] != "DRAFT":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot post invoice #{id} with status '{locked_inv['status']}'.",
            )

        for line in lines:
            med_id = line["medicine_id"]
            batch_num = line["batch_number"]
            exp_date = line["expiry_date"]
            pack_size = line["pack_size"]
            total_rx_packs = line["total_received_quantity"]
            base_units_inward = total_rx_packs * pack_size
            mrp_paise = line["mrp_paise"]
            ptr_paise = line["purchase_rate_paise"]

            # Check if batch exists for (medicine_id, batch_number)
            cursor.execute(
                "SELECT id, current_quantity FROM medicine_batches WHERE medicine_id = ? AND batch_number = ?;",
                (med_id, batch_num),
            )
            existing_batch = cursor.fetchone()

            if existing_batch:
                batch_id = existing_batch["id"]
                new_batch_qty = existing_batch["current_quantity"] + base_units_inward
                cursor.execute(
                    """
                    UPDATE medicine_batches SET
                        current_quantity = ?,
                        mrp_paise = ?,
                        purchase_rate_paise = ?,
                        pack_size = ?,
                        expiry_date = ?,
                        is_active = 1,
                        updated_at = ?
                    WHERE id = ?;
                    """,
                    (new_batch_qty, mrp_paise, ptr_paise, pack_size, exp_date, now_str, batch_id),
                )
                ledger_balance = new_batch_qty
            else:
                cursor.execute(
                    """
                    INSERT INTO medicine_batches (
                        medicine_id, batch_number, expiry_date, mrp_paise, purchase_rate_paise, pack_size,
                        current_quantity, reserved_quantity, is_active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 1, ?, ?);
                    """,
                    (med_id, batch_num, exp_date, mrp_paise, ptr_paise, pack_size, base_units_inward, now_str, now_str),
                )
                batch_id = cursor.lastrowid
                ledger_balance = base_units_inward

            # Insert into inventory_ledger
            cursor.execute(
                """
                INSERT INTO inventory_ledger (
                    medicine_id, batch_id, transaction_type, quantity_change, quantity_balance,
                    reference_type, reference_id, notes, user_id, created_at
                ) VALUES (?, ?, 'PURCHASE_INWARD', ?, ?, 'PURCHASE_INVOICE', ?, ?, ?, ?);
                """,
                (
                    med_id,
                    batch_id,
                    base_units_inward,
                    ledger_balance,
                    id,
                    f"Inward {total_rx_packs} packs (Scheme: {line['paid_quantity']}+{line['free_quantity']})",
                    current_user["id"],
                    now_str,
                ),
            )

        # Accrue supplier payable
        cursor.execute("SELECT current_payable_paise FROM suppliers WHERE id = ?;", (supplier_id,))
        sup_row = cursor.fetchone()
        current_payable_paise = sup_row["current_payable_paise"] if sup_row else 0
        new_payable_paise = current_payable_paise + grand_total_paise

        cursor.execute("UPDATE suppliers SET current_payable_paise = ? WHERE id = ?;", (new_payable_paise, supplier_id))

        cursor.execute(
            """
            INSERT INTO supplier_payable_ledger (
                supplier_id, reference_type, reference_id, entry_type, amount_paise, balance_paise, notes, created_at
            ) VALUES (?, 'PURCHASE_INVOICE', ?, 'CREDIT', ?, ?, ?, ?);
            """,
            (
                supplier_id,
                id,
                grand_total_paise,
                new_payable_paise,
                f"Inward Purchase Bill #{inv['supplier_invoice_number']}",
                now_str,
            ),
        )

        # Update purchase_invoices status to POSTED
        cursor.execute(
            "UPDATE purchase_invoices SET status = 'POSTED', posted_at = ?, updated_at = ? WHERE id = ?;",
            (now_str, now_str, id),
        )

        cursor.execute("COMMIT;")
    except HTTPException:
        db.execute("ROLLBACK;")
        raise
    except Exception as e:
        db.execute("ROLLBACK;")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Atomic purchase posting failed: {e}",
        ) from e
    finally:
        cursor.close()

    return SuccessResponse(
        data=_fetch_invoice_with_lines(id, db),
        message=f"Purchase invoice #{id} posted successfully. Stock and supplier payable accrued.",
    )


# ==========================================
# 6. SUPPLIER PAYABLES HISTORY
# ==========================================

@router.get("/api/v1/suppliers/{id}/payables", response_model=SuccessResponse[SupplierPayableHistoryResponse], dependencies=[read_guard])
def get_supplier_payables_history(id: int, db: sqlite3.Connection = Depends(get_db)):
    """Fetch distributor current payable balance and complete ledger history."""
    cursor = db.cursor()
    cursor.execute("SELECT id, name, current_payable_paise FROM suppliers WHERE id = ?;", (id,))
    sup = cursor.fetchone()
    if not sup:
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier #{id} not found.",
        )

    cursor.execute(
        """
        SELECT id, supplier_id, reference_type, reference_id, entry_type, amount_paise, balance_paise, notes, created_at
        FROM supplier_payable_ledger
        WHERE supplier_id = ?
        ORDER BY id DESC;
        """,
        (id,),
    )
    rows = cursor.fetchall()
    cursor.close()

    entries = [
        SupplierPayableEntryResponse(
            id=r["id"],
            supplier_id=r["supplier_id"],
            reference_type=r["reference_type"],
            reference_id=r["reference_id"],
            entry_type=r["entry_type"],
            amount_paise=r["amount_paise"],
            balance_paise=r["balance_paise"],
            notes=r["notes"],
            created_at=r["created_at"],
        )
        for r in rows
    ]

    return SuccessResponse(
        data=SupplierPayableHistoryResponse(
            supplier_id=sup["id"],
            supplier_name=sup["name"],
            current_payable_paise=sup["current_payable_paise"],
            entries=entries,
        )
    )
