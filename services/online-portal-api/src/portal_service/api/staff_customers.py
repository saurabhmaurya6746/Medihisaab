"""Staff customer lookup for operational support."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from portal_service.db.models import Customer, Order, PortalStaffUser
from portal_service.db.session import get_db
from portal_service.security.dependencies import get_current_staff
from portal_service.schemas import OperationalCustomerLookup

router = APIRouter(prefix="/staff/customers", tags=["Staff Customers"])


@router.get("", response_model=List[OperationalCustomerLookup])
def lookup_customers(
    search: Optional[str] = Query(None, description="Search by name, phone number, or email"),
    limit: int = Query(50, ge=1, le=100),
    current_staff: PortalStaffUser = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    """Search registered customers for phone inquiries and order lookups."""
    query = (
        db.query(
            Customer,
            func.count(Order.id).label("orders_count"),
            func.max(Order.created_at).label("last_order_date"),
        )
        .outerjoin(Order, Order.customer_id == Customer.id)
        .group_by(Customer.id)
    )

    if search:
        st = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Customer.full_name.ilike(st),
                Customer.phone.ilike(st),
                Customer.email.ilike(st),
            )
        )

    results = query.order_by(Customer.created_at.desc()).limit(limit).all()

    response = []
    for customer, ord_count, last_date in results:
        response.append(
            OperationalCustomerLookup(
                id=customer.id,
                email=customer.email,
                full_name=customer.full_name,
                phone=customer.phone,
                delivery_address=customer.delivery_address,
                orders_count=ord_count,
                last_order_date=last_date,
                created_at=customer.created_at,
            )
        )

    return response
