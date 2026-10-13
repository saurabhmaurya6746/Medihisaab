"""Vendor users management API endpoints (RBAC: OWNER, ADMIN only)."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from licensing_service.api.schemas import (
    ApiEnvelope,
    UserResponse,
    VendorUserCreateRequest,
    VendorUserStatusRequest,
)
from licensing_service.db.models import VendorRole, VendorUser
from licensing_service.db.session import get_db
from licensing_service.security.auth import get_current_vendor_user, hash_password, require_role
from licensing_service.services.audit import log_audit_event

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=ApiEnvelope)
def list_vendor_users(
    db: Session = Depends(get_db),
    user: VendorUser = Depends(require_role(VendorRole.OWNER, VendorRole.ADMIN)),
):
    """List all vendor portal users."""
    users = db.query(VendorUser).order_by(VendorUser.id.asc()).all()
    data = [UserResponse.model_validate(u).model_dump() for u in users]
    return ApiEnvelope(data=data)


@router.post("", response_model=ApiEnvelope, status_code=status.HTTP_201_CREATED)
def create_vendor_user(
    req: VendorUserCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: VendorUser = Depends(require_role(VendorRole.OWNER, VendorRole.ADMIN)),
):
    """Create a new vendor user account."""
    existing = db.query(VendorUser).filter(VendorUser.email == req.email.strip().lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists.")

    role_val = req.role.strip().upper()
    if role_val not in [r.value for r in VendorRole]:
        raise HTTPException(status_code=400, detail=f"Invalid role: {role_val}")

    new_user = VendorUser(
        full_name=req.full_name.strip(),
        email=req.email.strip().lower(),
        password_hash=hash_password(req.password),
        role=role_val,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    client_ip = request.client.host if request.client else None
    log_audit_event(
        db=db,
        user_email=user.email,
        action="CREATE_VENDOR_USER",
        entity_type="VENDOR_USER",
        entity_id=str(new_user.id),
        ip_address=client_ip,
        metadata={"created_email": new_user.email, "role": new_user.role},
    )

    data = UserResponse.model_validate(new_user)
    return ApiEnvelope(data=data.model_dump(), message="Vendor user created successfully.")


@router.put("/{user_id}/status", response_model=ApiEnvelope)
def update_user_status(
    user_id: int,
    req: VendorUserStatusRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: VendorUser = Depends(require_role(VendorRole.OWNER, VendorRole.ADMIN)),
):
    """Activate or deactivate a vendor user."""
    target_user = db.query(VendorUser).filter(VendorUser.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail=f"Vendor user {user_id} not found.")

    if target_user.id == user.id and not req.is_active:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own user account.")

    target_user.is_active = req.is_active
    db.commit()
    db.refresh(target_user)

    client_ip = request.client.host if request.client else None
    log_audit_event(
        db=db,
        user_email=user.email,
        action="UPDATE_USER_STATUS",
        entity_type="VENDOR_USER",
        entity_id=str(target_user.id),
        ip_address=client_ip,
        metadata={"email": target_user.email, "is_active": req.is_active},
    )

    data = UserResponse.model_validate(target_user)
    return ApiEnvelope(
        data=data.model_dump(),
        message=f"User {'activated' if req.is_active else 'deactivated'} successfully.",
    )
