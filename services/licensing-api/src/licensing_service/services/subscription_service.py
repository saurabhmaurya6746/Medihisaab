"""Subscription lifecycle management service."""

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy.orm import Session

from licensing_service.db.models import (
    Client,
    ClientStatus,
    Plan,
    Subscription,
    SubscriptionStatus,
)


def calculate_period_dates(start: date, billing_period: str) -> tuple[date, date]:
    """Calculate period end and grace period end dates."""
    if billing_period == "MONTHLY":
        end = start + timedelta(days=30)
        grace = end + timedelta(days=7)
    elif billing_period == "TRIAL":
        end = start + timedelta(days=15)
        grace = end + timedelta(days=7)
    else:  # ANNUAL / default
        end = start + timedelta(days=365)
        grace = end + timedelta(days=14)
    return end, grace


def start_trial(
    db: Session,
    client_id: int,
    trial_days: Optional[int] = None,
    grace_days: Optional[int] = None,
    notes: Optional[str] = None,
) -> Subscription:
    """Start evaluation trial subscription for client with configurable days."""
    from licensing_service.services.setting_service import get_default_grace_days, get_default_trial_days

    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise ValueError(f"Client {client_id} not found.")

    existing_trial = (
        db.query(Subscription)
        .filter(Subscription.client_id == client_id, Subscription.is_trial.is_(True))
        .first()
    )
    if existing_trial:
        raise ValueError(f"Client {client_id} has already been granted an evaluation trial.")

    trial_plan = db.query(Plan).filter(Plan.plan_code == "TRIAL").first()
    if not trial_plan:
        raise ValueError("Trial plan not configured.")

    actual_trial_days = trial_days if (trial_days is not None and trial_days > 0) else get_default_trial_days(db)
    actual_grace_days = grace_days if (grace_days is not None and grace_days >= 0) else get_default_grace_days(db)

    today = date.today()
    end_date = today + timedelta(days=actual_trial_days)
    grace_date = end_date + timedelta(days=actual_grace_days)

    sub = Subscription(
        client_id=client_id,
        plan_id=trial_plan.id,
        status=SubscriptionStatus.TRIALING.value,
        start_date=today,
        current_period_start=today,
        current_period_end=end_date,
        grace_period_end=grace_date,
        trial_days=actual_trial_days,
        is_trial=True,
        notes=notes or f"Initial {actual_trial_days}-day evaluation trial.",
    )
    client.status = ClientStatus.TRIAL.value
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def create_subscription(
    db: Session,
    client_id: int,
    plan_id: int,
    start_date: Optional[date] = None,
    expiry_date: Optional[date] = None,
    payment_reference: Optional[str] = None,
    amount: int = 0,
    payment_method: str = "UPI",
    notes: Optional[str] = None,
    recorded_by_email: Optional[str] = None,
) -> Subscription:
    """Create an active paid subscription and record payment receipt."""
    from licensing_service.services.payment_service import record_payment

    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise ValueError(f"Client {client_id} not found.")

    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise ValueError(f"Plan {plan_id} not found.")

    start = start_date or date.today()
    if expiry_date:
        end_date = expiry_date
        grace_date = expiry_date + timedelta(days=14)
    else:
        end_date, grace_date = calculate_period_dates(start, plan.billing_period)

    sub = Subscription(
        client_id=client_id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE.value,
        start_date=start,
        current_period_start=start,
        current_period_end=end_date,
        grace_period_end=grace_date,
        is_trial=False,
        payment_reference=payment_reference,
        notes=notes,
    )
    client.status = ClientStatus.ACTIVE.value
    db.add(sub)
    db.commit()
    db.refresh(sub)

    # Record in payments table if reference or amount is given
    if payment_reference or amount > 0:
        record_payment(
            db=db,
            client_id=client_id,
            subscription_id=sub.id,
            amount=amount if amount > 0 else plan.price,
            payment_reference=payment_reference or "MANUAL_PAID_SUB",
            payment_date=start,
            payment_method=payment_method,
            status="CONFIRMED",
            notes=notes or f"Initial payment for {plan.name}",
            recorded_by_email=recorded_by_email,
        )

    return sub


def convert_trial_to_paid(
    db: Session,
    subscription_id: int,
    plan_id: int,
    expiry_date: Optional[date] = None,
    payment_reference: str = "",
    amount: int = 0,
    payment_method: str = "UPI",
    notes: Optional[str] = None,
    recorded_by_email: Optional[str] = None,
) -> Subscription:
    """Convert an existing trial subscription into an active paid subscription."""
    from licensing_service.services.payment_service import record_payment

    sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not sub:
        raise ValueError(f"Subscription {subscription_id} not found.")

    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise ValueError(f"Plan {plan_id} not found.")

    today = date.today()
    base_date = sub.current_period_end if (sub.current_period_end and sub.current_period_end >= today) else today
    sub.plan_id = plan.id
    sub.is_trial = False
    sub.status = SubscriptionStatus.ACTIVE.value
    sub.current_period_start = base_date

    if expiry_date:
        sub.current_period_end = expiry_date
        sub.grace_period_end = expiry_date + timedelta(days=14)
    else:
        end_date, grace_date = calculate_period_dates(base_date, plan.billing_period)
        sub.current_period_end = end_date
        sub.grace_period_end = grace_date

    if payment_reference:
        sub.payment_reference = payment_reference.strip()

    if notes:
        sub.notes = (sub.notes or "") + f"\n[Converted to Paid {today.isoformat()}]: {notes}"

    if payment_reference or amount > 0:
        record_payment(
            db=db,
            client_id=sub.client_id,
            subscription_id=sub.id,
            amount=amount if amount > 0 else plan.price,
            payment_reference=payment_reference or "MANUAL_CONVERSION",
            payment_date=today,
            payment_method=payment_method,
            status="CONFIRMED",
            notes=notes or f"Converted trial to plan {plan.plan_code}",
            recorded_by_email=recorded_by_email,
        )

    sub.client.status = ClientStatus.ACTIVE.value
    db.commit()
    db.refresh(sub)
    return sub


def renew_subscription(
    db: Session,
    subscription_id: int,
    payment_reference: Optional[str] = None,
    amount: int = 0,
    payment_method: str = "UPI",
    notes: Optional[str] = None,
    recorded_by_email: Optional[str] = None,
    new_expiry_date: Optional[date] = None,
) -> Subscription:
    """Renew existing subscription by extending its period."""
    from licensing_service.services.payment_service import record_payment

    sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not sub:
        raise ValueError(f"Subscription {subscription_id} not found.")

    plan = sub.plan
    today = date.today()
    base_date = sub.current_period_end if sub.current_period_end >= today else today

    if new_expiry_date:
        sub.current_period_start = base_date
        sub.current_period_end = new_expiry_date
        sub.grace_period_end = new_expiry_date + timedelta(days=14)
    else:
        new_end, new_grace = calculate_period_dates(base_date, plan.billing_period)
        sub.current_period_start = base_date
        sub.current_period_end = new_end
        sub.grace_period_end = new_grace

    sub.status = SubscriptionStatus.ACTIVE.value
    sub.is_trial = False
    if payment_reference:
        sub.payment_reference = payment_reference.strip()
    if notes:
        sub.notes = (sub.notes or "") + f"\n[Renewal {today.isoformat()}]: {notes}"

    if payment_reference or amount > 0:
        record_payment(
            db=db,
            client_id=sub.client_id,
            subscription_id=sub.id,
            amount=amount if amount > 0 else plan.price,
            payment_reference=payment_reference or "MANUAL_RENEWAL",
            payment_date=today,
            payment_method=payment_method,
            status="CONFIRMED",
            notes=notes or f"Renewal for plan {plan.plan_code}",
            recorded_by_email=recorded_by_email,
        )

    sub.client.status = ClientStatus.ACTIVE.value
    db.commit()
    db.refresh(sub)
    return sub


def cancel_subscription(db: Session, subscription_id: int, reason: Optional[str] = None) -> Subscription:
    """Cancel a subscription."""
    sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not sub:
        raise ValueError(f"Subscription {subscription_id} not found.")

    sub.status = SubscriptionStatus.CANCELLED.value
    sub.cancelled_at = datetime.now(timezone.utc)
    if reason:
        sub.notes = (sub.notes or "") + f"\n[Cancelled]: {reason}"

    db.commit()
    db.refresh(sub)
    return sub


def suspend_subscription(db: Session, subscription_id: int, reason: Optional[str] = None) -> Subscription:
    """Suspend a subscription."""
    sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not sub:
        raise ValueError(f"Subscription {subscription_id} not found.")

    sub.status = SubscriptionStatus.SUSPENDED.value
    if reason:
        sub.notes = (sub.notes or "") + f"\n[Suspended]: {reason}"

    db.commit()
    db.refresh(sub)
    return sub


def evaluate_subscription_status(sub: Subscription) -> str:
    """Evaluate subscription status based on current date and grace period."""
    if sub.status in (SubscriptionStatus.CANCELLED.value, SubscriptionStatus.SUSPENDED.value):
        return sub.status

    today = date.today()
    if today <= sub.current_period_end:
        return sub.status  # ACTIVE or TRIALING
    elif today <= sub.grace_period_end:
        return SubscriptionStatus.PAST_DUE.value  # In renewal grace period
    else:
        return SubscriptionStatus.EXPIRED.value
