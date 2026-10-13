"""Manual payments API endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from licensing_service.api.schemas import (
    ApiEnvelope,
    PaymentCreateRequest,
    PaymentRejectRequest,
    PaymentResponse,
    SubscriptionResponse,
)
from licensing_service.db.models import VendorRole, VendorUser
from licensing_service.db.session import get_db
from licensing_service.security.auth import get_current_vendor_user, require_role
from licensing_service.services.audit import log_audit_event
from licensing_service.services.payment_service import (
    confirm_client_payment,
    get_payment,
    list_payments,
    record_payment,
    reject_client_payment,
)

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.get("", response_model=ApiEnvelope)
def get_payments(
    client_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: VendorUser = Depends(get_current_vendor_user),
):
    """List recorded payments."""
    payments = list_payments(db, client_id=client_id, limit=limit, offset=offset)
    data = [PaymentResponse.model_validate(p).model_dump() for p in payments]
    return ApiEnvelope(data=data)


@router.get("/{payment_id}", response_model=ApiEnvelope)
def get_payment_detail(
    payment_id: int,
    db: Session = Depends(get_db),
    user: VendorUser = Depends(get_current_vendor_user),
):
    """Retrieve single payment by ID."""
    payment = get_payment(db, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found.")
    return ApiEnvelope(data=PaymentResponse.model_validate(payment).model_dump())


@router.post("", response_model=ApiEnvelope, status_code=status.HTTP_201_CREATED)
def create_payment(
    req: PaymentCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: VendorUser = Depends(require_role(VendorRole.OWNER, VendorRole.ADMIN, VendorRole.SUPPORT)),
):
    """Record an offline manual payment confirmation."""
    try:
        payment = record_payment(
            db=db,
            client_id=req.client_id,
            subscription_id=req.subscription_id,
            amount=req.amount,
            payment_reference=req.payment_reference,
            payment_date=req.payment_date,
            payment_method=req.payment_method,
            notes=req.notes,
            recorded_by_email=user.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    client_ip = request.client.host if request.client else None
    log_audit_event(
        db=db,
        user_email=user.email,
        action="RECORD_PAYMENT",
        entity_type="PAYMENT",
        entity_id=str(payment.id),
        ip_address=client_ip,
        metadata={
            "client_id": req.client_id,
            "amount": req.amount,
            "ref": req.payment_reference,
            "method": req.payment_method,
        },
    )

    data = PaymentResponse.model_validate(payment)
    return ApiEnvelope(data=data.model_dump(), message="Payment successfully recorded.")


@router.post("/{payment_id}/confirm", response_model=ApiEnvelope)
def confirm_payment_endpoint(
    payment_id: int,
    notes: Optional[str] = Query(None),
    request: Request = None,
    db: Session = Depends(get_db),
    user: VendorUser = Depends(require_role(VendorRole.OWNER, VendorRole.ADMIN, VendorRole.SUPPORT)),
):
    """Confirm a submitted client payment, extend subscription, and issue signed license."""
    try:
        payment, sub, lic = confirm_client_payment(
            db=db,
            payment_id=payment_id,
            reviewed_by_email=user.email,
            notes=notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    client_ip = request.client.host if request and request.client else None
    log_audit_event(
        db=db,
        user_email=user.email,
        action="CONFIRM_PAYMENT",
        entity_type="PAYMENT",
        entity_id=str(payment.id),
        ip_address=client_ip,
        metadata={
            "client_id": payment.client_id,
            "subscription_id": sub.id if sub else None,
            "license_id": lic.license_id if lic else None,
            "amount": payment.amount,
            "ref": payment.payment_reference,
        },
    )

    return ApiEnvelope(
        data={
            "payment": PaymentResponse.model_validate(payment).model_dump(),
            "subscription": SubscriptionResponse.model_validate(sub).model_dump() if sub else None,
            "license_id": lic.license_id if lic else None,
        },
        message="Payment confirmed, subscription updated, and renewed license signed successfully.",
    )


@router.post("/{payment_id}/reject", response_model=ApiEnvelope)
def reject_payment_endpoint(
    payment_id: int,
    req: PaymentRejectRequest,
    request: Request = None,
    db: Session = Depends(get_db),
    user: VendorUser = Depends(require_role(VendorRole.OWNER, VendorRole.ADMIN, VendorRole.SUPPORT)),
):
    """Reject an unverified or invalid submitted payment."""
    try:
        payment = reject_client_payment(
            db=db,
            payment_id=payment_id,
            reviewed_by_email=user.email,
            reason=req.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    client_ip = request.client.host if request and request.client else None
    log_audit_event(
        db=db,
        user_email=user.email,
        action="REJECT_PAYMENT",
        entity_type="PAYMENT",
        entity_id=str(payment.id),
        ip_address=client_ip,
        metadata={"reason": req.reason, "client_id": payment.client_id},
    )

    return ApiEnvelope(
        data=PaymentResponse.model_validate(payment).model_dump(),
        message="Payment rejected.",
    )
