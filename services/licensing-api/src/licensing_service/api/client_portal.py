"""Client Portal API: customer registration, 15-day evaluation trial,
dashboard, installer/license downloads, and monthly renewal payments.
Strict tenant isolation: each client accesses only their own account records.
"""

from datetime import date, datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from licensing_service.api.schemas import (
    ApiEnvelope,
    ClientAuthResponse,
    ClientDashboardResponse,
    ClientPaymentSubmitRequest,
    ClientResponse,
    ClientSignupRequest,
    EmailVerifyRequest,
    LicenseResponse,
    LoginRequest,
    PaymentResponse,
    PlanResponse,
    RefreshTokenRequest,
    RenewalRequestCreateInput,
    RenewalRequestResponse,
    SubscriptionResponse,
    SupportContactsResponse,
)
from licensing_service.db.models import Client, LicenseRecord, Payment, Plan, RenewalRequest, Subscription
from licensing_service.db.session import get_db
from licensing_service.security.auth import (
    check_renewal_rate_limit,
    check_signup_rate_limit,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    get_current_client,
    record_renewal_attempt,
    record_signup_attempt,
    security_bearer,
)
from fastapi.security import HTTPAuthorizationCredentials
from licensing_service.services.audit import log_audit_event
from licensing_service.services.client_service import (
    authenticate_client,
    register_client_account,
)
from licensing_service.services.license_service import get_license_download_payload
from licensing_service.services.payment_service import submit_client_payment
from licensing_service.services.renewal_service import create_renewal_request
from licensing_service.services.setting_service import get_support_contacts
from licensing_service.services.subscription_service import evaluate_subscription_status

router = APIRouter(prefix="/client", tags=["Client Portal"])


# 1. AUTHENTICATION & SIGNUP
@router.post("/auth/signup", response_model=ApiEnvelope, status_code=status.HTTP_201_CREATED)
@router.post("/signup", response_model=ApiEnvelope, status_code=status.HTTP_201_CREATED)
def client_signup(
    req: ClientSignupRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Customer registration: creates account, activates configurable trial, and returns signed trial license."""
    client_ip = request.client.host if request.client else "unknown"

    check_signup_rate_limit(client_ip)
    record_signup_attempt(client_ip)

    pharm_name = req.pharmacy_name or req.business_name or "Retail Pharmacy"
    contact = req.contact_person or req.owner_name or "Store Owner"

    try:
        client, sub, lic = register_client_account(
            db=db,
            email=req.email,
            password=req.password,
            pharmacy_name=pharm_name,
            contact_person=contact,
            phone=req.phone,
            client_ip=client_ip,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # Create client JWT access token and refresh token
    token = create_access_token({
        "sub": str(client.id),
        "client_id": client.id,
        "client_code": client.client_code,
        "email": client.email,
        "type": "client",
    })
    refresh_token = create_refresh_token({
        "sub": str(client.id),
        "client_id": client.id,
        "client_code": client.client_code,
        "email": client.email,
        "type": "client",
    })

    lic_token_payload = get_license_download_payload(lic)

    log_audit_event(
        db=db,
        user_email=client.email,
        action="CLIENT_SIGNUP",
        entity_type="CLIENT",
        entity_id=str(client.id),
        ip_address=client_ip,
        metadata={
            "client_code": client.client_code,
            "pharmacy_name": client.business_name,
            "trial_days": sub.trial_days,
            "license_id": lic.license_id,
        },
    )

    auth_data = ClientAuthResponse(
        access_token=token,
        refresh_token=refresh_token,
        token_type="bearer",
        client=ClientResponse.model_validate(client),
        business_name=client.business_name,
        owner_name=client.owner_name,
        email=client.email,
        trial_days=sub.trial_days or 15,
        subscription_status=sub.status,
        license_token=lic_token_payload,
    )
    return ApiEnvelope(
        data=auth_data.model_dump(),
        message=f"Account created successfully. Your {sub.trial_days}-day evaluation trial is active.",
    )


@router.post("/auth/login", response_model=ApiEnvelope)
@router.post("/login", response_model=ApiEnvelope)
def client_login(
    req: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Client authentication using normalized email and password with brute-force rate limiting."""
    client_ip = request.client.host if request.client else "unknown"

    client = authenticate_client(db=db, email=req.email, password=req.password, client_ip=client_ip)

    token = create_access_token({
        "sub": str(client.id),
        "client_id": client.id,
        "client_code": client.client_code,
        "email": client.email,
        "type": "client",
    })
    refresh_token = create_refresh_token({
        "sub": str(client.id),
        "client_id": client.id,
        "client_code": client.client_code,
        "email": client.email,
        "type": "client",
    })

    # Find latest subscription status
    latest_sub = (
        db.query(Subscription)
        .filter(Subscription.client_id == client.id)
        .order_by(Subscription.id.desc())
        .first()
    )
    sub_status = evaluate_subscription_status(latest_sub) if latest_sub else "INACTIVE"

    # Find latest active license to return to desktop client
    latest_lic = (
        db.query(LicenseRecord)
        .filter(LicenseRecord.client_id == client.id, LicenseRecord.revoked_at.is_(None))
        .order_by(LicenseRecord.id.desc())
        .first()
    )
    lic_token_payload = get_license_download_payload(latest_lic) if latest_lic else None

    log_audit_event(
        db=db,
        user_email=client.email,
        action="CLIENT_LOGIN",
        entity_type="CLIENT",
        entity_id=str(client.id),
        ip_address=client_ip,
        metadata={"client_code": client.client_code},
    )

    auth_data = ClientAuthResponse(
        access_token=token,
        refresh_token=refresh_token,
        token_type="bearer",
        client=ClientResponse.model_validate(client),
        business_name=client.business_name,
        owner_name=client.owner_name,
        email=client.email,
        trial_days=latest_sub.trial_days if latest_sub else 15,
        subscription_status=sub_status,
        license_token=lic_token_payload,
    )
    return ApiEnvelope(data=auth_data.model_dump(), message="Login successful.")


@router.post("/auth/refresh", response_model=ApiEnvelope)
@router.post("/refresh", response_model=ApiEnvelope)
def client_refresh_session(
    req: Optional[RefreshTokenRequest] = None,
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db),
):
    """Securely refresh an expired client session token using a refresh token or client bearer token."""
    raw_token = (req.refresh_token if req and req.refresh_token else None) or (auth.credentials if auth else None)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session refresh credentials required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(raw_token)
    if payload.get("type") != "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Customer client access token required.",
        )

    client_id = payload.get("client_id") or payload.get("sub")
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject.",
        )

    client = db.query(Client).filter(Client.id == int(client_id)).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Client account not found.",
        )

    if client.status in ("SUSPENDED", "CLOSED"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is {client.status.lower()}. Please contact vendor support.",
        )

    new_access = create_access_token({
        "sub": str(client.id),
        "client_id": client.id,
        "client_code": client.client_code,
        "email": client.email,
        "type": "client",
    })
    new_refresh = create_refresh_token({
        "sub": str(client.id),
        "client_id": client.id,
        "client_code": client.client_code,
        "email": client.email,
        "type": "client",
    })

    return ApiEnvelope(
        data={
            "access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "bearer",
            "client_id": client.id,
            "business_name": client.business_name,
            "owner_name": client.owner_name,
            "email": client.email,
        },
        message="Client session token refreshed successfully.",
    )


@router.post("/auth/verify-email", response_model=ApiEnvelope)
def verify_email(
    req: EmailVerifyRequest,
    db: Session = Depends(get_db),
):
    """Safe email verification token endpoint."""
    token = req.token.strip()
    client = db.query(Client).filter(Client.verification_token == token).first()
    if not client:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification token.")

    client.email_verified = True
    client.verification_token = None
    db.commit()
    return ApiEnvelope(data={"verified": True}, message="Email address verified successfully.")


# 2. PROFILE & DASHBOARD
@router.get("/me", response_model=ApiEnvelope)
def get_me(current_client: Client = Depends(get_current_client)):
    """Retrieve current client account details."""
    data = ClientResponse.model_validate(current_client)
    return ApiEnvelope(data=data.model_dump())


@router.get("/dashboard", response_model=ApiEnvelope)
def get_dashboard(
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db),
):
    """Retrieve comprehensive customer dashboard with trial/subscription state, license, and payments."""
    today = date.today()

    # 1. Fetch current subscription
    sub = (
        db.query(Subscription)
        .filter(Subscription.client_id == current_client.id)
        .order_by(Subscription.id.desc())
        .first()
    )

    sub_status = "INACTIVE"
    days_remaining: Optional[int] = None
    grace_active = False
    max_terminals = 1

    if sub:
        sub_status = evaluate_subscription_status(sub)
        sub.status = sub_status
        if sub.plan:
            max_terminals = sub.plan.maximum_terminals

        if today <= sub.current_period_end:
            days_remaining = (sub.current_period_end - today).days
            grace_active = False
        elif today <= sub.grace_period_end:
            days_remaining = max(0, (sub.grace_period_end - today).days)
            grace_active = True
        else:
            days_remaining = 0
            grace_active = False

    # 2. Fetch latest active license
    lic = (
        db.query(LicenseRecord)
        .filter(LicenseRecord.client_id == current_client.id, LicenseRecord.revoked_at.is_(None))
        .order_by(LicenseRecord.id.desc())
        .first()
    )

    lic_token_payload = None
    if lic:
        lic_token_payload = get_license_download_payload(lic)

    # 3. Fetch recent payments
    payments = (
        db.query(Payment)
        .filter(Payment.client_id == current_client.id)
        .order_by(Payment.id.desc())
        .limit(10)
        .all()
    )

    dashboard = ClientDashboardResponse(
        client=ClientResponse.model_validate(current_client),
        subscription=SubscriptionResponse.model_validate(sub) if sub else None,
        active_license=LicenseResponse.model_validate(lic) if lic else None,
        license_token=lic_token_payload,
        days_remaining=days_remaining,
        grace_period_active=grace_active,
        status=sub_status,
        maximum_terminals=max_terminals,
        last_refreshed=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        can_renew=True,
        recent_payments=[PaymentResponse.model_validate(p) for p in payments],
    )
    return ApiEnvelope(data=dashboard.model_dump())


# 3. LICENSE DOWNLOAD
@router.get("/license/download")
def download_license(
    request: Request,
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db),
):
    """Securely download current active signed Ed25519 client license token (.json)."""
    lic = (
        db.query(LicenseRecord)
        .filter(LicenseRecord.client_id == current_client.id, LicenseRecord.revoked_at.is_(None))
        .order_by(LicenseRecord.id.desc())
        .first()
    )
    if not lic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active license found for this client account.",
        )

    payload = get_license_download_payload(lic)
    filename = f"{lic.license_id}.json"
    content = json.dumps(payload, indent=2)

    client_ip = request.client.host if request.client else "unknown"
    log_audit_event(
        db=db,
        user_email=current_client.email,
        action="CLIENT_LICENSE_DOWNLOAD",
        entity_type="LICENSE",
        entity_id=lic.license_id,
        ip_address=client_ip,
        metadata={
            "client_code": current_client.client_code,
            "license_id": lic.license_id,
            "filename": filename,
        },
    )

    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# 4. AVAILABLE RENEWAL PLANS
@router.get("/plans", response_model=ApiEnvelope)
def get_renewal_plans(db: Session = Depends(get_db)):
    """List commercial plans available for subscription renewal (Monthly default, Annual options)."""
    plans = (
        db.query(Plan)
        .filter(Plan.is_active == True, Plan.plan_code != "TRIAL")
        .order_by(Plan.price.asc())
        .all()
    )
    data = [PlanResponse.model_validate(p).model_dump() for p in plans]
    return ApiEnvelope(data=data)


# 5. PAYMENT SUBMISSION (PENDING REVIEW)
@router.post("/payments/submit", response_model=ApiEnvelope, status_code=status.HTTP_201_CREATED)
def submit_payment(
    req: ClientPaymentSubmitRequest,
    request: Request,
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db),
):
    """Client submits manual payment reference/UTR for review. Marked PENDING until vendor confirmation."""
    client_ip = request.client.host if request.client else "unknown"

    target_plan_id = req.plan_id
    if not target_plan_id and req.plan_code:
        plan = db.query(Plan).filter(Plan.plan_code == req.plan_code).first()
        if plan:
            target_plan_id = plan.id

    try:
        payment = submit_client_payment(
            db=db,
            client_id=current_client.id,
            amount=req.amount,
            payment_reference=req.payment_reference,
            plan_id=target_plan_id,
            payment_method=req.payment_method,
            notes=req.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    log_audit_event(
        db=db,
        user_email=current_client.email,
        action="CLIENT_PAYMENT_SUBMITTED",
        entity_type="PAYMENT",
        entity_id=str(payment.id),
        ip_address=client_ip,
        metadata={
            "client_code": current_client.client_code,
            "amount": req.amount,
            "ref": req.payment_reference,
            "plan_id": target_plan_id,
        },
    )

    data = PaymentResponse.model_validate(payment)
    return ApiEnvelope(
        data=data.model_dump(),
        message="Payment submitted for review. Your subscription will be extended upon vendor confirmation.",
    )


@router.get("/payments", response_model=ApiEnvelope)
def list_client_payments(
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db),
):
    """List payment transactions submitted by this client (tenant-isolated)."""
    payments = (
        db.query(Payment)
        .filter(Payment.client_id == current_client.id)
        .order_by(Payment.id.desc())
        .all()
    )
    data = [PaymentResponse.model_validate(p).model_dump() for p in payments]
    return ApiEnvelope(data=data)


# 6. DOWNLOADS AREA
@router.get("/downloads", response_model=ApiEnvelope)
def list_available_downloads(current_client: Client = Depends(get_current_client)):
    """List verified software installer and official documentation guides."""
    downloads = [
        {
            "id": "installer-windows",
            "title": "MediHisaab Windows Installer (v1.0.0)",
            "filename": "MediHisaab-Setup-1.0.0.exe",
            "file_size": "91.0 MB (95,442,984 bytes)",
            "os": "Windows 10 / 11 (64-bit)",
            "download_url": "/MediHisaab-Setup-1.0.0.exe",
            "sha256": "2e323e4b90768f866699b24c2aad6ba36f201e092acd65ba8cf6010b0f91c02f",
            "is_installer": True,
            "description": "Standalone offline-first MediHisaab installer with embedded Python, SQLite WAL engine, ESC/POS printing, and LAN multi-counter support.",
        },
        {
            "id": "doc-installation",
            "title": "Installation & First-Run Setup Guide",
            "filename": "FIRST_RUN_SETUP.md",
            "file_size": "3.2 KB",
            "os": "All",
            "download_url": "#docs-install",
            "is_installer": False,
            "description": "Step-by-step instructions for initial store setup and drug license registration.",
        },
        {
            "id": "doc-lan",
            "title": "Multi-Counter LAN Setup Guide",
            "filename": "LAN_SETUP_GUIDE.md",
            "file_size": "4.1 KB",
            "os": "All",
            "download_url": "#docs-lan",
            "is_installer": False,
            "description": "Instructions for connecting multiple counter terminals over local Wi-Fi or Ethernet.",
        },
        {
            "id": "doc-backup",
            "title": "Disaster Recovery & Hot Backup Guide",
            "filename": "BACKUP_RESTORE_GUIDE.md",
            "file_size": "3.9 KB",
            "os": "All",
            "download_url": "#docs-backup",
            "is_installer": False,
            "description": "Guidelines for creating automated and manual hot SQLite database snapshots.",
        },
    ]
    return ApiEnvelope(data=downloads)


@router.post("/downloads/{item_id}/request", response_model=ApiEnvelope)
@router.post("/downloads/request", response_model=ApiEnvelope)
def record_download_request(
    item_id: str = "installer-windows",
    request: Request = None,
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db),
):
    """Record an authenticated client download request in audit log and return verified download metadata."""
    client_ip = request.client.host if request and request.client else "unknown"
    log_audit_event(
        db=db,
        user_email=current_client.email,
        action="CLIENT_DOWNLOAD_REQUEST",
        entity_type="DOWNLOAD",
        entity_id=item_id,
        ip_address=client_ip,
        metadata={
            "client_code": current_client.client_code,
            "pharmacy_name": current_client.business_name,
            "item_id": item_id,
            "filename": "MediHisaab-Setup-1.0.0.exe" if "installer" in item_id else item_id,
            "version": "1.0.0",
        },
    )
    return ApiEnvelope(
        data={
            "item_id": item_id,
            "recorded": True,
            "download_url": "/MediHisaab-Setup-1.0.0.exe",
            "filename": "MediHisaab-Setup-1.0.0.exe",
            "version": "1.0.0",
            "sha256": "2e323e4b90768f866699b24c2aad6ba36f201e092acd65ba8cf6010b0f91c02f",
            "file_size": "91.0 MB (95,442,984 bytes)",
        },
        message="Installer download request recorded.",
    )


# 7. IN-APP LICENSE RENEWAL REQUESTS
@router.post("/renewal-requests", response_model=ApiEnvelope, status_code=status.HTTP_201_CREATED)
def submit_in_app_renewal_request(
    req: RenewalRequestCreateInput,
    request: Request,
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db),
):
    """Client submits an in-app license renewal request from the desktop app or portal.

    Requires an active, authenticated client session token (401/403 enforced).
    Pharmacy owner and store identity are strictly derived from the authenticated account record.
    Creates an auditable renewal request with rate limiting and attempts email dispatch.
    """
    client_ip = request.client.host if request.client else "unknown"

    # Enforce client-level renewal rate limiting
    check_renewal_rate_limit(str(current_client.id))
    record_renewal_attempt(str(current_client.id))

    store_name = current_client.business_name
    contact_name = current_client.owner_name or current_client.primary_contact_name
    email = current_client.email
    phone = current_client.phone

    try:
        renewal = create_renewal_request(
            db=db,
            client_id=current_client.id,
            store_name=store_name,
            contact_name=contact_name,
            email=email,
            phone=phone,
            requested_plan_code=req.requested_plan_code or "MONTHLY_STANDARD",
            payment_reference=req.payment_reference,
            payment_amount=req.payment_amount or 0,
            notes=req.notes,
            ip_address=client_ip,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    data = RenewalRequestResponse.model_validate(renewal).model_dump(mode="json")
    data["vendor_notified"] = renewal.vendor_notification_sent
    msg = (
        f"Renewal request #{renewal.id} submitted successfully. Vendor has been notified via email."
        if renewal.vendor_notification_sent
        else f"Renewal request #{renewal.id} recorded in vendor system. Our team will review and contact you."
    )

    return ApiEnvelope(success=True, data=data, message=msg)


@router.get("/renewal-requests", response_model=ApiEnvelope)
def list_my_renewal_requests(
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db),
):
    """Retrieve all license renewal requests submitted by the current authenticated client (tenant-isolated)."""
    requests = (
        db.query(RenewalRequest)
        .filter(RenewalRequest.client_id == current_client.id)
        .order_by(RenewalRequest.id.desc())
        .all()
    )
    data = [RenewalRequestResponse.model_validate(r).model_dump() for r in requests]
    return ApiEnvelope(data=data)


# 8. SUPPORT CONTACTS
@router.get("/support-contacts", response_model=ApiEnvelope)
def get_vendor_support_contacts(db: Session = Depends(get_db)):
    """Retrieve public vendor support details (phone, WhatsApp, and email)."""
    contacts = get_support_contacts(db)
    data = SupportContactsResponse(
        phone=contacts.get("phone", "+91 98765 43210"),
        whatsapp=contacts.get("whatsapp", "+91 98765 43210"),
        email=contacts.get("email", "support@apexhealth.com"),
    )
    return ApiEnvelope(data=data.model_dump())
