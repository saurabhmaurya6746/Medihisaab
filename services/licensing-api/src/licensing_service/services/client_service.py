"""Client management service."""

from typing import List, Optional
from sqlalchemy import or_
from sqlalchemy.orm import Session

from licensing_service.db.models import Client, ClientStatus


def generate_next_client_code(db: Session) -> str:
    """Generate next sequential client code e.g. CL-1001, CL-1002."""
    last_client = db.query(Client).order_by(Client.id.desc()).first()
    if not last_client:
        return "CL-1001"
    try:
        if last_client.client_code.startswith("CL-"):
            code_num = int(last_client.client_code.split("-")[1])
            return f"CL-{code_num + 1}"
    except Exception:
        pass
    return f"CL-{last_client.id + 1001}"


def _clean(val: Optional[str]) -> str:
    return val.strip() if isinstance(val, str) else ""


def _clean_or_none(val: Optional[str]) -> Optional[str]:
    return val.strip() if isinstance(val, str) and val.strip() else None


def create_client(db: Session, data: dict) -> Client:
    """Create a new client record with sequential code."""
    if not data.get("client_code"):
        data["client_code"] = generate_next_client_code(db)
    else:
        data["client_code"] = str(data["client_code"]).strip().upper()

    client = Client(
        client_code=_clean(data["client_code"]),
        business_name=_clean(data.get("business_name")),
        owner_name=_clean(data.get("owner_name")),
        phone=_clean(data.get("phone")),
        email=_clean(data.get("email")).lower(),
        address=_clean(data.get("address")),
        city=_clean(data.get("city")),
        state=_clean(data.get("state")),
        postal_code=_clean(data.get("postal_code")),
        gstin=_clean_or_none(data.get("gstin")),
        retail_drug_license=_clean_or_none(data.get("retail_drug_license")),
        wholesale_drug_license=_clean_or_none(data.get("wholesale_drug_license")),
        primary_contact_name=_clean(data.get("primary_contact_name")) or _clean(data.get("owner_name")),
        notes=data.get("notes"),
        status=data.get("status") or ClientStatus.ACTIVE.value,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def update_client(db: Session, client_id: int, data: dict) -> Optional[Client]:
    """Update existing client attributes."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        return None

    for key, value in data.items():
        if hasattr(client, key) and value is not None:
            if isinstance(value, str):
                value = value.strip()
            setattr(client, key, value)

    db.commit()
    db.refresh(client)
    return client


def search_clients(
    db: Session,
    query: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Client]:
    """Search clients by code, business name, phone, email, or city."""
    q = db.query(Client)
    if status:
        q = q.filter(Client.status == status)

    if query:
        term = f"%{query.strip()}%"
        q = q.filter(
            or_(
                Client.client_code.ilike(term),
                Client.business_name.ilike(term),
                Client.owner_name.ilike(term),
                Client.phone.ilike(term),
                Client.email.ilike(term),
                Client.city.ilike(term),
            )
        )

    return q.order_by(Client.id.desc()).offset(offset).limit(limit).all()


def get_client(db: Session, client_id: int) -> Optional[Client]:
    return db.query(Client).filter(Client.id == client_id).first()


def register_client_account(
    db: Session,
    email: str,
    password: str,
    pharmacy_name: str,
    contact_person: str,
    phone: str,
    trial_days: Optional[int] = None,
    client_ip: Optional[str] = None,
):
    """Register customer account, start configurable trial, and issue signed trial license."""
    import secrets
    from licensing_service.security.auth import hash_password
    from licensing_service.services.license_service import issue_license
    from licensing_service.services.subscription_service import start_trial

    clean_email = email.strip().lower() if email else ""
    clean_phone = phone.strip() if phone else ""
    clean_name = pharmacy_name.strip() if pharmacy_name else ""
    clean_contact = contact_person.strip() if contact_person else ""

    if not clean_email or "@" not in clean_email or "." not in clean_email.split("@")[1]:
        raise ValueError("A valid email address is required.")
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if len(clean_name) < 2:
        raise ValueError("Pharmacy name must be at least 2 characters long.")
    if len(clean_contact) < 2:
        raise ValueError("Contact person name must be at least 2 characters long.")
    
    phone_digits = "".join(c for c in clean_phone if c.isdigit())
    if len(phone_digits) < 10:
        raise ValueError("A valid 10-digit mobile phone number is required.")

    # 1. Prevent duplicate normalized email
    existing_by_email = db.query(Client).filter(Client.email.ilike(clean_email)).first()

    # 2. Prevent duplicate normalized phone
    existing_by_phone = None
    target_digits_suffix = phone_digits[-10:]
    for c in db.query(Client).filter(Client.phone.isnot(None)).all():
        c_digits = "".join(ch for ch in (c.phone or "") if ch.isdigit())
        if len(c_digits) >= 10 and c_digits[-10:] == target_digits_suffix:
            existing_by_phone = c
            break

    if existing_by_email:
        from licensing_service.services.audit import log_audit_event
        log_audit_event(
            db=db,
            user_email=clean_email,
            action="TRIAL_SIGNUP_REJECTED_DUPLICATE",
            entity_type="CLIENT",
            entity_id=str(existing_by_email.id),
            ip_address=client_ip,
            metadata={
                "rejected_email": clean_email,
                "duplicate_field": "email",
                "matched_client_code": existing_by_email.client_code,
            },
        )
        raise ValueError("An account with this email address already exists. Please sign in or contact vendor support.")

    if existing_by_phone:
        from licensing_service.services.audit import log_audit_event
        log_audit_event(
            db=db,
            user_email=clean_email,
            action="TRIAL_SIGNUP_REJECTED_DUPLICATE",
            entity_type="CLIENT",
            entity_id=str(existing_by_phone.id),
            ip_address=client_ip,
            metadata={
                "rejected_email": clean_email,
                "duplicate_field": "phone",
                "matched_client_code": existing_by_phone.client_code,
            },
        )
        raise ValueError("A pharmacy account with this phone number is already registered. Please sign in or contact vendor support.")

    client_code = generate_next_client_code(db)
    pwd_hash = hash_password(password)
    verification_token = secrets.token_urlsafe(32)

    client = Client(
        client_code=client_code,
        business_name=clean_name,
        owner_name=clean_contact,
        primary_contact_name=clean_contact,
        phone=clean_phone,
        email=clean_email,
        address="",
        city="",
        state="",
        postal_code="",
        status=ClientStatus.TRIAL.value,
        password_hash=pwd_hash,
        email_verified=True,  # Safe default verification; token also stored for verification workflows
        verification_token=verification_token,
    )
    db.add(client)
    db.commit()
    db.refresh(client)

    # Start default 15-day evaluation trial
    sub = start_trial(db=db, client_id=client.id, trial_days=trial_days)

    # Issue initial signed Ed25519 trial license token
    lic = issue_license(db=db, client_id=client.id, subscription_id=sub.id)

    return client, sub, lic


def authenticate_client(db: Session, email: str, password: str, client_ip: str) -> Client:
    """Authenticate client credentials with sliding window rate limiting."""
    from fastapi import HTTPException, status
    from licensing_service.security.auth import (
        check_login_rate_limit,
        clear_login_attempts,
        record_failed_login_attempt,
        verify_password,
    )

    check_login_rate_limit(client_ip)
    clean_email = email.strip().lower() if email else ""

    client = db.query(Client).filter(Client.email.ilike(clean_email)).first()
    if not client or not client.password_hash or not verify_password(password, client.password_hash):
        record_failed_login_attempt(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    clear_login_attempts(client_ip)

    if client.status in (ClientStatus.SUSPENDED.value, ClientStatus.CLOSED.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is {client.status.lower()}. Please contact vendor support.",
        )

    return client
