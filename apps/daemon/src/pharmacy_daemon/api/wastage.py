"""Wastage, damage, breakage, and expired stock write-off router."""

from datetime import datetime, timezone
import math
import sqlite3
from typing import Any, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..security.roles import UserRole
from .dependencies import get_db, get_current_user, require_role, require_write_role
from .schemas import (
    PaginatedData,
    SuccessResponse,
    WastageCreateRequest,
    WastageRecordResponse,
)

router = APIRouter(prefix="/api/v1/inventory/wastage", tags=["Wastage & Breakage Register"])

read_guard = Depends(require_role(UserRole.ADMIN, UserRole.PHARMACIST, UserRole.CASHIER))
write_guard = Depends(require_write_role(UserRole.ADMIN, UserRole.PHARMACIST))


@router.post("", response_model=SuccessResponse[WastageRecordResponse], status_code=status.HTTP_201_CREATED, dependencies=[write_guard])
def record_stock_wastage(
    payload: WastageCreateRequest,
    db: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Record batch stock write-off due to expiry, breakage, or damage, deducting inventory atomically."""
    if payload.quantity_units <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Quantity units to write off must be strictly greater than zero.",
        )

    now = datetime.now(timezone.utc)
    now_str = now.isoformat()
    date_code = now.strftime("%Y%m%d")
    unique_suffix = uuid.uuid4().hex[:6].upper()
    reference_no = f"WST-{date_code}-{unique_suffix}"

    cursor = db.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE;")

        cursor.execute("""
            SELECT mb.*, m.brand_name
            FROM medicine_batches mb
            JOIN medicines m ON m.id = mb.medicine_id
            WHERE mb.id = ?;
        """, (payload.batch_id,))
        batch = cursor.fetchone()

        if not batch:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Batch #{payload.batch_id} not found.")

        current_qty = batch["current_quantity"]
        if current_qty < payload.quantity_units:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Cannot write off {payload.quantity_units} units. Current batch stock is only {current_qty} units. Stock cannot be negative.",
            )

        pack_size = batch["pack_size"]
        ptr_paise = batch["purchase_rate_paise"]
        unit_cost = ptr_paise // pack_size if pack_size > 0 else ptr_paise
        cost_impact_paise = unit_cost * payload.quantity_units

        # Deduct batch stock
        new_qty = current_qty - payload.quantity_units
        cursor.execute("""
            UPDATE medicine_batches
            SET current_quantity = ?, updated_at = ?
            WHERE id = ?;
        """, (new_qty, now_str, payload.batch_id))

        # Insert wastage record
        cursor.execute("""
            INSERT INTO wastage_register (
                reference_no, batch_id, medicine_id, quantity_units, reason,
                cost_impact_paise, notes, reference_type, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'MANUAL_WRITE_OFF', ?, ?);
        """, (
            reference_no,
            payload.batch_id,
            batch["medicine_id"],
            payload.quantity_units,
            payload.reason,
            cost_impact_paise,
            payload.notes.strip() if payload.notes else None,
            current_user["id"],
            now_str,
        ))
        wastage_id = cursor.lastrowid

        # Insert inventory_ledger entry
        cursor.execute("""
            INSERT INTO inventory_ledger (
                medicine_id, batch_id, transaction_type, quantity_change, quantity_balance,
                reference_type, reference_id, notes, user_id, created_at
            ) VALUES (?, ?, 'ADJUSTMENT', ?, ?, 'WASTAGE', ?, ?, ?, ?);
        """, (
            batch["medicine_id"],
            payload.batch_id,
            -payload.quantity_units,
            new_qty,
            wastage_id,
            f"Wastage write-off #{reference_no} ({payload.reason})",
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
            detail=f"Failed to record wastage write-off: {e}",
        ) from e

    record = WastageRecordResponse(
        id=wastage_id,
        reference_no=reference_no,
        batch_id=payload.batch_id,
        medicine_id=batch["medicine_id"],
        medicine_name=batch["brand_name"],
        batch_number=batch["batch_number"],
        expiry_date=batch["expiry_date"],
        quantity_units=payload.quantity_units,
        pack_size=pack_size,
        reason=payload.reason,
        cost_impact_paise=cost_impact_paise,
        notes=payload.notes,
        reference_type="MANUAL_WRITE_OFF",
        reference_id=None,
        created_by=current_user["id"],
        created_by_name=current_user.get("full_name") or current_user.get("username"),
        created_at=now_str,
    )
    return SuccessResponse(data=record, message="Wastage write-off recorded successfully.")


@router.get("", response_model=SuccessResponse[PaginatedData[WastageRecordResponse]], dependencies=[read_guard])
def list_wastage_records(
    reason: Optional[str] = Query(None, description="Filter by wastage reason"),
    query: Optional[str] = Query(None, description="Search by medicine, batch, or reference"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: sqlite3.Connection = Depends(get_db),
):
    """List recorded wastage and breakage write-offs with pagination."""
    cursor = db.cursor()
    conditions = []
    params: List[Any] = []

    if reason:
        conditions.append("w.reason = ?")
        params.append(reason.upper())

    if query:
        conditions.append("(w.reference_no LIKE ? OR m.brand_name LIKE ? OR mb.batch_number LIKE ?)")
        wild = f"%{query.strip()}%"
        params.extend([wild, wild, wild])

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    cursor.execute(f"""
        SELECT COUNT(*)
        FROM wastage_register w
        JOIN medicines m ON m.id = w.medicine_id
        JOIN medicine_batches mb ON mb.id = w.batch_id
        {where_sql};
    """, params)
    total = cursor.fetchone()[0]

    offset = (page - 1) * page_size
    cursor.execute(f"""
        SELECT w.*, m.brand_name, mb.batch_number, mb.expiry_date, mb.pack_size, u.username, u.full_name
        FROM wastage_register w
        JOIN medicines m ON m.id = w.medicine_id
        JOIN medicine_batches mb ON mb.id = w.batch_id
        LEFT JOIN users u ON u.id = w.created_by
        {where_sql}
        ORDER BY w.created_at DESC, w.id DESC
        LIMIT ? OFFSET ?;
    """, params + [page_size, offset])
    rows = cursor.fetchall()
    cursor.close()

    items = [
        WastageRecordResponse(
            id=r["id"],
            reference_no=r["reference_no"],
            batch_id=r["batch_id"],
            medicine_id=r["medicine_id"],
            medicine_name=r["brand_name"],
            batch_number=r["batch_number"],
            expiry_date=r["expiry_date"],
            quantity_units=r["quantity_units"],
            pack_size=r["pack_size"],
            reason=r["reason"],
            cost_impact_paise=r["cost_impact_paise"],
            notes=r["notes"],
            reference_type=r["reference_type"],
            reference_id=r["reference_id"],
            created_by=r["created_by"],
            created_by_name=r["full_name"] or r["username"],
            created_at=r["created_at"],
        )
        for r in rows
    ]

    total_pages = math.ceil(total / page_size) if total > 0 else 1
    return SuccessResponse(data=PaginatedData(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages))
