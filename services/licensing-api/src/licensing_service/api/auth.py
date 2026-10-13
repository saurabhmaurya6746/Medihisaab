"""Authentication endpoints for vendor users."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from licensing_service.api.schemas import ApiEnvelope, LoginRequest, LoginResponse, UserResponse
from licensing_service.db.models import VendorUser
from licensing_service.db.session import get_db
from licensing_service.security.auth import (
    check_login_rate_limit,
    clear_login_attempts,
    create_access_token,
    get_current_vendor_user,
    record_failed_login_attempt,
    verify_password,
)
from licensing_service.services.audit import log_audit_event

router = APIRouter(prefix="/auth", tags=["Vendor Authentication"])


@router.post("/login", response_model=ApiEnvelope)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Authenticate vendor user and return signed JWT bearer token."""
    client_ip = request.client.host if request.client else "unknown"
    check_login_rate_limit(client_ip)

    user = db.query(VendorUser).filter(VendorUser.email == req.email.lower().strip()).first()
    if not user or not verify_password(req.password, user.password_hash):
        record_failed_login_attempt(client_ip)
        log_audit_event(
            db=db,
            user_email=req.email.lower().strip(),
            action="LOGIN_FAILED",
            entity_type="AUTH",
            ip_address=client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact the system owner.",
        )

    clear_login_attempts(client_ip)
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    token = create_access_token({"sub": str(user.id), "email": user.email, "role": user.role})

    log_audit_event(
        db=db,
        user_email=user.email,
        action="LOGIN_SUCCESS",
        entity_type="AUTH",
        entity_id=str(user.id),
        ip_address=client_ip,
    )

    data = LoginResponse(
        access_token=token,
        token_type="bearer",
        expires_in_minutes=60,
        user=UserResponse(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            last_login_at=user.last_login_at,
        ),
    )
    return ApiEnvelope(data=data.model_dump())


@router.get("/me", response_model=ApiEnvelope)
def get_current_user_profile(user: VendorUser = Depends(get_current_vendor_user)):
    """Return profile details of current authenticated vendor user."""
    data = UserResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
    )
    return ApiEnvelope(data=data.model_dump())
