"""Renewal request management service."""

from datetime import datetime, timezone
import logging
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session

from licensing_service.db.models import (
    Client,
    LicenseRecord,
    Plan,
    RenewalRequest,
    Subscription,
)
from licensing_service.services.audit import log_audit_event
from licensing_service.services.email_service import send_vendor_renewal_notification
from licensing_service.services.license_service import issue_license
from licensing_service.services.subscription_service import (
    convert_trial_to_paid,
    create_subscription,
    renew_subscription,
)

logger = logging.getLogger("licensing_service.services.renewal_service")


def create_renewal_request(
    db: Session,
    client_id: Optional[int],
    store_name: str,
    contact_name: str,
    email: str,
    phone: str,
    requested_plan_code: str = "MONTHLY_STANDARD",
    payment_reference: Optional[str] = None,
    payment_amount: int = 0,
    notes: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> RenewalRequest:
    """Create in-app license renewal request, notify vendor, and log auditable event."""
    clean_email = email.strip().lower() if email else ""
    clean_phone = phone.strip() if phone else ""
    clean_store = store_name.strip() if store_name else ""
    clean_contact = contact_name.strip() if contact_name else ""

    if not clean_email or "@" not in clean_email:
        raise ValueError("A valid email address is required for renewal requests.")
    if len(clean_phone) < 7:
        raise ValueError("A valid phone number is required for renewal requests.")
    if len(clean_store) < 2:
        raise ValueError("Store name is required.")

    # Match client if client_id is not provided
    resolved_client_id = client_id
    if not resolved_client_id:
        client_record = db.query(Client).filter(Client.email.ilike(clean_email)).first()
        if not client_record:
            client_record = db.query(Client).filter(Client.phone == clean_phone).first()
        if client_record:
            resolved_client_id = client_record.id
        else:
            raise ValueError(
                f"No existing client account found matching email '{clean_email}' or phone '{clean_phone}'. "
                "Please verify your account details or register a new account."
            )

    # Find active subscription and requested plan
    client = db.query(Client).filter(Client.id == resolved_client_id).first()
    if not client:
        raise ValueError(f"Client account {resolved_client_id} not found.")

    latest_sub = (
        db.query(Subscription)
        .filter(Subscription.client_id == resolved_client_id)
        .order_by(Subscription.id.desc())
        .first()
    )

    plan = db.query(Plan).filter(Plan.plan_code == requested_plan_code).first()
    if not plan:
        # Fallback to monthly standard
        plan = db.query(Plan).filter(Plan.plan_code == "MONTHLY_STANDARD").first()

    renewal = RenewalRequest(
        client_id=resolved_client_id,
        subscription_id=latest_sub.id if latest_sub else None,
        plan_id=plan.id if plan else None,
        requested_plan_code=requested_plan_code or (plan.plan_code if plan else "MONTHLY_STANDARD"),
        store_name=clean_store or client.business_name,
        contact_name=clean_contact or client.owner_name,
        email=clean_email,
        phone=clean_phone,
        status="PENDING",
        notes=notes.strip() if notes else None,
        payment_reference=payment_reference.strip() if payment_reference else None,
        payment_amount=payment_amount or (plan.price if plan else 0),
    )
    db.add(renewal)
    db.commit()
    db.refresh(renewal)

    # Dispatch email notification to vendor
    sent, error = send_vendor_renewal_notification(db, renewal)
    renewal.vendor_notification_sent = sent
    renewal.vendor_notification_error = error
    db.commit()
    db.refresh(renewal)

    log_audit_event(
        db=db,
        user_email=clean_email,
        action="RENEWAL_REQUEST_SUBMITTED",
        entity_type="RENEWAL_REQUEST",
        entity_id=str(renewal.id),
        ip_address=ip_address,
        metadata={
            "client_code": client.client_code,
            "store_name": renewal.store_name,
            "plan_code": renewal.requested_plan_code,
            "payment_ref": renewal.payment_reference,
            "vendor_notified": sent,
        },
    )

    return renewal


def list_renewal_requests(
    db: Session,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[RenewalRequest]:
    """Retrieve list of renewal requests with optional status filtering."""
    q = db.query(RenewalRequest)
    if status:
        q = q.filter(RenewalRequest.status == status.upper())
    return q.order_by(RenewalRequest.id.desc()).offset(offset).limit(limit).all()


def get_renewal_request(db: Session, request_id: int) -> Optional[RenewalRequest]:
    return db.query(RenewalRequest).filter(RenewalRequest.id == request_id).first()


def approve_renewal_request(
    db: Session,
    request_id: int,
    reviewer_email: str,
    ip_address: Optional[str] = None,
    plan_id: Optional[int] = None,
    payment_reference: Optional[str] = None,
    amount: Optional[int] = None,
    notes: Optional[str] = None,
) -> Tuple[RenewalRequest, Subscription, LicenseRecord]:
    """Approve renewal request, extend subscription from max(today, expiry), and issue signed license."""
    renewal = get_renewal_request(db, request_id)
    if not renewal:
        raise ValueError(f"Renewal request #{request_id} not found.")

    if renewal.status == "APPROVED":
        raise ValueError(f"Renewal request #{request_id} has already been approved.")

    target_plan_id = plan_id or renewal.plan_id
    if not target_plan_id:
        target_plan = db.query(Plan).filter(Plan.plan_code == renewal.requested_plan_code).first()
        if target_plan:
            target_plan_id = target_plan.id
        else:
            default_monthly = db.query(Plan).filter(Plan.plan_code == "MONTHLY_STANDARD").first()
            target_plan_id = default_monthly.id if default_monthly else 1

    ref = payment_reference or renewal.payment_reference or f"RENEW-{renewal.id}"
    amt = amount if amount is not None else renewal.payment_amount

    # 1. Renew or convert subscription extending period
    target_sub = None
    if renewal.subscription_id:
        target_sub = db.query(Subscription).filter(Subscription.id == renewal.subscription_id).first()
    if not target_sub and renewal.client_id:
        target_sub = (
            db.query(Subscription)
            .filter(Subscription.client_id == renewal.client_id)
            .order_by(Subscription.id.desc())
            .first()
        )

    if target_sub and target_sub.is_trial:
        sub = convert_trial_to_paid(
            db=db,
            subscription_id=target_sub.id,
            plan_id=target_plan_id,
            payment_reference=ref,
            amount=amt or 0,
            notes=notes or renewal.notes or f"Approved renewal request #{renewal.id}",
            recorded_by_email=reviewer_email,
        )
    elif target_sub:
        if target_plan_id and target_sub.plan_id != target_plan_id:
            target_sub.plan_id = target_plan_id
            db.commit()
        sub = renew_subscription(
            db=db,
            subscription_id=target_sub.id,
            payment_reference=ref,
            amount=amt or 0,
            notes=notes or renewal.notes or f"Approved renewal request #{renewal.id}",
            recorded_by_email=reviewer_email,
        )
    else:
        sub = create_subscription(
            db=db,
            client_id=renewal.client_id,
            plan_id=target_plan_id,
            payment_reference=ref,
            amount=amt or 0,
            notes=notes or renewal.notes or f"Approved renewal request #{renewal.id}",
            recorded_by_email=reviewer_email,
        )

    # 2. Issue fresh signed Ed25519 renewal license
    lic = issue_license(db=db, client_id=renewal.client_id, subscription_id=sub.id)

    # 3. Update renewal request status
    now = datetime.now(timezone.utc)
    renewal.status = "APPROVED"
    renewal.subscription_id = sub.id
    renewal.plan_id = target_plan_id
    renewal.payment_reference = ref
    renewal.payment_amount = amt
    renewal.reviewed_by_email = reviewer_email
    renewal.reviewed_at = now
    db.commit()
    db.refresh(renewal)

    log_audit_event(
        db=db,
        user_email=reviewer_email,
        action="RENEWAL_REQUEST_APPROVED",
        entity_type="RENEWAL_REQUEST",
        entity_id=str(renewal.id),
        ip_address=ip_address,
        metadata={
            "client_code": renewal.client.client_code if renewal.client else None,
            "subscription_id": sub.id,
            "license_id": lic.license_id,
            "new_expiry": str(sub.current_period_end),
            "payment_ref": ref,
        },
    )

    return renewal, sub, lic


def reject_renewal_request(
    db: Session,
    request_id: int,
    reviewer_email: str,
    reason: str,
    ip_address: Optional[str] = None,
) -> RenewalRequest:
    """Reject a renewal request with documented reason."""
    renewal = get_renewal_request(db, request_id)
    if not renewal:
        raise ValueError(f"Renewal request #{request_id} not found.")

    if renewal.status in ("APPROVED", "REJECTED"):
        raise ValueError(f"Renewal request #{request_id} is already {renewal.status.lower()}.")

    clean_reason = reason.strip() if reason else "Rejected by vendor administrator"
    now = datetime.now(timezone.utc)
    renewal.status = "REJECTED"
    renewal.rejection_reason = clean_reason
    renewal.reviewed_by_email = reviewer_email
    renewal.reviewed_at = now
    db.commit()
    db.refresh(renewal)

    log_audit_event(
        db=db,
        user_email=reviewer_email,
        action="RENEWAL_REQUEST_REJECTED",
        entity_type="RENEWAL_REQUEST",
        entity_id=str(renewal.id),
        ip_address=ip_address,
        metadata={
            "client_code": renewal.client.client_code if renewal.client else None,
            "reason": clean_reason,
        },
    )

    return renewal
