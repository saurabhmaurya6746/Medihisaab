"""Staff authentication and profile endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from portal_service.db.models import PortalStaffUser
from portal_service.db.session import get_db
from portal_service.security.dependencies import get_current_staff
from portal_service.security.password import verify_password
from portal_service.security.tokens import create_access_token
from portal_service.schemas import (
    StaffAuthResponse,
    StaffLoginRequest,
    StaffProfileResponse,
)

router = APIRouter(prefix="/staff", tags=["Staff Auth"])


@router.post("/login", response_model=StaffAuthResponse)
def login_staff(payload: StaffLoginRequest, db: Session = Depends(get_db)):
    """Authenticate pharmacy staff member (ADMIN, PHARMACIST, STAFF)."""
    clean_email = payload.email.lower().strip()
    user = db.query(PortalStaffUser).filter(PortalStaffUser.email == clean_email).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid staff email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff account is deactivated.",
        )

    token = create_access_token(
        subject=user.id,
        role=user.role,
        user_type="STAFF",
        extra_claims={"email": user.email, "name": user.full_name},
    )

    staff_profile = StaffProfileResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
    )

    return StaffAuthResponse(
        access_token=token,
        token_type="bearer",
        staff=staff_profile,
    )


@router.get("/me", response_model=StaffProfileResponse)
def get_staff_profile(current_staff: PortalStaffUser = Depends(get_current_staff)):
    """Retrieve profile and role information for currently signed-in staff."""
    return StaffProfileResponse(
        id=current_staff.id,
        email=current_staff.email,
        full_name=current_staff.full_name,
        role=current_staff.role,
        is_active=current_staff.is_active,
        created_at=current_staff.created_at,
    )
