"""Staff dashboard metrics and KPIs."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from portal_service.db.models import (
    Customer,
    Order,
    OrderStatusEnum,
    PortalStaffUser,
    Product,
    StockStatusEnum,
)
from portal_service.db.session import get_db
from portal_service.security.dependencies import get_current_staff
from portal_service.schemas import StaffDashboardMetrics

router = APIRouter(prefix="/staff/dashboard", tags=["Staff Dashboard"])


@router.get("/metrics", response_model=StaffDashboardMetrics)
def get_dashboard_metrics(
    current_staff: PortalStaffUser = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    """Retrieve operational KPIs for staff overview."""
    total_orders = db.query(Order).count()

    pending_confirmation = (
        db.query(Order)
        .filter(Order.status == OrderStatusEnum.PENDING_CONFIRMATION.value)
        .count()
    )

    pharmacist_review = (
        db.query(Order)
        .filter(Order.status == OrderStatusEnum.PHARMACIST_REVIEW.value)
        .count()
    )

    ready_orders = (
        db.query(Order)
        .filter(Order.status.in_([OrderStatusEnum.READY_FOR_PICKUP.value, OrderStatusEnum.OUT_FOR_DELIVERY.value]))
        .count()
    )

    # Orders delivered today
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    delivered_today = (
        db.query(Order)
        .filter(
            Order.status == OrderStatusEnum.DELIVERED.value,
            Order.updated_at >= today_start,
        )
        .count()
    )

    # Revenue today
    revenue_today = (
        db.query(func.coalesce(func.sum(Order.total_paise), 0))
        .filter(
            Order.status == OrderStatusEnum.DELIVERED.value,
            Order.updated_at >= today_start,
        )
        .scalar()
    )

    total_products = db.query(Product).count()
    low_stock = (
        db.query(Product)
        .filter(Product.stock_status.in_([StockStatusEnum.LOW_STOCK.value, StockStatusEnum.OUT_OF_STOCK.value]))
        .count()
    )

    total_customers = db.query(Customer).count()

    return StaffDashboardMetrics(
        total_orders=total_orders,
        pending_confirmation_count=pending_confirmation,
        pharmacist_review_count=pharmacist_review,
        ready_orders_count=ready_orders,
        delivered_today_count=delivered_today,
        total_products_count=total_products,
        low_stock_count=low_stock,
        total_customers_count=total_customers,
        revenue_today_paise=int(revenue_today),
    )
