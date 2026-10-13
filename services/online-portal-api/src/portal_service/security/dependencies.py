"""FastAPI dependencies for authentication and authorization."""

from typing import List
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from portal_service.db.models import Customer, PortalStaffUser
from portal_service.db.session import get_db
from portal_service.security.tokens import decode_access_token

security_scheme = HTTPBearer(auto_error=True)
optional_security_scheme = HTTPBearer(auto_error=False)


def get_current_customer(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> Customer:
    """Validate customer JWT and return active customer entity."""
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("user_type") != "CUSTOMER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Customer account required.",
        )

    customer_id = payload.get("sub")
    if not customer_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token payload.",
        )

    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer or not customer.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Customer account not found or suspended.",
        )

    return customer


def get_current_staff(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> PortalStaffUser:
    """Validate staff JWT and return active staff entity."""
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired staff token. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("user_type") != "STAFF":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Staff credentials required.",
        )

    staff_id = payload.get("sub")
    if not staff_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed staff token payload.",
        )

    staff = db.query(PortalStaffUser).filter(PortalStaffUser.id == staff_id).first()
    if not staff or not staff.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Staff account not found or inactive.",
        )

    return staff


def require_roles(allowed_roles: List[str]):
    """Role-based authorization dependency factory for staff endpoints."""

    def role_checker(staff: PortalStaffUser = Depends(get_current_staff)) -> PortalStaffUser:
        if staff.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions: requires one of {allowed_roles}.",
            )
        return staff

    return role_checker
