"""Dashboard KPI statistics and recent licenses."""

from datetime import date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from licensing_service.api.schemas import ApiEnvelope, DashboardStatsResponse, LicenseResponse
from licensing_service.db.models import (
    Client,
    ClientStatus,
    LicenseRecord,
    Subscription,
    SubscriptionStatus,
    VendorUser,
)
from licensing_service.db.session import get_db
from licensing_service.security.auth import get_current_vendor_user

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=ApiEnvelope)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    user: VendorUser = Depends(get_current_vendor_user),
):
    """Retrieve executive metrics and KPI counters for software owner dashboard."""
    today = date.today()
    in_14_days = today + timedelta(days=14)

    total_clients = db.query(Client).count()
    trial_clients = db.query(Client).filter(Client.status == ClientStatus.TRIAL.value).count()
    suspended_clients = db.query(Client).filter(Client.status == ClientStatus.SUSPENDED.value).count()

    active_subs = db.query(Subscription).filter(Subscription.status == SubscriptionStatus.ACTIVE.value).count()

    # Expiring soon: active/trialing subscriptions ending within next 14 days
    expiring_soon = (
        db.query(Subscription)
        .filter(
            Subscription.status.in_([SubscriptionStatus.ACTIVE.value, SubscriptionStatus.TRIALING.value]),
            Subscription.current_period_end >= today,
            Subscription.current_period_end <= in_14_days,
        )
        .count()
    )

    # Expired: past grace period
    expired_subs = (
        db.query(Subscription)
        .filter(
            Subscription.status.in_([SubscriptionStatus.EXPIRED.value, SubscriptionStatus.PAST_DUE.value])
            | (Subscription.grace_period_end < today)
        )
        .count()
    )

    total_licenses = db.query(LicenseRecord).count()

    recent_licenses = (
        db.query(LicenseRecord)
        .order_by(LicenseRecord.id.desc())
        .limit(10)
        .all()
    )

    stats = DashboardStatsResponse(
        total_clients=total_clients,
        active_subscriptions=active_subs,
        trial_clients=trial_clients,
        expiring_soon_subscriptions=expiring_soon,
        expired_subscriptions=expired_subs,
        suspended_clients=suspended_clients,
        total_licenses_issued=total_licenses,
        recent_licenses=[LicenseResponse.model_validate(l) for l in recent_licenses],
    )
    return ApiEnvelope(data=stats.model_dump())
