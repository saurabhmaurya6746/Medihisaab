"""Manual payment confirmation service."""

from datetime import date, datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session

from licensing_service.db.models import Client, Payment, Subscription


def record_payment(
    db: Session,
    client_id: int,
    amount: int,
    payment_reference: str,
    payment_date: Optional[date] = None,
    payment_method: str = "UPI",
    subscription_id: Optional[int] = None,
    status: str = "CONFIRMED",
    notes: Optional[str] = None,
    recorded_by_email: Optional[str] = None,
) -> Payment:
    """Record an offline manual payment confirmation."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise ValueError(f"Client {client_id} not found.")

    sub: Optional[Subscription] = None
    if subscription_id:
        sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
        if not sub:
            raise ValueError(f"Subscription {subscription_id} not found.")

    pay_date = payment_date or date.today()
    payment = Payment(
        client_id=client_id,
        subscription_id=subscription_id,
        amount=int(amount),
        currency="INR",
        payment_date=pay_date,
        payment_method=payment_method.strip().upper(),
        payment_reference=payment_reference.strip(),
        status=status.strip().upper(),
        notes=notes,
        recorded_by_email=recorded_by_email,
    )
    db.add(payment)

    # If linked to a subscription, update its payment reference too
    if sub and payment_reference:
        sub.payment_reference = payment_reference.strip()

    db.commit()
    db.refresh(payment)
    return payment


def list_payments(
    db: Session,
    client_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Payment]:
    """List recorded payments with optional client filter."""
    q = db.query(Payment)
    if client_id:
        q = q.filter(Payment.client_id == client_id)
    return q.order_by(Payment.id.desc()).offset(offset).limit(limit).all()


def get_payment(db: Session, payment_id: int) -> Optional[Payment]:
    """Retrieve single payment by ID."""
    return db.query(Payment).filter(Payment.id == payment_id).first()


def submit_client_payment(
    db: Session,
    client_id: int,
    amount: int,
    payment_reference: str,
    plan_id: Optional[int] = None,
    payment_method: str = "UPI",
    notes: Optional[str] = None,
) -> Payment:
    """Submit client payment transaction pending vendor review and confirmation."""
    clean_ref = str(payment_reference or "").strip()
    if not clean_ref:
        raise ValueError("Payment reference / UTR is required.")
    if amount <= 0:
        raise ValueError("Payment amount must be greater than zero.")

    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise ValueError(f"Client {client_id} not found.")

    latest_sub = (
        db.query(Subscription)
        .filter(Subscription.client_id == client_id)
        .order_by(Subscription.id.desc())
        .first()
    )

    pay = Payment(
        client_id=client_id,
        subscription_id=latest_sub.id if latest_sub else None,
        plan_id=plan_id,
        amount=int(amount),
        currency="INR",
        payment_date=date.today(),
        payment_method=payment_method.strip().upper(),
        payment_reference=clean_ref,
        status="PENDING",
        notes=notes,
    )
    db.add(pay)
    db.commit()
    db.refresh(pay)
    return pay


def confirm_client_payment(
    db: Session,
    payment_id: int,
    reviewed_by_email: str,
    notes: Optional[str] = None,
):
    """Vendor confirms a submitted payment, extends subscription, and issues signed license."""
    from licensing_service.db.models import Plan
    from licensing_service.services.license_service import issue_license
    from licensing_service.services.subscription_service import (
        convert_trial_to_paid,
        create_subscription,
        renew_subscription,
    )

    pay = db.query(Payment).filter(Payment.id == payment_id).first()
    if not pay:
        raise ValueError(f"Payment #{payment_id} not found.")
    if pay.status == "CONFIRMED":
        raise ValueError(f"Payment #{payment_id} has already been confirmed.")

    pay.status = "CONFIRMED"
    pay.reviewed_by_email = reviewed_by_email
    pay.reviewed_at = datetime.now(timezone.utc)
    if notes:
        pay.notes = (pay.notes or "") + f"\n[Review Notes]: {notes}"

    # Determine target plan
    target_plan = None
    if pay.plan_id:
        target_plan = db.query(Plan).filter(Plan.id == pay.plan_id).first()

    sub = None
    if pay.subscription_id:
        sub = db.query(Subscription).filter(Subscription.id == pay.subscription_id).first()
    if not sub:
        sub = (
            db.query(Subscription)
            .filter(Subscription.client_id == pay.client_id)
            .order_by(Subscription.id.desc())
            .first()
        )

    if not target_plan:
        if sub and sub.plan and sub.plan.plan_code != "TRIAL":
            target_plan = sub.plan
        else:
            # Default to MONTHLY_STANDARD
            target_plan = (
                db.query(Plan).filter(Plan.plan_code == "MONTHLY_STANDARD").first()
                or db.query(Plan).filter(Plan.plan_code == "SINGLE_COUNTER").first()
            )

    if not target_plan:
        raise ValueError("No target plan found for confirmation.")

    if sub and sub.is_trial:
        sub = convert_trial_to_paid(
            db=db,
            subscription_id=sub.id,
            plan_id=target_plan.id,
            payment_reference=pay.payment_reference,
            amount=pay.amount,
            payment_method=pay.payment_method,
            notes=pay.notes,
            recorded_by_email=reviewed_by_email,
        )
    elif sub:
        if target_plan.id != sub.plan_id:
            sub.plan_id = target_plan.id
        sub = renew_subscription(
            db=db,
            subscription_id=sub.id,
            payment_reference=pay.payment_reference,
            amount=pay.amount,
            payment_method=pay.payment_method,
            notes=pay.notes,
            recorded_by_email=reviewed_by_email,
        )
    else:
        sub = create_subscription(
            db=db,
            client_id=pay.client_id,
            plan_id=target_plan.id,
            payment_reference=pay.payment_reference,
            amount=pay.amount,
            payment_method=pay.payment_method,
            notes=pay.notes,
            recorded_by_email=reviewed_by_email,
        )

    pay.subscription_id = sub.id

    # Automatically issue new signed Ed25519 license token
    lic = issue_license(db=db, client_id=pay.client_id, subscription_id=sub.id)

    db.commit()
    db.refresh(pay)
    db.refresh(sub)
    return pay, sub, lic


def reject_client_payment(
    db: Session,
    payment_id: int,
    reviewed_by_email: str,
    reason: str,
) -> Payment:
    """Vendor rejects an invalid or unverified submitted payment."""
    pay = db.query(Payment).filter(Payment.id == payment_id).first()
    if not pay:
        raise ValueError(f"Payment #{payment_id} not found.")

    pay.status = "REJECTED"
    pay.rejection_reason = (reason or "Payment could not be verified with bank/UPI statement.").strip()
    pay.reviewed_by_email = reviewed_by_email
    pay.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(pay)
    return pay
