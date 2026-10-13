"""Subscription management endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from licensing_service.api.schemas import (
    ActionReasonRequest,
    ApiEnvelope,
    ConvertTrialRequest,
    CreatePaidSubscriptionRequest,
    RecordPaymentRequest,
    RenewSubscriptionRequest,
    StartTrialRequest,
    SubscriptionResponse,
)
from licensing_service.db.models import Subscription, VendorRole, VendorUser
from licensing_service.db.session import get_db
from licensing_service.security.auth import get_current_vendor_user, require_role
from licensing_service.services.audit import log_audit_event
from licensing_service.services.subscription_service import (
    cancel_subscription,
    convert_trial_to_paid,
    create_subscription,
    evaluate_subscription_status,
    renew_subscription,
    start_trial,
    suspend_subscription,
)

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


@router.get("", response_model=ApiEnvelope)
def list_subscriptions(
    client_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: VendorUser = Depends(get_current_vendor_user),
):
    """List subscriptions with optional client and status filters."""
    q = db.query(Subscription)
    if client_id:
        q = q.filter(Subscription.client_id == client_id)
    if status:
        q = q.filter(Subscription.status == status)

    subs = q.order_by(Subscription.id.desc()).all()
    for s in subs:
        s.status = evaluate_subscription_status(s)

    data = [SubscriptionResponse.model_validate(s) for s in subs]
    return ApiEnvelope(data=[d.model_dump() for d in data])


@router.get("/{sub_id}", response_model=ApiEnvelope)
def get_subscription_detail(
    sub_id: int,
    db: Session = Depends(get_db),
    user: VendorUser = Depends(get_current_vendor_user),
):
    """Get single subscription by ID."""
    sub = db.query(Subscription).filter(Subscription.id == sub_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail=f"Subscription {sub_id} not found.")
    sub.status = evaluate_subscription_status(sub)
    data = SubscriptionResponse.model_validate(sub)
    return ApiEnvelope(data=data.model_dump())


@router.post("/trial", response_model=ApiEnvelope, status_code=status.HTTP_201_CREATED)
@router.post("/start-trial", response_model=ApiEnvelope, status_code=status.HTTP_201_CREATED)
def start_client_trial(
    req: StartTrialRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: VendorUser = Depends(require_role(VendorRole.OWNER, VendorRole.ADMIN, VendorRole.SUPPORT)),
):
    """Start an evaluation trial for a client with configurable or overridden duration."""
    try:
        sub = start_trial(
            db=db,
            client_id=req.client_id,
            trial_days=req.trial_days,
            grace_days=req.grace_days,
            notes=req.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    client_ip = request.client.host if request.client else None
    log_audit_event(
        db=db,
        user_email=user.email,
        action="START_TRIAL",
        entity_type="SUBSCRIPTION",
        entity_id=str(sub.id),
        ip_address=client_ip,
        metadata={
            "client_id": req.client_id,
            "trial_days": sub.trial_days,
            "grace_period_end": sub.grace_period_end.isoformat(),
        },
    )

    data = SubscriptionResponse.model_validate(sub)
    return ApiEnvelope(data=data.model_dump(), message="Trial started successfully.")


@router.post("", response_model=ApiEnvelope, status_code=status.HTTP_201_CREATED)
@router.post("/paid", response_model=ApiEnvelope, status_code=status.HTTP_201_CREATED)
def create_paid_sub(
    req: CreatePaidSubscriptionRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: VendorUser = Depends(require_role(VendorRole.OWNER, VendorRole.ADMIN, VendorRole.SUPPORT)),
):
    """Create a paid subscription manually and record payment receipt."""
    from licensing_service.db.models import Plan

    target_plan_id = req.plan_id
    if not target_plan_id and req.plan_code:
        plan = db.query(Plan).filter(Plan.plan_code == req.plan_code).first()
        if not plan:
            raise HTTPException(status_code=400, detail=f"Plan code {req.plan_code} not found.")
        target_plan_id = plan.id
    if not target_plan_id:
        raise HTTPException(status_code=400, detail="Either plan_id or plan_code must be provided.")

    try:
        sub = create_subscription(
            db=db,
            client_id=req.client_id,
            plan_id=target_plan_id,
            start_date=req.start_date,
            expiry_date=req.expiry_date,
            payment_reference=req.payment_reference,
            amount=req.amount or 0,
            payment_method=req.payment_method or "UPI",
            notes=req.notes,
            recorded_by_email=user.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    client_ip = request.client.host if request.client else None
    log_audit_event(
        db=db,
        user_email=user.email,
        action="CREATE_PAID_SUBSCRIPTION",
        entity_type="SUBSCRIPTION",
        entity_id=str(sub.id),
        ip_address=client_ip,
        metadata={
            "client_id": req.client_id,
            "plan_id": target_plan_id,
            "ref": req.payment_reference,
            "amount": req.amount,
        },
    )

    data = SubscriptionResponse.model_validate(sub)
    return ApiEnvelope(data=data.model_dump(), message="Subscription created successfully.")


@router.post("/{sub_id}/convert-to-paid", response_model=ApiEnvelope)
def convert_sub_to_paid(
    sub_id: int,
    req: ConvertTrialRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: VendorUser = Depends(require_role(VendorRole.OWNER, VendorRole.ADMIN, VendorRole.SUPPORT)),
):
    """Convert an existing trial subscription to an active paid subscription."""
    try:
        sub = convert_trial_to_paid(
            db=db,
            subscription_id=sub_id,
            plan_id=req.plan_id,
            expiry_date=req.expiry_date,
            payment_reference=req.payment_reference or "",
            amount=req.amount or 0,
            payment_method=req.payment_method or "UPI",
            notes=req.notes,
            recorded_by_email=user.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    client_ip = request.client.host if request.client else None
    log_audit_event(
        db=db,
        user_email=user.email,
        action="CONVERT_TRIAL_TO_PAID",
        entity_type="SUBSCRIPTION",
        entity_id=str(sub.id),
        ip_address=client_ip,
        metadata={
            "subscription_id": sub.id,
            "plan_id": req.plan_id,
            "ref": req.payment_reference,
            "amount": req.amount,
        },
    )

    data = SubscriptionResponse.model_validate(sub)
    return ApiEnvelope(data=data.model_dump(), message="Trial successfully converted to paid subscription.")


@router.post("/{sub_id}/payment", response_model=ApiEnvelope)
def record_payment_endpoint(
    sub_id: int,
    req: RecordPaymentRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: VendorUser = Depends(require_role(VendorRole.OWNER, VendorRole.ADMIN, VendorRole.SUPPORT)),
):
    """Confirm and record manual payment for subscription."""
    from licensing_service.services.payment_service import record_payment as record_payment_fn

    sub = db.query(Subscription).filter(Subscription.id == sub_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail=f"Subscription {sub_id} not found.")

    pay = record_payment_fn(
        db=db,
        client_id=sub.client_id,
        subscription_id=sub.id,
        amount=req.amount,
        payment_reference=req.payment_reference,
        payment_method=req.payment_method,
        notes=req.notes,
        recorded_by_email=user.email,
    )

    client_ip = request.client.host if request.client else None
    log_audit_event(
        db=db,
        user_email=user.email,
        action="RECORD_PAYMENT",
        entity_type="PAYMENT",
        entity_id=str(pay.id),
        ip_address=client_ip,
        metadata={"amount": req.amount, "reference": req.payment_reference, "method": req.payment_method},
    )

    data = SubscriptionResponse.model_validate(sub)
    return ApiEnvelope(data=data.model_dump(), message="Payment recorded successfully.")


@router.post("/{sub_id}/renew", response_model=ApiEnvelope)
def renew_sub(
    sub_id: int,
    body: Optional[RenewSubscriptionRequest] = None,
    payment_reference: Optional[str] = Query(None),
    notes: Optional[str] = Query(None),
    request: Request = None,
    db: Session = Depends(get_db),
    user: VendorUser = Depends(require_role(VendorRole.OWNER, VendorRole.ADMIN, VendorRole.SUPPORT)),
):
    """Renew an existing subscription period with optional payment receipt."""
    ref = body.payment_reference if body and body.payment_reference else payment_reference
    n = body.notes if body and body.notes else notes
    amt = body.amount if body and body.amount else 0
    method = body.payment_method if body and body.payment_method else "UPI"
    new_expiry = body.new_expiry_date if body and body.new_expiry_date else None

    try:
        sub = renew_subscription(
            db=db,
            subscription_id=sub_id,
            payment_reference=ref,
            amount=amt,
            payment_method=method,
            notes=n,
            recorded_by_email=user.email,
            new_expiry_date=new_expiry,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    client_ip = request.client.host if request and request.client else None
    log_audit_event(
        db=db,
        user_email=user.email,
        action="RENEW_SUBSCRIPTION",
        entity_type="SUBSCRIPTION",
        entity_id=str(sub.id),
        ip_address=client_ip,
        metadata={"new_end_date": sub.current_period_end.isoformat(), "reference": ref},
    )

    data = SubscriptionResponse.model_validate(sub)
    return ApiEnvelope(data=data.model_dump(), message="Subscription renewed successfully.")


@router.post("/{sub_id}/cancel", response_model=ApiEnvelope)
def cancel_sub(
    sub_id: int,
    body: Optional[ActionReasonRequest] = None,
    reason: Optional[str] = Query(None),
    request: Request = None,
    db: Session = Depends(get_db),
    user: VendorUser = Depends(require_role(VendorRole.OWNER, VendorRole.ADMIN)),
):
    """Cancel subscription (OWNER and ADMIN only)."""
    reason_val = (body.reason or body.notes) if body else reason
    try:
        sub = cancel_subscription(db, sub_id, reason=reason_val)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    client_ip = request.client.host if request and request.client else None
    log_audit_event(
        db=db,
        user_email=user.email,
        action="CANCEL_SUBSCRIPTION",
        entity_type="SUBSCRIPTION",
        entity_id=str(sub.id),
        ip_address=client_ip,
        metadata={"reason": reason_val},
    )

    data = SubscriptionResponse.model_validate(sub)
    return ApiEnvelope(data=data.model_dump(), message="Subscription cancelled.")


@router.post("/{sub_id}/suspend", response_model=ApiEnvelope)
def suspend_sub(
    sub_id: int,
    body: Optional[ActionReasonRequest] = None,
    reason: Optional[str] = Query(None),
    request: Request = None,
    db: Session = Depends(get_db),
    user: VendorUser = Depends(require_role(VendorRole.OWNER, VendorRole.ADMIN)),
):
    """Suspend subscription (OWNER and ADMIN only)."""
    reason_val = (body.reason or body.notes) if body else reason
    try:
        sub = suspend_subscription(db, sub_id, reason=reason_val)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    client_ip = request.client.host if request and request.client else None
    log_audit_event(
        db=db,
        user_email=user.email,
        action="SUSPEND_SUBSCRIPTION",
        entity_type="SUBSCRIPTION",
        entity_id=str(sub.id),
        ip_address=client_ip,
        metadata={"reason": reason_val},
    )

    data = SubscriptionResponse.model_validate(sub)
    return ApiEnvelope(data=data.model_dump(), message="Subscription suspended.")
