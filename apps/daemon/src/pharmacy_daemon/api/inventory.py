"""Inventory API: batch lookups, FEFO ordering, Expiry Dashboard, Stock Audits, and Want-Book."""

from datetime import date, datetime, timedelta, timezone
import math
import sqlite3
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from .dependencies import get_current_user, get_db, require_role, require_write_role
from .schemas import (
    BatchAuditDetailsResponse,
    CreateStockAdjustmentRequest,
    CreateWantBookRequest,
    ExpiryBatchResponse,
    ExpiryDashboardData,
    ExpiryDashboardSummaryResponse,
    LowStockMedicineResponse,
    MedicineBatchResponse,
    MedicineStockSummaryResponse,
    PaginatedData,
    StockAdjustmentResponse,
    SuccessResponse,
    SupplierReturnDumpGroupResponse,
    UpdateWantBookStatusRequest,
    WantBookResponse,
)
from ..security.roles import UserRole

router = APIRouter(prefix="/api/v1/inventory", tags=["Inventory & Batches"])

read_guard = Depends(require_role(UserRole.ADMIN, UserRole.PHARMACIST, UserRole.CASHIER))
write_audit_guard = Depends(require_write_role(UserRole.ADMIN, UserRole.PHARMACIST))
write_want_guard = Depends(require_write_role(UserRole.ADMIN, UserRole.PHARMACIST, UserRole.CASHIER))
manage_want_guard = Depends(require_write_role(UserRole.ADMIN, UserRole.PHARMACIST))


# ==========================================
# 1. BATCH SEARCH & FEFO ORDERING (EXISTING)
# ==========================================

@router.get("/batches", response_model=SuccessResponse[PaginatedData[MedicineBatchResponse]], dependencies=[read_guard])
def list_batches(
    medicine_id: Optional[int] = Query(None, description="Filter by medicine ID"),
    query: Optional[str] = Query(None, description="Search by medicine name, salt, or batch number"),
    is_active: Optional[bool] = Query(True, description="Filter by active status"),
    in_stock_only: bool = Query(False, description="Filter only batches with current_quantity > 0"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: sqlite3.Connection = Depends(get_db),
):
    """List batches ordered by FEFO (First Expiring, First Out: earliest expiry date first)."""
    conditions = []
    params = []

    if medicine_id is not None:
        conditions.append("mb.medicine_id = ?")
        params.append(medicine_id)

    if is_active is not None:
        conditions.append("mb.is_active = ?")
        params.append(1 if is_active else 0)

    if in_stock_only:
        conditions.append("mb.current_quantity > 0")

    if query and query.strip():
        term = f"%{query.strip()}%"
        conditions.append("(mb.batch_number LIKE ? OR m.brand_name LIKE ? OR m.generic_salt LIKE ?)")
        params.extend([term, term, term])

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    cursor = db.cursor()
    count_sql = f"""
        SELECT COUNT(*)
        FROM medicine_batches mb
        JOIN medicines m ON m.id = mb.medicine_id
        {where_clause};
    """
    cursor.execute(count_sql, params)
    total = cursor.fetchone()[0]

    offset = (page - 1) * page_size
    list_sql = f"""
        SELECT mb.*, m.brand_name AS medicine_name, m.generic_salt, m.dosage_form
        FROM medicine_batches mb
        JOIN medicines m ON m.id = mb.medicine_id
        {where_clause}
        ORDER BY mb.expiry_date ASC, mb.current_quantity DESC
        LIMIT ? OFFSET ?;
    """
    cursor.execute(list_sql, params + [page_size, offset])
    rows = cursor.fetchall()
    cursor.close()

    items = [
        MedicineBatchResponse(
            id=r["id"],
            medicine_id=r["medicine_id"],
            medicine_name=r["medicine_name"],
            generic_salt=r["generic_salt"],
            dosage_form=r["dosage_form"],
            batch_number=r["batch_number"],
            expiry_date=r["expiry_date"],
            mrp_paise=r["mrp_paise"],
            purchase_rate_paise=r["purchase_rate_paise"],
            pack_size=r["pack_size"],
            current_quantity=r["current_quantity"],
            available_packs=round(r["current_quantity"] / r["pack_size"], 2) if r["pack_size"] > 0 else r["current_quantity"],
            reserved_quantity=r["reserved_quantity"],
            is_active=bool(r["is_active"]),
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
        for r in rows
    ]

    total_pages = math.ceil(total / page_size) if total > 0 else 1
    return SuccessResponse(
        data=PaginatedData(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)
    )


# ==========================================
# 2. AGGREGATED CURRENT STOCK BY MEDICINE (EXISTING)
# ==========================================

@router.get("/stock", response_model=SuccessResponse[PaginatedData[MedicineStockSummaryResponse]], dependencies=[read_guard])
def get_current_stock(
    query: Optional[str] = Query(None, description="Search by brand name or generic salt"),
    dosage_form: Optional[str] = Query(None, description="Filter by dosage form"),
    in_stock_only: bool = Query(False, description="Filter only medicines with positive stock"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: sqlite3.Connection = Depends(get_db),
):
    """Aggregate total stock across active batches for each medicine."""
    conditions = ["m.is_active = 1"]
    params = []

    if dosage_form and dosage_form.strip():
        conditions.append("m.dosage_form = ?")
        params.append(dosage_form.strip().upper())

    if query and query.strip():
        term = f"%{query.strip()}%"
        conditions.append("(m.brand_name LIKE ? OR m.generic_salt LIKE ?)")
        params.extend([term, term])

    where_clause = f"WHERE {' AND '.join(conditions)}"
    having_clause = "HAVING total_stock_units > 0" if in_stock_only else ""

    cursor = db.cursor()
    count_sql = f"""
        SELECT COUNT(*) FROM (
            SELECT m.id, COALESCE(SUM(mb.current_quantity), 0) AS total_stock_units
            FROM medicines m
            LEFT JOIN medicine_batches mb ON mb.medicine_id = m.id AND mb.is_active = 1
            {where_clause}
            GROUP BY m.id
            {having_clause}
        );
    """
    cursor.execute(count_sql, params)
    total = cursor.fetchone()[0]

    offset = (page - 1) * page_size
    stock_sql = f"""
        SELECT
            m.id AS medicine_id,
            m.brand_name,
            m.generic_salt,
            m.dosage_form,
            m.pack_size,
            m.min_stock_units,
            m.rack_location,
            COALESCE(SUM(mb.current_quantity), 0) AS total_stock_units,
            MIN(CASE WHEN mb.current_quantity > 0 THEN mb.expiry_date ELSE NULL END) AS earliest_expiry,
            COUNT(CASE WHEN mb.current_quantity > 0 THEN mb.id ELSE NULL END) AS active_batches_count
        FROM medicines m
        LEFT JOIN medicine_batches mb ON mb.medicine_id = m.id AND mb.is_active = 1
        {where_clause}
        GROUP BY m.id
        {having_clause}
        ORDER BY m.brand_name ASC
        LIMIT ? OFFSET ?;
    """
    cursor.execute(stock_sql, params + [page_size, offset])
    rows = cursor.fetchall()
    cursor.close()

    items = [
        MedicineStockSummaryResponse(
            medicine_id=r["medicine_id"],
            brand_name=r["brand_name"],
            generic_salt=r["generic_salt"],
            dosage_form=r["dosage_form"],
            pack_size=r["pack_size"],
            total_stock_units=r["total_stock_units"],
            total_packs=round(r["total_stock_units"] / r["pack_size"], 2) if r["pack_size"] > 0 else r["total_stock_units"],
            earliest_expiry=r["earliest_expiry"],
            active_batches_count=r["active_batches_count"],
        )
        for r in rows
    ]

    total_pages = math.ceil(total / page_size) if total > 0 else 1
    return SuccessResponse(
        data=PaginatedData(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)
    )


# ==========================================
# 3. EXPIRY DASHBOARD & MANAGEMENT (MILESTONE 4)
# ==========================================

@router.get("/expiry", response_model=SuccessResponse[ExpiryDashboardData], dependencies=[read_guard])
def get_expiry_dashboard(
    filter_type: str = Query("ALL", alias="filter", description="Filter: ALL, EXPIRED, WITHIN_30_DAYS, WITHIN_60_DAYS, WITHIN_90_DAYS, WITHIN_180_DAYS"),
    search: Optional[str] = Query(None, description="Search brand, generic salt, or batch number"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: sqlite3.Connection = Depends(get_db),
):
    """Return batches categorized by expiry thresholds with summary values and FEFO order."""
    today = date.today()
    today_str = today.isoformat()
    d30_str = (today + timedelta(days=30)).isoformat()
    d60_str = (today + timedelta(days=60)).isoformat()
    d90_str = (today + timedelta(days=90)).isoformat()
    d180_str = (today + timedelta(days=180)).isoformat()

    cursor = db.cursor()

    # 1. Calculate overall summary aggregates for batches in stock
    summary_sql = """
        SELECT
            COUNT(CASE WHEN mb.expiry_date <= ? THEN 1 END) AS exp_cnt,
            COALESCE(SUM(CASE WHEN mb.expiry_date <= ? THEN (mb.current_quantity * mb.purchase_rate_paise) / mb.pack_size ELSE 0 END), 0) AS exp_val,

            COUNT(CASE WHEN mb.expiry_date > ? AND mb.expiry_date <= ? THEN 1 END) AS w30_cnt,
            COALESCE(SUM(CASE WHEN mb.expiry_date > ? AND mb.expiry_date <= ? THEN (mb.current_quantity * mb.purchase_rate_paise) / mb.pack_size ELSE 0 END), 0) AS w30_val,

            COUNT(CASE WHEN mb.expiry_date > ? AND mb.expiry_date <= ? THEN 1 END) AS w60_cnt,
            COALESCE(SUM(CASE WHEN mb.expiry_date > ? AND mb.expiry_date <= ? THEN (mb.current_quantity * mb.purchase_rate_paise) / mb.pack_size ELSE 0 END), 0) AS w60_val,

            COUNT(CASE WHEN mb.expiry_date > ? AND mb.expiry_date <= ? THEN 1 END) AS w90_cnt,
            COALESCE(SUM(CASE WHEN mb.expiry_date > ? AND mb.expiry_date <= ? THEN (mb.current_quantity * mb.purchase_rate_paise) / mb.pack_size ELSE 0 END), 0) AS w90_val,

            COUNT(CASE WHEN mb.expiry_date > ? AND mb.expiry_date <= ? THEN 1 END) AS w180_cnt,
            COALESCE(SUM(CASE WHEN mb.expiry_date > ? AND mb.expiry_date <= ? THEN (mb.current_quantity * mb.purchase_rate_paise) / mb.pack_size ELSE 0 END), 0) AS w180_val
        FROM medicine_batches mb
        WHERE mb.is_active = 1 AND mb.current_quantity > 0;
    """
    cursor.execute(summary_sql, (
        today_str, today_str,
        today_str, d30_str, today_str, d30_str,
        d30_str, d60_str, d30_str, d60_str,
        d60_str, d90_str, d60_str, d90_str,
        d90_str, d180_str, d90_str, d180_str,
    ))
    s_row = cursor.fetchone()
    summary = ExpiryDashboardSummaryResponse(
        expired_count=s_row["exp_cnt"],
        expired_value_paise=s_row["exp_val"],
        within_30_count=s_row["w30_cnt"],
        within_30_value_paise=s_row["w30_val"],
        within_60_count=s_row["w60_cnt"],
        within_60_value_paise=s_row["w60_val"],
        within_90_count=s_row["w90_cnt"],
        within_90_value_paise=s_row["w90_val"],
        within_180_count=s_row["w180_cnt"],
        within_180_value_paise=s_row["w180_val"],
        total_at_risk_value_paise=s_row["exp_val"] + s_row["w30_val"] + s_row["w60_val"] + s_row["w90_val"] + s_row["w180_val"],
    )

    # 2. Build list filter conditions
    conditions = ["mb.is_active = 1", "mb.current_quantity > 0"]
    params = []

    f_upper = filter_type.strip().upper()
    if f_upper == "EXPIRED":
        conditions.append("mb.expiry_date <= ?")
        params.append(today_str)
    elif f_upper == "WITHIN_30_DAYS":
        conditions.append("mb.expiry_date > ? AND mb.expiry_date <= ?")
        params.extend([today_str, d30_str])
    elif f_upper == "WITHIN_60_DAYS":
        conditions.append("mb.expiry_date > ? AND mb.expiry_date <= ?")
        params.extend([d30_str, d60_str])
    elif f_upper == "WITHIN_90_DAYS":
        conditions.append("mb.expiry_date > ? AND mb.expiry_date <= ?")
        params.extend([d60_str, d90_str])
    elif f_upper == "WITHIN_180_DAYS":
        conditions.append("mb.expiry_date > ? AND mb.expiry_date <= ?")
        params.extend([d90_str, d180_str])
    elif f_upper == "ALL":
        # Default: all expired or expiring within 180 days
        conditions.append("mb.expiry_date <= ?")
        params.append(d180_str)

    if search and search.strip():
        term = f"%{search.strip()}%"
        conditions.append("(m.brand_name LIKE ? OR m.generic_salt LIKE ? OR mb.batch_number LIKE ?)")
        params.extend([term, term, term])

    where_clause = f"WHERE {' AND '.join(conditions)}"

    count_sql = f"""
        SELECT COUNT(*)
        FROM medicine_batches mb
        JOIN medicines m ON m.id = mb.medicine_id
        {where_clause};
    """
    cursor.execute(count_sql, params)
    total = cursor.fetchone()[0]

    offset = (page - 1) * page_size
    # Join with latest posted supplier for batch
    items_sql = f"""
        SELECT
            mb.id,
            mb.medicine_id,
            m.brand_name AS medicine_name,
            m.generic_salt,
            m.dosage_form,
            m.rack_location,
            mb.batch_number,
            mb.expiry_date,
            mb.pack_size,
            mb.current_quantity,
            mb.purchase_rate_paise,
            mb.mrp_paise,
            sup.supplier_id,
            sup.supplier_name
        FROM medicine_batches mb
        JOIN medicines m ON m.id = mb.medicine_id
        LEFT JOIN (
            SELECT pil.medicine_id, pil.batch_number, pi.supplier_id, s.name AS supplier_name
            FROM purchase_invoice_lines pil
            JOIN purchase_invoices pi ON pi.id = pil.purchase_invoice_id
            JOIN suppliers s ON s.id = pi.supplier_id
            WHERE pi.status = 'POSTED'
            GROUP BY pil.medicine_id, pil.batch_number
        ) sup ON sup.medicine_id = mb.medicine_id AND sup.batch_number = mb.batch_number
        {where_clause}
        ORDER BY mb.expiry_date ASC, mb.current_quantity DESC
        LIMIT ? OFFSET ?;
    """
    cursor.execute(items_sql, params + [page_size, offset])
    rows = cursor.fetchall()
    cursor.close()

    items = []
    for r in rows:
        exp_d = datetime.strptime(r["expiry_date"], "%Y-%m-%d").date()
        days_diff = (exp_d - today).days
        is_exp = exp_d <= today
        est_val = (r["current_quantity"] * r["purchase_rate_paise"]) // max(1, r["pack_size"])
        items.append(
            ExpiryBatchResponse(
                id=r["id"],
                medicine_id=r["medicine_id"],
                medicine_name=r["medicine_name"],
                generic_salt=r["generic_salt"],
                dosage_form=r["dosage_form"],
                batch_number=r["batch_number"],
                expiry_date=r["expiry_date"],
                days_to_expiry=days_diff,
                is_expired=is_exp,
                pack_size=r["pack_size"],
                current_quantity=r["current_quantity"],
                available_packs=round(r["current_quantity"] / r["pack_size"], 2) if r["pack_size"] > 0 else r["current_quantity"],
                purchase_rate_paise=r["purchase_rate_paise"],
                mrp_paise=r["mrp_paise"],
                estimated_stock_value_paise=est_val,
                rack_location=r["rack_location"],
                supplier_id=r["supplier_id"],
                supplier_name=r["supplier_name"],
            )
        )

    total_pages = math.ceil(total / page_size) if total > 0 else 1
    return SuccessResponse(
        data=ExpiryDashboardData(
            summary=summary,
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    )


@router.get("/expiry/return-dump", response_model=SuccessResponse[List[SupplierReturnDumpGroupResponse]], dependencies=[read_guard])
def get_supplier_return_dump(
    days: int = Query(90, ge=0, le=365, description="Include batches expiring within N days or already expired"),
    supplier_id: Optional[int] = Query(None, description="Optional filter by supplier ID"),
    db: sqlite3.Connection = Depends(get_db),
):
    """Group near-expiry and expired stock by supplier for return preparation and debit note processing."""
    today = date.today()
    cutoff_date = today + timedelta(days=days)
    cutoff_str = cutoff_date.isoformat()

    cursor = db.cursor()
    params = [cutoff_str]
    sup_filter = ""
    if supplier_id is not None:
        sup_filter = "AND s.id = ?"
        params.append(supplier_id)

    dump_sql = f"""
        SELECT
            mb.id,
            mb.medicine_id,
            m.brand_name AS medicine_name,
            m.generic_salt,
            m.dosage_form,
            m.rack_location,
            mb.batch_number,
            mb.expiry_date,
            mb.pack_size,
            mb.current_quantity,
            mb.purchase_rate_paise,
            mb.mrp_paise,
            COALESCE(s.id, NULL) AS supplier_id,
            COALESCE(s.name, 'Unassigned Stockist') AS supplier_name,
            s.phone AS supplier_phone,
            s.gstin AS supplier_gstin
        FROM medicine_batches mb
        JOIN medicines m ON m.id = mb.medicine_id
        LEFT JOIN (
            SELECT pil.medicine_id, pil.batch_number, pi.supplier_id
            FROM purchase_invoice_lines pil
            JOIN purchase_invoices pi ON pi.id = pil.purchase_invoice_id
            WHERE pi.status = 'POSTED'
            GROUP BY pil.medicine_id, pil.batch_number
        ) sup_map ON sup_map.medicine_id = mb.medicine_id AND sup_map.batch_number = mb.batch_number
        LEFT JOIN suppliers s ON s.id = sup_map.supplier_id
        WHERE mb.is_active = 1 AND mb.current_quantity > 0 AND mb.expiry_date <= ?
        {sup_filter}
        ORDER BY s.name ASC, mb.expiry_date ASC;
    """
    cursor.execute(dump_sql, params)
    rows = cursor.fetchall()
    cursor.close()

    grouped: dict[tuple, list] = {}
    supplier_meta: dict[tuple, dict] = {}

    for r in rows:
        key = (r["supplier_id"], r["supplier_name"])
        if key not in grouped:
            grouped[key] = []
            supplier_meta[key] = {
                "supplier_id": r["supplier_id"],
                "supplier_name": r["supplier_name"],
                "supplier_phone": r["supplier_phone"],
                "supplier_gstin": r["supplier_gstin"],
            }

        exp_d = datetime.strptime(r["expiry_date"], "%Y-%m-%d").date()
        days_diff = (exp_d - today).days
        is_exp = exp_d <= today
        est_val = (r["current_quantity"] * r["purchase_rate_paise"]) // max(1, r["pack_size"])

        batch_item = ExpiryBatchResponse(
            id=r["id"],
            medicine_id=r["medicine_id"],
            medicine_name=r["medicine_name"],
            generic_salt=r["generic_salt"],
            dosage_form=r["dosage_form"],
            batch_number=r["batch_number"],
            expiry_date=r["expiry_date"],
            days_to_expiry=days_diff,
            is_expired=is_exp,
            pack_size=r["pack_size"],
            current_quantity=r["current_quantity"],
            available_packs=round(r["current_quantity"] / r["pack_size"], 2) if r["pack_size"] > 0 else r["current_quantity"],
            purchase_rate_paise=r["purchase_rate_paise"],
            mrp_paise=r["mrp_paise"],
            estimated_stock_value_paise=est_val,
            rack_location=r["rack_location"],
            supplier_id=r["supplier_id"],
            supplier_name=r["supplier_name"],
        )
        grouped[key].append(batch_item)

    result = []
    for key, batch_list in grouped.items():
        meta = supplier_meta[key]
        total_units = sum(b.current_quantity for b in batch_list)
        total_val = sum(b.estimated_stock_value_paise for b in batch_list)
        result.append(
            SupplierReturnDumpGroupResponse(
                supplier_id=meta["supplier_id"],
                supplier_name=meta["supplier_name"],
                supplier_phone=meta["supplier_phone"],
                supplier_gstin=meta["supplier_gstin"],
                total_batches=len(batch_list),
                total_units=total_units,
                total_value_paise=total_val,
                batches=batch_list,
            )
        )

    return SuccessResponse(data=result)


# ==========================================
# 4. PHYSICAL STOCK AUDIT (MILESTONE 4)
# ==========================================

@router.get("/audits", response_model=SuccessResponse[PaginatedData[StockAdjustmentResponse]], dependencies=[read_guard])
def list_stock_audits(
    search: Optional[str] = Query(None, description="Search medicine, batch, or adjustment number"),
    reason: Optional[str] = Query(None, description="Filter by reason (BREAKAGE, THEFT, AUDIT_CORRECTION, EXPIRED_SCRAP)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: sqlite3.Connection = Depends(get_db),
):
    """Retrieve immutable stock audit adjustments ledger."""
    conditions = []
    params = []

    if reason and reason.strip():
        conditions.append("sa.reason = ?")
        params.append(reason.strip().upper())

    if search and search.strip():
        term = f"%{search.strip()}%"
        conditions.append("(sa.adjustment_number LIKE ? OR m.brand_name LIKE ? OR mb.batch_number LIKE ?)")
        params.extend([term, term, term])

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    cursor = db.cursor()
    count_sql = f"""
        SELECT COUNT(*)
        FROM stock_adjustments sa
        JOIN medicine_batches mb ON mb.id = sa.batch_id
        JOIN medicines m ON m.id = sa.medicine_id
        {where_clause};
    """
    cursor.execute(count_sql, params)
    total = cursor.fetchone()[0]

    offset = (page - 1) * page_size
    list_sql = f"""
        SELECT
            sa.*,
            m.brand_name AS medicine_name,
            m.generic_salt,
            m.dosage_form,
            mb.batch_number,
            mb.expiry_date,
            mb.pack_size,
            u.full_name AS username
        FROM stock_adjustments sa
        JOIN medicine_batches mb ON mb.id = sa.batch_id
        JOIN medicines m ON m.id = sa.medicine_id
        LEFT JOIN users u ON u.id = sa.user_id
        {where_clause}
        ORDER BY sa.created_at DESC, sa.id DESC
        LIMIT ? OFFSET ?;
    """
    cursor.execute(list_sql, params + [page_size, offset])
    rows = cursor.fetchall()
    cursor.close()

    items = [
        StockAdjustmentResponse(
            id=r["id"],
            adjustment_number=r["adjustment_number"],
            batch_id=r["batch_id"],
            medicine_id=r["medicine_id"],
            medicine_name=r["medicine_name"],
            generic_salt=r["generic_salt"],
            dosage_form=r["dosage_form"],
            batch_number=r["batch_number"],
            expiry_date=r["expiry_date"],
            pack_size=r["pack_size"],
            system_quantity=r["system_quantity"],
            physical_quantity=r["physical_quantity"],
            delta_quantity=r["delta_quantity"],
            reason=r["reason"],
            estimated_loss_paise=r["estimated_loss_paise"],
            notes=r["notes"],
            user_id=r["user_id"],
            username=r["username"],
            created_at=r["created_at"],
        )
        for r in rows
    ]

    total_pages = math.ceil(total / page_size) if total > 0 else 1
    return SuccessResponse(
        data=PaginatedData(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)
    )


@router.get("/audits/batch/{batch_id}", response_model=SuccessResponse[BatchAuditDetailsResponse], dependencies=[read_guard])
def get_batch_audit_details(
    batch_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    """Retrieve current system quantity and metadata for batch physical counting."""
    cursor = db.cursor()
    cursor.execute("""
        SELECT
            mb.id AS batch_id,
            mb.medicine_id,
            m.brand_name AS medicine_name,
            m.generic_salt,
            m.dosage_form,
            m.rack_location,
            mb.batch_number,
            mb.expiry_date,
            mb.pack_size,
            mb.current_quantity,
            mb.purchase_rate_paise,
            mb.mrp_paise
        FROM medicine_batches mb
        JOIN medicines m ON m.id = mb.medicine_id
        WHERE mb.id = ?;
    """, (batch_id,))
    row = cursor.fetchone()
    cursor.close()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch #{batch_id} not found.",
        )

    return SuccessResponse(
        data=BatchAuditDetailsResponse(
            batch_id=row["batch_id"],
            medicine_id=row["medicine_id"],
            medicine_name=row["medicine_name"],
            generic_salt=row["generic_salt"],
            dosage_form=row["dosage_form"],
            batch_number=row["batch_number"],
            expiry_date=row["expiry_date"],
            pack_size=row["pack_size"],
            current_quantity=row["current_quantity"],
            purchase_rate_paise=row["purchase_rate_paise"],
            mrp_paise=row["mrp_paise"],
            rack_location=row["rack_location"],
        )
    )


@router.post("/audits", response_model=SuccessResponse[StockAdjustmentResponse], status_code=status.HTTP_201_CREATED, dependencies=[write_audit_guard])
def submit_stock_audit(
    payload: CreateStockAdjustmentRequest,
    current_user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Submit a physical count adjustment with atomic ledger update and validation."""
    valid_reasons = {"BREAKAGE", "THEFT", "AUDIT_CORRECTION", "EXPIRED_SCRAP"}
    if payload.reason not in valid_reasons:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid reason '{payload.reason}'. Must be one of: {sorted(valid_reasons)}",
        )

    if payload.physical_quantity < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Physical stock quantity cannot be negative.",
        )

    cursor = db.cursor()
    cursor.execute("BEGIN IMMEDIATE;")
    try:
        # 1. Fetch current batch under write lock
        cursor.execute("""
            SELECT
                mb.id,
                mb.medicine_id,
                mb.batch_number,
                mb.expiry_date,
                mb.pack_size,
                mb.current_quantity,
                mb.purchase_rate_paise,
                mb.mrp_paise,
                m.brand_name AS medicine_name,
                m.generic_salt,
                m.dosage_form
            FROM medicine_batches mb
            JOIN medicines m ON m.id = mb.medicine_id
            WHERE mb.id = ?;
        """, (payload.batch_id,))
        batch = cursor.fetchone()

        if not batch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Batch #{payload.batch_id} not found.",
            )

        system_qty = batch["current_quantity"]
        physical_qty = payload.physical_quantity
        delta_qty = physical_qty - system_qty

        # Require explanatory notes for any negative adjustment or scrap
        if delta_qty < 0 or payload.reason in ("BREAKAGE", "THEFT", "EXPIRED_SCRAP"):
            if not payload.notes or not payload.notes.strip():
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Notes are mandatory for negative stock adjustment / {payload.reason}.",
                )

        if delta_qty == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Physical quantity matches current system quantity (delta = 0). No adjustment needed.",
            )

        # Estimate loss in integer paise (only for stock loss)
        loss_paise = 0
        if delta_qty < 0:
            loss_paise = (abs(delta_qty) * batch["purchase_rate_paise"]) // max(1, batch["pack_size"])

        # Generate sequence adjustment number: ADJ-YYYYMMDD-XXXX
        now_dt = datetime.now(timezone.utc)
        today_date_str = now_dt.strftime("%Y%m%d")
        prefix = f"ADJ-{today_date_str}"
        cursor.execute(
            "SELECT COUNT(*) FROM stock_adjustments WHERE adjustment_number LIKE ?;",
            (f"{prefix}-%",),
        )
        seq = cursor.fetchone()[0] + 1
        adj_number = f"{prefix}-{seq:04d}"
        now_str = now_dt.isoformat()

        # 2. Insert stock_adjustments record
        cursor.execute("""
            INSERT INTO stock_adjustments (
                adjustment_number, batch_id, medicine_id, system_quantity, physical_quantity,
                delta_quantity, reason, estimated_loss_paise, notes, user_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            adj_number,
            batch["id"],
            batch["medicine_id"],
            system_qty,
            physical_qty,
            delta_qty,
            payload.reason,
            loss_paise,
            payload.notes.strip() if payload.notes else None,
            current_user["id"],
            now_str,
        ))
        adj_id = cursor.lastrowid

        # 3. Update medicine_batches current_quantity
        cursor.execute("""
            UPDATE medicine_batches
            SET current_quantity = ?, updated_at = ?
            WHERE id = ?;
        """, (physical_qty, now_str, batch["id"]))

        # 4. Insert into inventory_ledger
        cursor.execute("""
            INSERT INTO inventory_ledger (
                medicine_id, batch_id, transaction_type, quantity_change, quantity_balance,
                reference_type, reference_id, notes, user_id, created_at
            ) VALUES (?, ?, 'ADJUSTMENT', ?, ?, 'STOCK_ADJUSTMENT', ?, ?, ?, ?);
        """, (
            batch["medicine_id"],
            batch["id"],
            delta_qty,
            physical_qty,
            adj_id,
            f"Audit ({payload.reason}): {payload.notes.strip() if payload.notes else ''}",
            current_user["id"],
            now_str,
        ))

        cursor.execute("COMMIT;")
    except HTTPException:
        db.execute("ROLLBACK;")
        raise
    except Exception as e:
        db.execute("ROLLBACK;")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stock adjustment failed: {e}",
        ) from e
    finally:
        cursor.close()

    return SuccessResponse(
        data=StockAdjustmentResponse(
            id=adj_id,
            adjustment_number=adj_number,
            batch_id=batch["id"],
            medicine_id=batch["medicine_id"],
            medicine_name=batch["medicine_name"],
            generic_salt=batch["generic_salt"],
            dosage_form=batch["dosage_form"],
            batch_number=batch["batch_number"],
            expiry_date=batch["expiry_date"],
            pack_size=batch["pack_size"],
            system_quantity=system_qty,
            physical_quantity=physical_qty,
            delta_quantity=delta_qty,
            reason=payload.reason,
            estimated_loss_paise=loss_paise,
            notes=payload.notes,
            user_id=current_user["id"],
            username=current_user.get("full_name"),
            created_at=now_str,
        ),
        message=f"Stock adjusted by {delta_qty:+d} units ({payload.reason}). Inventory ledger updated.",
    )


# ==========================================
# 5. WANT-BOOK & REORDER WORKFLOW (MILESTONE 4)
# ==========================================

@router.get("/want-book/low-stock", response_model=SuccessResponse[List[LowStockMedicineResponse]], dependencies=[read_guard])
def list_low_stock_medicines(
    search: Optional[str] = Query(None, description="Search by brand name or generic salt"),
    limit: int = Query(100, ge=1, le=500),
    db: sqlite3.Connection = Depends(get_db),
):
    """Automatically identify active medicines whose total non-expired stock is <= min_stock_units."""
    today_str = date.today().isoformat()
    conditions = ["m.is_active = 1"]
    params = [today_str]

    if search and search.strip():
        term = f"%{search.strip()}%"
        conditions.append("(m.brand_name LIKE ? OR m.generic_salt LIKE ?)")
        params.extend([term, term])

    where_clause = f"WHERE {' AND '.join(conditions)}"

    cursor = db.cursor()
    # Find active medicines where non-expired stock <= min_stock_units
    low_sql = f"""
        SELECT
            m.id AS medicine_id,
            m.brand_name,
            m.generic_salt,
            m.dosage_form,
            m.pack_size,
            m.min_stock_units,
            m.rack_location,
            COALESCE(SUM(CASE WHEN mb.is_active = 1 AND mb.expiry_date > ? THEN mb.current_quantity ELSE 0 END), 0) AS current_stock_units,
            pref_sup.supplier_id AS preferred_supplier_id,
            pref_sup.supplier_name AS preferred_supplier_name
        FROM medicines m
        LEFT JOIN medicine_batches mb ON mb.medicine_id = m.id
        LEFT JOIN (
            SELECT pil.medicine_id, pi.supplier_id, s.name AS supplier_name
            FROM purchase_invoice_lines pil
            JOIN purchase_invoices pi ON pi.id = pil.purchase_invoice_id
            JOIN suppliers s ON s.id = pi.supplier_id
            WHERE pi.status = 'POSTED'
            GROUP BY pil.medicine_id
        ) pref_sup ON pref_sup.medicine_id = m.id
        {where_clause}
        GROUP BY m.id
        HAVING current_stock_units <= m.min_stock_units
        ORDER BY (m.min_stock_units - current_stock_units) DESC, m.brand_name ASC
        LIMIT ?;
    """
    params.append(limit)
    cursor.execute(low_sql, params)
    rows = cursor.fetchall()
    cursor.close()

    items = []
    for r in rows:
        c_units = r["current_stock_units"]
        min_u = r["min_stock_units"]
        ps = max(1, r["pack_size"])
        shortfall = max(0, min_u - c_units)
        # Suggest enough packs to cover shortfall plus one replenishment threshold
        suggested_units = shortfall + min_u
        suggested_packs = max(1, math.ceil(suggested_units / ps))

        items.append(
            LowStockMedicineResponse(
                medicine_id=r["medicine_id"],
                brand_name=r["brand_name"],
                generic_salt=r["generic_salt"],
                dosage_form=r["dosage_form"],
                pack_size=r["pack_size"],
                min_stock_units=min_u,
                current_stock_units=c_units,
                current_packs=round(c_units / ps, 2),
                suggested_reorder_packs=suggested_packs,
                rack_location=r["rack_location"],
                preferred_supplier_id=r["preferred_supplier_id"],
                preferred_supplier_name=r["preferred_supplier_name"],
            )
        )

    return SuccessResponse(data=items)


@router.get("/want-book", response_model=SuccessResponse[PaginatedData[WantBookResponse]], dependencies=[read_guard])
def list_want_book(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (PENDING, ORDERED, RECEIVED)"),
    search: Optional[str] = Query(None, description="Search brand name, generic salt, or supplier"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: sqlite3.Connection = Depends(get_db),
):
    """List procurement want-book reorder items."""
    conditions = []
    params = []

    if status_filter and status_filter.strip():
        conditions.append("wb.status = ?")
        params.append(status_filter.strip().upper())

    if search and search.strip():
        term = f"%{search.strip()}%"
        conditions.append("(m.brand_name LIKE ? OR m.generic_salt LIKE ? OR s.name LIKE ?)")
        params.extend([term, term, term])

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    cursor = db.cursor()
    count_sql = f"""
        SELECT COUNT(*)
        FROM want_book wb
        JOIN medicines m ON m.id = wb.medicine_id
        LEFT JOIN suppliers s ON s.id = wb.supplier_id
        {where_clause};
    """
    cursor.execute(count_sql, params)
    total = cursor.fetchone()[0]

    offset = (page - 1) * page_size
    list_sql = f"""
        SELECT
            wb.*,
            m.brand_name AS medicine_name,
            m.generic_salt,
            m.dosage_form,
            m.pack_size,
            s.name AS supplier_name,
            u.full_name AS requested_by_name
        FROM want_book wb
        JOIN medicines m ON m.id = wb.medicine_id
        LEFT JOIN suppliers s ON s.id = wb.supplier_id
        LEFT JOIN users u ON u.id = wb.requested_by
        {where_clause}
        ORDER BY
            CASE wb.status WHEN 'PENDING' THEN 1 WHEN 'ORDERED' THEN 2 ELSE 3 END ASC,
            wb.created_at DESC
        LIMIT ? OFFSET ?;
    """
    cursor.execute(list_sql, params + [page_size, offset])
    rows = cursor.fetchall()
    cursor.close()

    items = [
        WantBookResponse(
            id=r["id"],
            medicine_id=r["medicine_id"],
            medicine_name=r["medicine_name"],
            generic_salt=r["generic_salt"],
            dosage_form=r["dosage_form"],
            pack_size=r["pack_size"],
            requested_quantity_packs=r["requested_quantity_packs"],
            current_stock_units=r["current_stock_units"],
            min_stock_units=r["min_stock_units"],
            status=r["status"],
            supplier_id=r["supplier_id"],
            supplier_name=r["supplier_name"],
            notes=r["notes"],
            requested_by=r["requested_by"],
            requested_by_name=r["requested_by_name"],
            ordered_at=r["ordered_at"],
            received_at=r["received_at"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
        for r in rows
    ]

    total_pages = math.ceil(total / page_size) if total > 0 else 1
    return SuccessResponse(
        data=PaginatedData(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)
    )


@router.post("/want-book", response_model=SuccessResponse[WantBookResponse], status_code=status.HTTP_201_CREATED, dependencies=[write_want_guard])
def create_want_book_item(
    payload: CreateWantBookRequest,
    current_user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Add a medicine to the procurement want-book (accessible from billing via Ctrl+W)."""
    cursor = db.cursor()
    cursor.execute("""
        SELECT id, brand_name, generic_salt, dosage_form, pack_size, min_stock_units, is_active
        FROM medicines WHERE id = ?;
    """, (payload.medicine_id,))
    med = cursor.fetchone()

    if not med:
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medicine #{payload.medicine_id} not found.",
        )

    # Compute current active non-expired stock
    today_str = date.today().isoformat()
    cursor.execute("""
        SELECT COALESCE(SUM(current_quantity), 0)
        FROM medicine_batches
        WHERE medicine_id = ? AND is_active = 1 AND expiry_date > ?;
    """, (payload.medicine_id, today_str))
    current_stock = cursor.fetchone()[0]

    # Verify supplier if provided
    supplier_name = None
    if payload.supplier_id:
        cursor.execute("SELECT name FROM suppliers WHERE id = ?;", (payload.supplier_id,))
        sup = cursor.fetchone()
        if not sup:
            cursor.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supplier #{payload.supplier_id} not found.",
            )
        supplier_name = sup["name"]

    now_str = datetime.now(timezone.utc).isoformat()
    cursor.execute("""
        INSERT INTO want_book (
            medicine_id, requested_quantity_packs, current_stock_units, min_stock_units,
            status, supplier_id, notes, requested_by, created_at, updated_at
        ) VALUES (?, ?, ?, ?, 'PENDING', ?, ?, ?, ?, ?);
    """, (
        payload.medicine_id,
        payload.requested_quantity_packs,
        current_stock,
        med["min_stock_units"],
        payload.supplier_id,
        payload.notes.strip() if payload.notes else None,
        current_user["id"],
        now_str,
        now_str,
    ))
    wb_id = cursor.lastrowid
    db.commit()
    cursor.close()

    return SuccessResponse(
        data=WantBookResponse(
            id=wb_id,
            medicine_id=med["id"],
            medicine_name=med["brand_name"],
            generic_salt=med["generic_salt"],
            dosage_form=med["dosage_form"],
            pack_size=med["pack_size"],
            requested_quantity_packs=payload.requested_quantity_packs,
            current_stock_units=current_stock,
            min_stock_units=med["min_stock_units"],
            status="PENDING",
            supplier_id=payload.supplier_id,
            supplier_name=supplier_name,
            notes=payload.notes,
            requested_by=current_user["id"],
            requested_by_name=current_user.get("full_name"),
            created_at=now_str,
            updated_at=now_str,
        ),
        message=f"Added '{med['brand_name']}' ({payload.requested_quantity_packs} packs) to Want-Book.",
    )


@router.patch("/want-book/{id}/status", response_model=SuccessResponse[WantBookResponse], dependencies=[manage_want_guard])
def update_want_book_status(
    id: int,
    payload: UpdateWantBookStatusRequest,
    db: sqlite3.Connection = Depends(get_db),
):
    """Update status of a want-book item (PENDING -> ORDERED -> RECEIVED)."""
    valid_statuses = {"PENDING", "ORDERED", "RECEIVED"}
    if payload.status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status '{payload.status}'. Must be one of: {sorted(valid_statuses)}",
        )

    cursor = db.cursor()
    cursor.execute("SELECT * FROM want_book WHERE id = ?;", (id,))
    wb = cursor.fetchone()

    if not wb:
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Want-Book item #{id} not found.",
        )

    now_str = datetime.now(timezone.utc).isoformat()
    ordered_at = wb["ordered_at"]
    received_at = wb["received_at"]

    if payload.status == "ORDERED" and not ordered_at:
        ordered_at = now_str
    elif payload.status == "RECEIVED":
        if not ordered_at:
            ordered_at = now_str
        if not received_at:
            received_at = now_str

    notes = payload.notes if payload.notes is not None else wb["notes"]

    cursor.execute("""
        UPDATE want_book
        SET status = ?, notes = ?, ordered_at = ?, received_at = ?, updated_at = ?
        WHERE id = ?;
    """, (payload.status, notes, ordered_at, received_at, now_str, id))
    db.commit()

    # Re-fetch item with joined details
    cursor.execute("""
        SELECT
            wb.*,
            m.brand_name AS medicine_name,
            m.generic_salt,
            m.dosage_form,
            m.pack_size,
            s.name AS supplier_name,
            u.full_name AS requested_by_name
        FROM want_book wb
        JOIN medicines m ON m.id = wb.medicine_id
        LEFT JOIN suppliers s ON s.id = wb.supplier_id
        LEFT JOIN users u ON u.id = wb.requested_by
        WHERE wb.id = ?;
    """, (id,))
    r = cursor.fetchone()
    cursor.close()

    return SuccessResponse(
        data=WantBookResponse(
            id=r["id"],
            medicine_id=r["medicine_id"],
            medicine_name=r["medicine_name"],
            generic_salt=r["generic_salt"],
            dosage_form=r["dosage_form"],
            pack_size=r["pack_size"],
            requested_quantity_packs=r["requested_quantity_packs"],
            current_stock_units=r["current_stock_units"],
            min_stock_units=r["min_stock_units"],
            status=r["status"],
            supplier_id=r["supplier_id"],
            supplier_name=r["supplier_name"],
            notes=r["notes"],
            requested_by=r["requested_by"],
            requested_by_name=r["requested_by_name"],
            ordered_at=r["ordered_at"],
            received_at=r["received_at"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        ),
        message=f"Want-Book item #{id} updated to '{payload.status}'.",
    )


@router.delete("/want-book/{id}", response_model=SuccessResponse[dict], dependencies=[manage_want_guard])
def delete_want_book_item(
    id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    """Remove an item from the want-book."""
    cursor = db.cursor()
    cursor.execute("SELECT id, status FROM want_book WHERE id = ?;", (id,))
    row = cursor.fetchone()

    if not row:
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Want-Book item #{id} not found.",
        )

    cursor.execute("DELETE FROM want_book WHERE id = ?;", (id,))
    db.commit()
    cursor.close()

    return SuccessResponse(
        data={"deleted_id": id},
        message=f"Want-Book item #{id} removed successfully.",
    )
