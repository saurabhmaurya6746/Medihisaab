"""Customer Sales Returns (Credit Notes) and Supplier Purchase Returns (Debit Notes) router."""

from datetime import datetime, timezone
import math
import sqlite3
from typing import Any, Dict, List, Optional
import urllib.parse
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..security.roles import UserRole
from .dependencies import get_db, get_current_user, require_role, require_write_role
from .schemas import (
    InvoiceForReturnLookupResponse,
    InvoiceReturnableItemResponse,
    PaginatedData,
    PurchaseInvoiceForReturnLookupResponse,
    PurchaseInvoiceReturnableLineResponse,
    PurchaseReturnCreateRequest,
    PurchaseReturnItemResponse,
    PurchaseReturnResponse,
    SalesReturnCreateRequest,
    SalesReturnItemResponse,
    SalesReturnResponse,
    SuccessResponse,
)

router = APIRouter(prefix="/api/v1/returns", tags=["Sales & Purchase Returns"])

read_guard = Depends(require_role(UserRole.ADMIN, UserRole.PHARMACIST, UserRole.CASHIER))
write_guard = Depends(require_write_role(UserRole.ADMIN, UserRole.PHARMACIST))


def _round_half_up(val: float) -> int:
    return math.floor(val + 0.5)


# =========================================================================
# 1. SALES RETURNS: LOOKUP SALE INVOICE FOR RETURN
# =========================================================================

@router.get("/sales/invoice/{invoice_identifier}", response_model=SuccessResponse[InvoiceForReturnLookupResponse], dependencies=[read_guard])
def lookup_sale_invoice_for_return(
    invoice_identifier: str,
    db: sqlite3.Connection = Depends(get_db),
):
    """Fetch sale invoice by ID or Invoice Number with previous returns calculation and remaining returnable limits."""
    cursor = db.cursor()
    decoded = urllib.parse.unquote(invoice_identifier).strip()

    # Match by ID or invoice_no
    cursor.execute("""
        SELECT si.*, c.name AS cust_name, c.phone AS cust_phone, c.current_balance_paise
        FROM sale_invoices si
        LEFT JOIN customers c ON c.id = si.customer_id
        WHERE si.id = ? OR UPPER(si.invoice_no) = UPPER(?);
    """, (decoded if decoded.isdigit() else -1, decoded))
    inv = cursor.fetchone()

    if not inv:
        cursor.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sale invoice '{decoded}' not found.")

    if inv["status"] != "COMPLETED":
        cursor.close()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invoice '{inv['invoice_no']}' has status '{inv['status']}' and cannot be returned.")

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    cursor.execute("""
        SELECT sit.id, sit.medicine_id, m.brand_name, m.dosage_form, m.pack_size,
               sit.batch_id, mb.batch_number, mb.expiry_date,
               sit.quantity_units, sit.unit_rate_paise, sit.gst_rate, sit.discount_percent
        FROM sale_items sit
        JOIN medicines m ON m.id = sit.medicine_id
        JOIN medicine_batches mb ON mb.id = sit.batch_id
        WHERE sit.sale_invoice_id = ?
        ORDER BY sit.id ASC;
    """, (inv["id"],))
    items_rows = cursor.fetchall()

    items: List[InvoiceReturnableItemResponse] = []
    for r in items_rows:
        sale_item_id = r["id"]

        # Calculate previous returns
        cursor.execute("""
            SELECT COALESCE(SUM(quantity_units), 0) AS returned_qty
            FROM sales_return_items
            WHERE sale_item_id = ?;
        """, (sale_item_id,))
        ret_row = cursor.fetchone()
        previously_returned = ret_row["returned_qty"] if ret_row else 0
        sold_qty = r["quantity_units"]
        returnable_qty = max(0, sold_qty - previously_returned)

        is_expired = r["expiry_date"] <= today_str

        items.append(
            InvoiceReturnableItemResponse(
                sale_item_id=sale_item_id,
                medicine_id=r["medicine_id"],
                medicine_name=r["brand_name"],
                dosage_form=r["dosage_form"],
                pack_size=r["pack_size"],
                batch_id=r["batch_id"],
                batch_number=r["batch_number"],
                expiry_date=r["expiry_date"],
                is_expired=is_expired,
                sold_quantity_units=sold_qty,
                previously_returned_units=previously_returned,
                returnable_quantity_units=returnable_qty,
                unit_rate_paise=r["unit_rate_paise"],
                gst_rate=r["gst_rate"],
                discount_percent=r["discount_percent"],
            )
        )

    cursor.close()

    result = InvoiceForReturnLookupResponse(
        invoice_id=inv["id"],
        invoice_no=inv["invoice_no"],
        fiscal_year=inv["fiscal_year"],
        invoice_date=inv["created_at"],
        customer_id=inv["customer_id"],
        customer_name=inv["customer_name"] or inv["cust_name"],
        customer_phone=inv["customer_phone"] or inv["cust_phone"],
        customer_balance_paise=inv["current_balance_paise"],
        grand_total_paise=inv["grand_total_paise"],
        payment_mode=inv["payment_mode"],
        items=items,
    )
    return SuccessResponse(data=result)


# =========================================================================
# 2. SALES RETURNS: PROCESS CUSTOMER SALES RETURN
# =========================================================================

@router.post("/sales", response_model=SuccessResponse[SalesReturnResponse], status_code=status.HTTP_201_CREATED, dependencies=[write_guard])
def process_sales_return(
    payload: SalesReturnCreateRequest,
    db: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Atomically commit a customer sales return (credit note), restock resellable items, and adjust Khata if applicable."""
    if not payload.items:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="At least one item must be returned.")

    now = datetime.now(timezone.utc)
    now_str = now.isoformat()
    today_str = now.strftime("%Y-%m-%d")
    date_code = now.strftime("%Y%m%d")
    unique_suffix = uuid.uuid4().hex[:6].upper()
    return_number = f"CN-{date_code}-{unique_suffix}"

    cursor = db.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE;")

        # Validate invoice exists
        cursor.execute("SELECT * FROM sale_invoices WHERE id = ?;", (payload.sale_invoice_id,))
        inv = cursor.fetchone()
        if not inv:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sale invoice #{payload.sale_invoice_id} not found.")
        if inv["status"] != "COMPLETED":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Sale invoice #{payload.sale_invoice_id} has status '{inv['status']}' and cannot be returned.")

        cust_id = inv["customer_id"]
        if payload.refund_mode in ("KHATA", "STORE_CREDIT") and not cust_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Refund mode KHATA or STORE_CREDIT requires a registered customer account on the invoice.",
            )

        total_taxable_paise = 0
        total_cgst_paise = 0
        total_sgst_paise = 0
        total_refund_paise = 0

        validated_items = []

        for item_in in payload.items:
            # Fetch original sale_item
            cursor.execute("""
                SELECT sit.*, mb.batch_number, mb.expiry_date, mb.current_quantity, m.brand_name, m.dosage_form, m.pack_size
                FROM sale_items sit
                JOIN medicine_batches mb ON mb.id = sit.batch_id
                JOIN medicines m ON m.id = sit.medicine_id
                WHERE sit.id = ? AND sit.sale_invoice_id = ?;
            """, (item_in.sale_item_id, payload.sale_invoice_id))
            sale_item = cursor.fetchone()

            if not sale_item:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Sale item #{item_in.sale_item_id} does not belong to invoice #{payload.sale_invoice_id}.",
                )

            # Check previously returned quantity
            cursor.execute("""
                SELECT COALESCE(SUM(quantity_units), 0) FROM sales_return_items WHERE sale_item_id = ?;
            """, (item_in.sale_item_id,))
            previously_returned = cursor.fetchone()[0]

            available_to_return = sale_item["quantity_units"] - previously_returned
            if item_in.quantity_units > available_to_return:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Cannot return {item_in.quantity_units} units of '{sale_item['brand_name']}'. Only {available_to_return} units available for return (Sold: {sale_item['quantity_units']}, Previously Returned: {previously_returned}).",
                )

            # Financial calculation matching original pro-rata sale
            unit_rate = sale_item["unit_rate_paise"]
            gross_paise = unit_rate * item_in.quantity_units
            discount_pct = sale_item["discount_percent"]
            line_disc_paise = _round_half_up(gross_paise * (discount_pct / 100.0))
            line_taxable_paise = max(0, gross_paise - line_disc_paise)

            gst_rate = sale_item["gst_rate"]
            half_gst = gst_rate / 2.0
            line_cgst_paise = _round_half_up(line_taxable_paise * (half_gst / 100.0))
            line_sgst_paise = _round_half_up(line_taxable_paise * (half_gst / 100.0))
            line_total_paise = line_taxable_paise + line_cgst_paise + line_sgst_paise

            total_taxable_paise += line_taxable_paise
            total_cgst_paise += line_cgst_paise
            total_sgst_paise += line_sgst_paise
            total_refund_paise += line_total_paise

            is_expired = sale_item["expiry_date"] <= today_str
            # Cannot resell expired items even if requested
            is_resellable = item_in.is_resellable and not is_expired

            validated_items.append({
                "sale_item": sale_item,
                "input": item_in,
                "taxable_paise": line_taxable_paise,
                "cgst_paise": line_cgst_paise,
                "sgst_paise": line_sgst_paise,
                "line_total_paise": line_total_paise,
                "is_resellable": is_resellable,
                "is_expired": is_expired,
            })

        # Insert sales_returns header
        cursor.execute("""
            INSERT INTO sales_returns (
                return_number, sale_invoice_id, customer_id, customer_name, refund_mode,
                subtotal_taxable_paise, total_cgst_paise, total_sgst_paise, total_igst_paise,
                refund_amount_paise, reason, notes, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?);
        """, (
            return_number,
            payload.sale_invoice_id,
            cust_id,
            inv["customer_name"],
            payload.refund_mode,
            total_taxable_paise,
            total_cgst_paise,
            total_sgst_paise,
            total_refund_paise,
            payload.reason.strip(),
            payload.notes.strip() if payload.notes else None,
            current_user["id"],
            now_str,
        ))
        sales_return_id = cursor.lastrowid

        # Insert items and process restocking or wastage
        result_items: List[SalesReturnItemResponse] = []

        for v in validated_items:
            si = v["sale_item"]
            inp = v["input"]

            cursor.execute("""
                INSERT INTO sales_return_items (
                    sales_return_id, sale_item_id, medicine_id, batch_id, quantity_units,
                    unit_rate_paise, taxable_amount_paise, gst_rate, cgst_amount_paise,
                    sgst_amount_paise, total_amount_paise, is_resellable, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                sales_return_id,
                inp.sale_item_id,
                si["medicine_id"],
                si["batch_id"],
                inp.quantity_units,
                si["unit_rate_paise"],
                v["taxable_paise"],
                si["gst_rate"],
                v["cgst_paise"],
                v["sgst_paise"],
                v["line_total_paise"],
                1 if v["is_resellable"] else 0,
                now_str,
            ))
            sri_id = cursor.lastrowid

            if v["is_resellable"]:
                # Restock inventory
                cursor.execute("""
                    UPDATE medicine_batches
                    SET current_quantity = current_quantity + ?, updated_at = ?
                    WHERE id = ?;
                """, (inp.quantity_units, now_str, si["batch_id"]))

                cursor.execute("SELECT current_quantity FROM medicine_batches WHERE id = ?;", (si["batch_id"],))
                new_batch_qty = cursor.fetchone()[0]

                cursor.execute("""
                    INSERT INTO inventory_ledger (
                        medicine_id, batch_id, transaction_type, quantity_change, quantity_balance,
                        reference_type, reference_id, notes, user_id, created_at
                    ) VALUES (?, ?, 'SALE_RETURN', ?, ?, 'SALES_RETURN', ?, ?, ?, ?);
                """, (
                    si["medicine_id"],
                    si["batch_id"],
                    inp.quantity_units,
                    new_batch_qty,
                    sales_return_id,
                    f"Return restocked from Credit Note {return_number}",
                    current_user["id"],
                    now_str,
                ))
            else:
                # Record as wastage
                wastage_reason = "EXPIRED" if v["is_expired"] else "DAMAGED"
                wastage_ref = f"WST-{date_code}-{uuid.uuid4().hex[:6].upper()}"
                cursor.execute("""
                    INSERT INTO wastage_register (
                        reference_no, batch_id, medicine_id, quantity_units, reason,
                        cost_impact_paise, notes, reference_type, reference_id, created_by, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'SALES_RETURN', ?, ?, ?);
                """, (
                    wastage_ref,
                    si["batch_id"],
                    si["medicine_id"],
                    inp.quantity_units,
                    wastage_reason,
                    v["line_total_paise"],
                    f"Customer return not resellable ({inp.reason or payload.reason})",
                    sales_return_id,
                    current_user["id"],
                    now_str,
                ))

            result_items.append(
                SalesReturnItemResponse(
                    id=sri_id,
                    sales_return_id=sales_return_id,
                    sale_item_id=inp.sale_item_id,
                    medicine_id=si["medicine_id"],
                    medicine_name=si["brand_name"],
                    dosage_form=si["dosage_form"],
                    pack_size=si["pack_size"],
                    batch_id=si["batch_id"],
                    batch_number=si["batch_number"],
                    expiry_date=si["expiry_date"],
                    quantity_units=inp.quantity_units,
                    unit_rate_paise=si["unit_rate_paise"],
                    taxable_amount_paise=v["taxable_paise"],
                    gst_rate=si["gst_rate"],
                    cgst_amount_paise=v["cgst_paise"],
                    sgst_amount_paise=v["sgst_paise"],
                    total_amount_paise=v["line_total_paise"],
                    is_resellable=v["is_resellable"],
                    created_at=now_str,
                )
            )

        # Update Khata if refund mode is KHATA or STORE_CREDIT
        if payload.refund_mode in ("KHATA", "STORE_CREDIT") and cust_id:
            cursor.execute("""
                UPDATE customers
                SET current_balance_paise = current_balance_paise - ?, updated_at = ?
                WHERE id = ?;
            """, (total_refund_paise, now_str, cust_id))

            cursor.execute("SELECT current_balance_paise FROM customers WHERE id = ?;", (cust_id,))
            new_cust_balance = cursor.fetchone()[0]

            cursor.execute("""
                INSERT INTO khata_ledger (
                    customer_id, transaction_type, entry_type, amount_paise, balance_paise,
                    reference_type, reference_id, notes, user_id, created_at
                ) VALUES (?, 'RETURN_REFUND', 'CREDIT', ?, ?, 'SALES_RETURN', ?, ?, ?, ?);
            """, (
                cust_id,
                total_refund_paise,
                new_cust_balance,
                sales_return_id,
                f"Sales Return Credit Note {return_number}",
                current_user["id"],
                now_str,
            ))

        cursor.execute("COMMIT;")
    except HTTPException:
        cursor.execute("ROLLBACK;")
        cursor.close()
        raise
    except Exception as e:
        cursor.execute("ROLLBACK;")
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process sales return: {e}",
        ) from e

    response_data = SalesReturnResponse(
        id=sales_return_id,
        return_number=return_number,
        sale_invoice_id=payload.sale_invoice_id,
        invoice_no=inv["invoice_no"],
        customer_id=cust_id,
        customer_name=inv["customer_name"],
        refund_mode=payload.refund_mode,
        subtotal_taxable_paise=total_taxable_paise,
        total_cgst_paise=total_cgst_paise,
        total_sgst_paise=total_sgst_paise,
        total_igst_paise=0,
        refund_amount_paise=total_refund_paise,
        reason=payload.reason,
        notes=payload.notes,
        created_by=current_user["id"],
        created_by_name=current_user.get("full_name") or current_user.get("username"),
        created_at=now_str,
        items=result_items,
    )
    return SuccessResponse(data=response_data, message="Sales return processed successfully.")


# =========================================================================
# 3. SALES RETURNS: LIST & GET DETAILS
# =========================================================================

@router.get("/sales", response_model=SuccessResponse[PaginatedData[SalesReturnResponse]], dependencies=[read_guard])
def list_sales_returns(
    query: Optional[str] = Query(None, description="Search by return number or invoice number"),
    customer_id: Optional[int] = Query(None, description="Filter by customer ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: sqlite3.Connection = Depends(get_db),
):
    """List customer sales returns with pagination."""
    cursor = db.cursor()
    conditions = []
    params: List[Any] = []

    if customer_id:
        conditions.append("sr.customer_id = ?")
        params.append(customer_id)

    if query:
        conditions.append("(sr.return_number LIKE ? OR si.invoice_no LIKE ? OR sr.customer_name LIKE ?)")
        wild = f"%{query.strip()}%"
        params.extend([wild, wild, wild])

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    cursor.execute(f"""
        SELECT COUNT(*)
        FROM sales_returns sr
        JOIN sale_invoices si ON si.id = sr.sale_invoice_id
        {where_sql};
    """, params)
    total = cursor.fetchone()[0]

    offset = (page - 1) * page_size
    cursor.execute(f"""
        SELECT sr.*, si.invoice_no, u.username, u.full_name
        FROM sales_returns sr
        JOIN sale_invoices si ON si.id = sr.sale_invoice_id
        LEFT JOIN users u ON u.id = sr.created_by
        {where_sql}
        ORDER BY sr.created_at DESC, sr.id DESC
        LIMIT ? OFFSET ?;
    """, params + [page_size, offset])
    rows = cursor.fetchall()

    items: List[SalesReturnResponse] = []
    for r in rows:
        cursor.execute("""
            SELECT sri.*, m.brand_name, m.dosage_form, m.pack_size, mb.batch_number, mb.expiry_date
            FROM sales_return_items sri
            JOIN medicines m ON m.id = sri.medicine_id
            JOIN medicine_batches mb ON mb.id = sri.batch_id
            WHERE sri.sales_return_id = ?
            ORDER BY sri.id ASC;
        """, (r["id"],))
        sri_rows = cursor.fetchall()

        item_list = [
            SalesReturnItemResponse(
                id=it["id"],
                sales_return_id=it["sales_return_id"],
                sale_item_id=it["sale_item_id"],
                medicine_id=it["medicine_id"],
                medicine_name=it["brand_name"],
                dosage_form=it["dosage_form"],
                pack_size=it["pack_size"],
                batch_id=it["batch_id"],
                batch_number=it["batch_number"],
                expiry_date=it["expiry_date"],
                quantity_units=it["quantity_units"],
                unit_rate_paise=it["unit_rate_paise"],
                taxable_amount_paise=it["taxable_amount_paise"],
                gst_rate=it["gst_rate"],
                cgst_amount_paise=it["cgst_amount_paise"],
                sgst_amount_paise=it["sgst_amount_paise"],
                total_amount_paise=it["total_amount_paise"],
                is_resellable=bool(it["is_resellable"]),
                created_at=it["created_at"],
            )
            for it in sri_rows
        ]

        items.append(
            SalesReturnResponse(
                id=r["id"],
                return_number=r["return_number"],
                sale_invoice_id=r["sale_invoice_id"],
                invoice_no=r["invoice_no"],
                customer_id=r["customer_id"],
                customer_name=r["customer_name"],
                refund_mode=r["refund_mode"],
                subtotal_taxable_paise=r["subtotal_taxable_paise"],
                total_cgst_paise=r["total_cgst_paise"],
                total_sgst_paise=r["total_sgst_paise"],
                total_igst_paise=r["total_igst_paise"],
                refund_amount_paise=r["refund_amount_paise"],
                reason=r["reason"],
                notes=r["notes"],
                created_by=r["created_by"],
                created_by_name=r["full_name"] or r["username"],
                created_at=r["created_at"],
                items=item_list,
            )
        )

    cursor.close()
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    return SuccessResponse(data=PaginatedData(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages))


# =========================================================================
# 4. PURCHASE RETURNS: LOOKUP PURCHASE INVOICE FOR RETURN
# =========================================================================

@router.get("/purchases/invoice/{invoice_identifier}", response_model=SuccessResponse[PurchaseInvoiceForReturnLookupResponse], dependencies=[read_guard])
def lookup_purchase_invoice_for_return(
    invoice_identifier: str,
    db: sqlite3.Connection = Depends(get_db),
):
    """Fetch purchase invoice by ID or supplier invoice number with line return limits and live batch stock."""
    cursor = db.cursor()
    decoded = urllib.parse.unquote(invoice_identifier).strip()

    cursor.execute("""
        SELECT pi.*, s.name AS sup_name, s.current_payable_paise
        FROM purchase_invoices pi
        JOIN suppliers s ON s.id = pi.supplier_id
        WHERE pi.id = ? OR UPPER(pi.supplier_invoice_number) = UPPER(?);
    """, (decoded if decoded.isdigit() else -1, decoded))
    pi = cursor.fetchone()

    if not pi:
        cursor.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Purchase invoice '{decoded}' not found.")

    if pi["status"] != "POSTED":
        cursor.close()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Purchase invoice #{pi['id']} has status '{pi['status']}' and cannot be returned (must be POSTED).")

    cursor.execute("""
        SELECT pil.id, pil.medicine_id, m.brand_name, pil.batch_number, pil.expiry_date,
               pil.pack_size, pil.total_received_quantity, pil.purchase_rate_paise, pil.gst_percentage,
               mb.id AS batch_id, mb.current_quantity AS batch_current_quantity
        FROM purchase_invoice_lines pil
        JOIN medicines m ON m.id = pil.medicine_id
        LEFT JOIN medicine_batches mb ON mb.medicine_id = pil.medicine_id AND mb.batch_number = pil.batch_number
        WHERE pil.purchase_invoice_id = ?
        ORDER BY pil.id ASC;
    """, (pi["id"],))
    lines_rows = cursor.fetchall()

    lines: List[PurchaseInvoiceReturnableLineResponse] = []
    for r in lines_rows:
        line_id = r["id"]

        # Calculate previously returned units
        cursor.execute("""
            SELECT COALESCE(SUM(return_units), 0) FROM purchase_return_items WHERE purchase_invoice_line_id = ?;
        """, (line_id,))
        previously_returned = cursor.fetchone()[0]

        total_rx_units = r["total_received_quantity"] * r["pack_size"]
        available_return_units = max(0, total_rx_units - previously_returned)
        batch_stock = r["batch_current_quantity"] if r["batch_current_quantity"] is not None else 0

        lines.append(
            PurchaseInvoiceReturnableLineResponse(
                purchase_invoice_line_id=line_id,
                medicine_id=r["medicine_id"],
                medicine_name=r["brand_name"],
                batch_id=r["batch_id"] or 0,
                batch_number=r["batch_number"],
                expiry_date=r["expiry_date"],
                pack_size=r["pack_size"],
                total_received_units=total_rx_units,
                previously_returned_units=previously_returned,
                available_return_units=available_return_units,
                current_batch_stock_units=batch_stock,
                purchase_rate_paise=r["purchase_rate_paise"],
                gst_percentage=r["gst_percentage"],
            )
        )

    cursor.close()

    result = PurchaseInvoiceForReturnLookupResponse(
        invoice_id=pi["id"],
        supplier_invoice_number=pi["supplier_invoice_number"],
        supplier_id=pi["supplier_id"],
        supplier_name=pi["sup_name"],
        invoice_date=pi["invoice_date"],
        grand_total_paise=pi["grand_total_paise"],
        supplier_current_payable_paise=pi["current_payable_paise"],
        lines=lines,
    )
    return SuccessResponse(data=result)


# =========================================================================
# 5. PURCHASE RETURNS: PROCESS DISTRIBUTOR DEBIT NOTE
# =========================================================================

@router.post("/purchases", response_model=SuccessResponse[PurchaseReturnResponse], status_code=status.HTTP_201_CREATED, dependencies=[write_guard])
def process_purchase_return(
    payload: PurchaseReturnCreateRequest,
    db: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Atomically commit a distributor debit note, deduct batch stock, and reduce supplier payable balance."""
    if not payload.items:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="At least one line item must be returned.")

    now = datetime.now(timezone.utc)
    now_str = now.isoformat()
    date_code = now.strftime("%Y%m%d")
    unique_suffix = uuid.uuid4().hex[:6].upper()
    debit_note_number = f"DN-{date_code}-{unique_suffix}"

    cursor = db.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE;")

        cursor.execute("""
            SELECT pi.*, s.name AS sup_name, s.current_payable_paise
            FROM purchase_invoices pi
            JOIN suppliers s ON s.id = pi.supplier_id
            WHERE pi.id = ?;
        """, (payload.purchase_invoice_id,))
        pi = cursor.fetchone()

        if not pi:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Purchase invoice #{payload.purchase_invoice_id} not found.")
        if pi["status"] != "POSTED":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Purchase invoice #{payload.purchase_invoice_id} is not POSTED.")

        supplier_id = pi["supplier_id"]

        total_taxable_paise = 0
        total_tax_paise = 0
        total_debit_amount_paise = 0

        validated_lines = []

        for item_in in payload.items:
            cursor.execute("""
                SELECT pil.*, m.brand_name, mb.id AS batch_id, mb.current_quantity AS batch_current_qty
                FROM purchase_invoice_lines pil
                JOIN medicines m ON m.id = pil.medicine_id
                LEFT JOIN medicine_batches mb ON mb.medicine_id = pil.medicine_id AND mb.batch_number = pil.batch_number
                WHERE pil.id = ? AND pil.purchase_invoice_id = ?;
            """, (item_in.purchase_invoice_line_id, payload.purchase_invoice_id))
            line = cursor.fetchone()

            if not line:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Line #{item_in.purchase_invoice_line_id} does not belong to purchase invoice #{payload.purchase_invoice_id}.",
                )

            total_received_units = line["total_received_quantity"] * line["pack_size"]

            # Calculate previously returned units
            cursor.execute("""
                SELECT COALESCE(SUM(return_units), 0) FROM purchase_return_items WHERE purchase_invoice_line_id = ?;
            """, (item_in.purchase_invoice_line_id,))
            previously_returned = cursor.fetchone()[0]

            available_return_units = total_received_units - previously_returned
            if item_in.return_units > available_return_units:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Cannot return {item_in.return_units} units for line '{line['brand_name']}'. Only {available_return_units} units available for return.",
                )

            batch_id = line["batch_id"]
            batch_stock = line["batch_current_qty"] if line["batch_current_qty"] is not None else 0

            # Prevent reducing stock below zero
            if batch_stock < item_in.return_units:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Insufficient physical stock for '{line['brand_name']}' batch '{line['batch_number']}'! Current stock: {batch_stock} units, Return requested: {item_in.return_units} units. Cannot reduce stock below zero.",
                )

            # Integer commercial math for debit note line
            # Base pro-rata rate per unit
            pack_size = line["pack_size"]
            ptr_paise = line["purchase_rate_paise"]
            unit_rate_paise = ptr_paise // pack_size if pack_size > 0 else ptr_paise

            # Total pro-rata taxable based on original line
            orig_line_taxable_paise = line["line_total_paise"] - line["tax_amount_paise"]
            line_taxable_paise = (orig_line_taxable_paise * item_in.return_units) // total_received_units
            line_tax_paise = (line["tax_amount_paise"] * item_in.return_units) // total_received_units
            line_total_paise = line_taxable_paise + line_tax_paise

            total_taxable_paise += line_taxable_paise
            total_tax_paise += line_tax_paise
            total_debit_amount_paise += line_total_paise

            validated_lines.append({
                "line": line,
                "input": item_in,
                "batch_id": batch_id,
                "taxable_paise": line_taxable_paise,
                "tax_paise": line_tax_paise,
                "line_total_paise": line_total_paise,
                "unit_rate_paise": ptr_paise,
            })

        # Insert purchase_returns header
        cursor.execute("""
            INSERT INTO purchase_returns (
                debit_note_number, purchase_invoice_id, supplier_id, subtotal_taxable_paise,
                total_tax_paise, total_amount_paise, reason, notes, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            debit_note_number,
            payload.purchase_invoice_id,
            supplier_id,
            total_taxable_paise,
            total_tax_paise,
            total_debit_amount_paise,
            payload.reason.strip(),
            payload.notes.strip() if payload.notes else None,
            current_user["id"],
            now_str,
        ))
        purchase_return_id = cursor.lastrowid

        result_items: List[PurchaseReturnItemResponse] = []

        for v in validated_lines:
            line = v["line"]
            inp = v["input"]
            batch_id = v["batch_id"]

            cursor.execute("""
                INSERT INTO purchase_return_items (
                    purchase_return_id, purchase_invoice_line_id, medicine_id, batch_id,
                    return_packs, return_units, purchase_rate_paise, taxable_amount_paise,
                    gst_percentage, tax_amount_paise, line_total_paise, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                purchase_return_id,
                inp.purchase_invoice_line_line_id if hasattr(inp, "purchase_invoice_line_line_id") else inp.purchase_invoice_line_id,
                line["medicine_id"],
                batch_id,
                inp.return_packs or 0,
                inp.return_units,
                v["unit_rate_paise"],
                v["taxable_paise"],
                line["gst_percentage"],
                v["tax_paise"],
                v["line_total_paise"],
                now_str,
            ))
            pri_id = cursor.lastrowid

            # Deduct batch stock
            cursor.execute("""
                UPDATE medicine_batches
                SET current_quantity = current_quantity - ?, updated_at = ?
                WHERE id = ?;
            """, (inp.return_units, now_str, batch_id))

            cursor.execute("SELECT current_quantity FROM medicine_batches WHERE id = ?;", (batch_id,))
            new_batch_stock = cursor.fetchone()[0]

            # Insert into inventory_ledger
            cursor.execute("""
                INSERT INTO inventory_ledger (
                    medicine_id, batch_id, transaction_type, quantity_change, quantity_balance,
                    reference_type, reference_id, notes, user_id, created_at
                ) VALUES (?, ?, 'PURCHASE_RETURN', ?, ?, 'PURCHASE_RETURN', ?, ?, ?, ?);
            """, (
                line["medicine_id"],
                batch_id,
                -inp.return_units,
                new_batch_stock,
                purchase_return_id,
                f"Debit Note {debit_note_number}",
                current_user["id"],
                now_str,
            ))

            result_items.append(
                PurchaseReturnItemResponse(
                    id=pri_id,
                    purchase_return_id=purchase_return_id,
                    purchase_invoice_line_id=inp.purchase_invoice_line_id,
                    medicine_id=line["medicine_id"],
                    medicine_name=line["brand_name"],
                    batch_id=batch_id,
                    batch_number=line["batch_number"],
                    expiry_date=line["expiry_date"],
                    return_packs=inp.return_packs or 0,
                    return_units=inp.return_units,
                    purchase_rate_paise=v["unit_rate_paise"],
                    taxable_amount_paise=v["taxable_paise"],
                    gst_percentage=line["gst_percentage"],
                    tax_amount_paise=v["tax_paise"],
                    line_total_paise=v["line_total_paise"],
                    created_at=now_str,
                )
            )

        # Update supplier payable balance
        current_payable = pi["current_payable_paise"]
        new_payable = max(0, current_payable - total_debit_amount_paise)

        cursor.execute("UPDATE suppliers SET current_payable_paise = ? WHERE id = ?;", (new_payable, supplier_id))

        cursor.execute("""
            INSERT INTO supplier_payable_ledger (
                supplier_id, reference_type, reference_id, entry_type, amount_paise, balance_paise, notes, created_at
            ) VALUES (?, 'PURCHASE_RETURN', ?, 'DEBIT', ?, ?, ?, ?);
        """, (
            supplier_id,
            purchase_return_id,
            total_debit_amount_paise,
            new_payable,
            f"Debit Note #{debit_note_number} (Ref: Invoice #{pi['supplier_invoice_number']})",
            now_str,
        ))

        cursor.execute("COMMIT;")
    except HTTPException:
        cursor.execute("ROLLBACK;")
        cursor.close()
        raise
    except Exception as e:
        cursor.execute("ROLLBACK;")
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process purchase return: {e}",
        ) from e

    response_data = PurchaseReturnResponse(
        id=purchase_return_id,
        debit_note_number=debit_note_number,
        purchase_invoice_id=payload.purchase_invoice_id,
        supplier_invoice_number=pi["supplier_invoice_number"],
        supplier_id=supplier_id,
        supplier_name=pi["sup_name"],
        subtotal_taxable_paise=total_taxable_paise,
        total_tax_paise=total_tax_paise,
        total_amount_paise=total_debit_amount_paise,
        reason=payload.reason,
        notes=payload.notes,
        created_by=current_user["id"],
        created_by_name=current_user.get("full_name") or current_user.get("username"),
        created_at=now_str,
        items=result_items,
    )
    return SuccessResponse(data=response_data, message="Purchase return debit note committed successfully.")


# =========================================================================
# 6. PURCHASE RETURNS: LIST & GET DETAILS
# =========================================================================

@router.get("/purchases", response_model=SuccessResponse[PaginatedData[PurchaseReturnResponse]], dependencies=[read_guard])
def list_purchase_returns(
    query: Optional[str] = Query(None, description="Search by debit note number or supplier name"),
    supplier_id: Optional[int] = Query(None, description="Filter by supplier ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: sqlite3.Connection = Depends(get_db),
):
    """List distributor purchase return debit notes with pagination."""
    cursor = db.cursor()
    conditions = []
    params: List[Any] = []

    if supplier_id:
        conditions.append("pr.supplier_id = ?")
        params.append(supplier_id)

    if query:
        conditions.append("(pr.debit_note_number LIKE ? OR s.name LIKE ? OR pi.supplier_invoice_number LIKE ?)")
        wild = f"%{query.strip()}%"
        params.extend([wild, wild, wild])

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    cursor.execute(f"""
        SELECT COUNT(*)
        FROM purchase_returns pr
        JOIN suppliers s ON s.id = pr.supplier_id
        JOIN purchase_invoices pi ON pi.id = pr.purchase_invoice_id
        {where_sql};
    """, params)
    total = cursor.fetchone()[0]

    offset = (page - 1) * page_size
    cursor.execute(f"""
        SELECT pr.*, s.name AS supplier_name, pi.supplier_invoice_number, u.username, u.full_name
        FROM purchase_returns pr
        JOIN suppliers s ON s.id = pr.supplier_id
        JOIN purchase_invoices pi ON pi.id = pr.purchase_invoice_id
        LEFT JOIN users u ON u.id = pr.created_by
        {where_sql}
        ORDER BY pr.created_at DESC, pr.id DESC
        LIMIT ? OFFSET ?;
    """, params + [page_size, offset])
    rows = cursor.fetchall()

    items: List[PurchaseReturnResponse] = []
    for r in rows:
        cursor.execute("""
            SELECT pri.*, m.brand_name, mb.batch_number, mb.expiry_date
            FROM purchase_return_items pri
            JOIN medicines m ON m.id = pri.medicine_id
            JOIN medicine_batches mb ON mb.id = pri.batch_id
            WHERE pri.purchase_return_id = ?
            ORDER BY pri.id ASC;
        """, (r["id"],))
        pri_rows = cursor.fetchall()

        item_list = [
            PurchaseReturnItemResponse(
                id=it["id"],
                purchase_return_id=it["purchase_return_id"],
                purchase_invoice_line_id=it["purchase_invoice_line_id"],
                medicine_id=it["medicine_id"],
                medicine_name=it["brand_name"],
                batch_id=it["batch_id"],
                batch_number=it["batch_number"],
                expiry_date=it["expiry_date"],
                return_packs=it["return_packs"],
                return_units=it["return_units"],
                purchase_rate_paise=it["purchase_rate_paise"],
                taxable_amount_paise=it["taxable_amount_paise"],
                gst_percentage=it["gst_percentage"],
                tax_amount_paise=it["tax_amount_paise"],
                line_total_paise=it["line_total_paise"],
                created_at=it["created_at"],
            )
            for it in pri_rows
        ]

        items.append(
            PurchaseReturnResponse(
                id=r["id"],
                debit_note_number=r["debit_note_number"],
                purchase_invoice_id=r["purchase_invoice_id"],
                supplier_invoice_number=r["supplier_invoice_number"],
                supplier_id=r["supplier_id"],
                supplier_name=r["supplier_name"],
                subtotal_taxable_paise=r["subtotal_taxable_paise"],
                total_tax_paise=r["total_tax_paise"],
                total_amount_paise=r["total_amount_paise"],
                reason=r["reason"],
                notes=r["notes"],
                created_by=r["created_by"],
                created_by_name=r["full_name"] or r["username"],
                created_at=r["created_at"],
                items=item_list,
            )
        )

    cursor.close()
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    return SuccessResponse(data=PaginatedData(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages))
