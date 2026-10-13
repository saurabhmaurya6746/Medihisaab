"""License issuance, management, revocation, and secure download endpoints."""

import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from licensing_service.api.schemas import (
    ApiEnvelope,
    GenerateLicenseRequest,
    LicenseResponse,
)
from licensing_service.db.models import LicenseRecord, VendorRole, VendorUser
from licensing_service.db.session import get_db
from licensing_service.security.auth import get_current_vendor_user, require_role
from licensing_service.services.audit import log_audit_event
from licensing_service.services.license_service import (
    get_license_download_payload,
    issue_license,
    revoke_license,
)

router = APIRouter(prefix="/licenses", tags=["Licenses"])


@router.get("", response_model=ApiEnvelope)
def list_licenses(
    client_id: Optional[int] = Query(None),
    revoked: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: VendorUser = Depends(get_current_vendor_user),
):
    """List issued licenses with client and revocation filters."""
    q = db.query(LicenseRecord)
    if client_id:
        q = q.filter(LicenseRecord.client_id == client_id)
    if revoked is True:
        q = q.filter(LicenseRecord.revoked_at.isnot(None))
    elif revoked is False:
        q = q.filter(LicenseRecord.revoked_at.is_(None))

    records = q.order_by(LicenseRecord.id.desc()).offset(offset).limit(limit).all()
    data = [LicenseResponse.model_validate(l) for l in records]
    return ApiEnvelope(data=[d.model_dump() for d in data])


@router.post("/generate", response_model=ApiEnvelope, status_code=status.HTTP_201_CREATED)
def generate_license_endpoint(
    req: GenerateLicenseRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: VendorUser = Depends(require_role(VendorRole.OWNER, VendorRole.ADMIN)),
):
    """Generate and cryptographically sign an Ed25519 client license (OWNER and ADMIN only)."""
    try:
        record = issue_license(
            db=db,
            client_id=req.client_id,
            subscription_id=req.subscription_id,
            terminal_count=req.terminal_count,
            activation_date=req.activation_date,
            expiry_date=req.expiry_date,
            edition=req.edition,
            enabled_features=req.enabled_features,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    client_ip = request.client.host if request.client else None
    log_audit_event(
        db=db,
        user_email=user.email,
        action="GENERATE_LICENSE",
        entity_type="LICENSE",
        entity_id=record.license_id,
        ip_address=client_ip,
        metadata={
            "client_id": req.client_id,
            "terminals": record.terminal_count,
            "expiry": record.expiry_date,
            "edition": record.edition,
        },
    )

    data = LicenseResponse.model_validate(record)
    return ApiEnvelope(data=data.model_dump(), message="License generated and signed successfully.")


@router.post("/{license_id}/revoke", response_model=ApiEnvelope)
def revoke_license_endpoint(
    license_id: str,
    reason: Optional[str] = Query(None),
    request: Request = None,
    db: Session = Depends(get_db),
    user: VendorUser = Depends(require_role(VendorRole.OWNER, VendorRole.ADMIN)),
):
    """Revoke an issued client license (OWNER and ADMIN only)."""
    try:
        record = revoke_license(db, license_id, reason=reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    client_ip = request.client.host if request and request.client else None
    log_audit_event(
        db=db,
        user_email=user.email,
        action="REVOKE_LICENSE",
        entity_type="LICENSE",
        entity_id=license_id,
        ip_address=client_ip,
        metadata={"reason": reason},
    )

    data = LicenseResponse.model_validate(record)
    return ApiEnvelope(data=data.model_dump(), message="License revoked.")


@router.get("/{license_id}/download")
def download_license_file(
    license_id: str,
    db: Session = Depends(get_db),
    user: VendorUser = Depends(get_current_vendor_user),
):
    """Download signed client license token file (.json) via authenticated vendor session."""
    from sqlalchemy import or_

    lic = None
    if str(license_id).isdigit():
        lic = db.query(LicenseRecord).filter(
            or_(LicenseRecord.id == int(license_id), LicenseRecord.license_id == str(license_id).strip())
        ).first()
    else:
        lic = db.query(LicenseRecord).filter(LicenseRecord.license_id == str(license_id).strip()).first()

    if not lic:
        raise HTTPException(status_code=404, detail=f"License {license_id} not found.")

    payload = get_license_download_payload(lic)
    json_bytes = json.dumps(payload, indent=2).encode("utf-8")

    return Response(
        content=json_bytes,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{lic.license_id}.json"',
            "Cache-Control": "no-store, no-cache, must-revalidate",
        },
    )
