"""Staff order management, workflow progression, and pharmacist verification."""

import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from portal_service.db.models import (
    Order,
    OrderStatusEnum,
    OrderStatusHistory,
    PortalAuditLog,
    PortalStaffUser,
    StaffRole,
)
from portal_service.db.session import get_db
from portal_service.security.dependencies import get_current_staff
from portal_service.api.customer_orders import format_order_response
from portal_service.schemas import OrderResponse, UpdateOrderStatusRequest

router = APIRouter(prefix="/staff/orders", tags=["Staff Orders"])


@router.get("", response_model=List[OrderResponse])
def list_staff_orders(
    status_filter: Optional[str] = Query(None, description="Filter by OrderStatus"),
    search: Optional[str] = Query(None, description="Search by order number, customer name, phone, or email"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_staff: PortalStaffUser = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    """Retrieve orders with status and search filters for staff management."""
    query = db.query(Order)

    if status_filter:
        query = query.filter(Order.status == status_filter)

    if search:
        st = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Order.order_number.ilike(st),
                Order.customer_name.ilike(st),
                Order.customer_phone.ilike(st),
                Order.customer_email.ilike(st),
            )
        )

    orders = query.order_by(Order.created_at.desc()).offset(offset).limit(limit).all()
    return [format_order_response(o) for o in orders]


@router.get("/{order_id}", response_model=OrderResponse)
def get_order_by_id(
    order_id: str,
    current_staff: PortalStaffUser = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    """Retrieve complete order details by ID for staff processing."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order ID '{order_id}' was not found.",
        )
    return format_order_response(order)


@router.put("/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: str,
    payload: UpdateOrderStatusRequest,
    current_staff: PortalStaffUser = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    """Update order status with pharmacist review validation and audit trail."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order ID '{order_id}' was not found.",
        )

    # Validate valid target status
    valid_statuses = [e.value for e in OrderStatusEnum]
    if payload.status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid order status '{payload.status}'. Allowed values: {valid_statuses}",
        )

    # Safety check: Prescription item approval from PHARMACIST_REVIEW
    if order.status == OrderStatusEnum.PHARMACIST_REVIEW.value and payload.status in [
        OrderStatusEnum.CONFIRMED.value,
        OrderStatusEnum.PREPARING.value,
        OrderStatusEnum.READY_FOR_PICKUP.value,
    ]:
        if current_staff.role not in [StaffRole.ADMIN.value, StaffRole.PHARMACIST.value]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Prescription approval requires a Registered Pharmacist or Admin role.",
            )

    prev_status = order.status
    order.status = payload.status

    if payload.pharmacist_notes:
        order.pharmacist_notes = payload.pharmacist_notes.strip()

    if payload.rejection_reason:
        order.rejection_reason = payload.rejection_reason.strip()

    # Append to OrderStatusHistory
    history_note = payload.notes or f"Status changed to {payload.status}"
    if payload.pharmacist_notes:
        history_note += f" | Pharmacist Note: {payload.pharmacist_notes}"
    if payload.rejection_reason:
        history_note += f" | Rejection Reason: {payload.rejection_reason}"

    history_entry = OrderStatusHistory(
        order_id=order.id,
        from_status=prev_status,
        to_status=payload.status,
        changed_by_type="STAFF",
        changed_by_name=f"{current_staff.full_name} ({current_staff.role})",
        notes=history_note,
    )
    db.add(history_entry)

    # Record Audit Log
    audit_entry = PortalAuditLog(
        staff_user_id=current_staff.id,
        staff_email=current_staff.email,
        action="ORDER_STATUS_CHANGED",
        entity_type="ORDER",
        entity_id=order.id,
        details_json=json.dumps(
            {
                "order_number": order.order_number,
                "from_status": prev_status,
                "to_status": payload.status,
                "notes": history_note,
            }
        ),
    )
    db.add(audit_entry)

    db.commit()
    db.refresh(order)

    return format_order_response(order)
