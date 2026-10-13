"""Vendor admin API endpoints for reviewing and approving license renewal requests."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from licensing_service.api.schemas import (
    ApiEnvelope,
    RenewalRequestApproveInput,
    RenewalRequestRejectInput,
    RenewalRequestResponse,
)
from licensing_service.db.models import VendorRole, VendorUser
from licensing_service.db.session import get_db
from licensing_service.security.auth import get_current_vendor_user, require_role
from licensing_service.services.license_service import get_license_download_payload
from licensing_service.services.renewal_service import (
    approve_renewal_request,
    get_renewal_request,
    list_renewal_requests,
    reject_renewal_request,
)

router = APIRouter(prefix="/renewal-requests", tags=["Renewal Requests"])


@router.get("", response_model=ApiEnvelope)
def get_all_renewal_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: VendorUser = Depends(get_current_vendor_user),
):
    """List client renewal requests with optional status filtering."""
    requests = list_renewal_requests(db=db, status=status_filter, limit=limit, offset=offset)
    data = [RenewalRequestResponse.model_validate(r).model_dump() for r in requests]
    return ApiEnvelope(data=data)


@router.get("/{request_id}", response_model=ApiEnvelope)
def get_single_renewal_request(
    request_id: int,
    db: Session = Depends(get_db),
    user: VendorUser = Depends(get_current_vendor_user),
):
    """Retrieve details for a specific renewal request."""
    req = get_renewal_request(db, request_id)
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Renewal request not found.")
    return ApiEnvelope(data=RenewalRequestResponse.model_validate(req).model_dump())


@router.post("/{request_id}/approve", response_model=ApiEnvelope)
def approve_request(
    request_id: int,
    body: RenewalRequestApproveInput,
    request: Request,
    db: Session = Depends(get_db),
    user: VendorUser = Depends(require_role(VendorRole.OWNER, VendorRole.ADMIN)),
):
    """Vendor approves renewal request, extending subscription and generating a signed Ed25519 license."""
    client_ip = request.client.host if request.client else "unknown"

    try:
        renewal, sub, lic = approve_renewal_request(
            db=db,
            request_id=request_id,
            reviewer_email=user.email,
            ip_address=client_ip,
            plan_id=body.plan_id,
            payment_reference=body.payment_reference,
            amount=body.amount,
            notes=body.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    lic_payload = get_license_download_payload(lic)
    renewal_data = RenewalRequestResponse.model_validate(renewal).model_dump()

    return ApiEnvelope(
        data={
            "renewal_request": renewal_data,
            "license": lic_payload,
            "license_id": lic.license_id,
            "subscription_id": sub.id,
            "new_expiry_date": str(sub.current_period_end),
        },
        message=f"Renewal approved! Subscription extended to {sub.current_period_end} and signed license generated.",
    )


@router.post("/{request_id}/reject", response_model=ApiEnvelope)
def reject_request(
    request_id: int,
    body: RenewalRequestRejectInput,
    request: Request,
    db: Session = Depends(get_db),
    user: VendorUser = Depends(require_role(VendorRole.OWNER, VendorRole.ADMIN)),
):
    """Vendor rejects renewal request with documented reason."""
    client_ip = request.client.host if request.client else "unknown"

    try:
        renewal = reject_renewal_request(
            db=db,
            request_id=request_id,
            reviewer_email=user.email,
            reason=body.reason,
            ip_address=client_ip,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return ApiEnvelope(
        data=RenewalRequestResponse.model_validate(renewal).model_dump(),
        message="Renewal request marked as rejected.",
    )
