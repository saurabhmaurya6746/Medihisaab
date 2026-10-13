"""Customer registration, authentication, and profile management."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from portal_service.db.models import Customer
from portal_service.db.session import get_db
from portal_service.security.dependencies import get_current_customer
from portal_service.security.password import hash_password, verify_password
from portal_service.security.tokens import create_access_token
from portal_service.schemas import (
    CustomerAuthResponse,
    CustomerLoginRequest,
    CustomerProfileResponse,
    CustomerRegisterRequest,
    CustomerUpdateProfileRequest,
)

router = APIRouter(prefix="/customer", tags=["Customer Auth & Profile"])


@router.post("/register", response_model=CustomerAuthResponse, status_code=status.HTTP_201_CREATED)
def register_customer(payload: CustomerRegisterRequest, db: Session = Depends(get_db)):
    """Register a new customer account."""
    clean_email = payload.email.lower().strip()
    existing = db.query(Customer).filter(Customer.email == clean_email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address is already registered. Please sign in.",
        )

    customer = Customer(
        email=clean_email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        phone=payload.phone.strip(),
        delivery_address=(payload.delivery_address or "").strip(),
        is_active=True,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)

    token = create_access_token(
        subject=customer.id,
        role="CUSTOMER",
        user_type="CUSTOMER",
        extra_claims={"email": customer.email, "name": customer.full_name},
    )

    profile = CustomerProfileResponse(
        id=customer.id,
        email=customer.email,
        full_name=customer.full_name,
        phone=customer.phone,
        delivery_address=customer.delivery_address,
        created_at=customer.created_at,
    )

    return CustomerAuthResponse(
        access_token=token,
        token_type="bearer",
        customer=profile,
    )


@router.post("/login", response_model=CustomerAuthResponse)
def login_customer(payload: CustomerLoginRequest, db: Session = Depends(get_db)):
    """Sign in an existing customer."""
    clean_email = payload.email.lower().strip()
    customer = db.query(Customer).filter(Customer.email == clean_email).first()

    if not customer or not verify_password(payload.password, customer.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not customer.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This customer account has been suspended. Please contact pharmacy support.",
        )

    token = create_access_token(
        subject=customer.id,
        role="CUSTOMER",
        user_type="CUSTOMER",
        extra_claims={"email": customer.email, "name": customer.full_name},
    )

    profile = CustomerProfileResponse(
        id=customer.id,
        email=customer.email,
        full_name=customer.full_name,
        phone=customer.phone,
        delivery_address=customer.delivery_address,
        created_at=customer.created_at,
    )

    return CustomerAuthResponse(
        access_token=token,
        token_type="bearer",
        customer=profile,
    )


@router.get("/me", response_model=CustomerProfileResponse)
def get_customer_profile(current_customer: Customer = Depends(get_current_customer)):
    """Retrieve currently authenticated customer profile."""
    return CustomerProfileResponse(
        id=current_customer.id,
        email=current_customer.email,
        full_name=current_customer.full_name,
        phone=current_customer.phone,
        delivery_address=current_customer.delivery_address,
        created_at=current_customer.created_at,
    )


@router.put("/me", response_model=CustomerProfileResponse)
def update_customer_profile(
    payload: CustomerUpdateProfileRequest,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    """Update profile information (full name, phone, delivery address)."""
    if payload.full_name is not None:
        current_customer.full_name = payload.full_name.strip()
    if payload.phone is not None:
        current_customer.phone = payload.phone.strip()
    if payload.delivery_address is not None:
        current_customer.delivery_address = payload.delivery_address.strip()

    db.commit()
    db.refresh(current_customer)

    return CustomerProfileResponse(
        id=current_customer.id,
        email=current_customer.email,
        full_name=current_customer.full_name,
        phone=current_customer.phone,
        delivery_address=current_customer.delivery_address,
        created_at=current_customer.created_at,
    )
