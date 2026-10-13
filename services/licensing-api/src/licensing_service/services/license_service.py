"""License issuance, renewal, revocation, and cryptographic signing service."""

from datetime import date, datetime, timezone
import secrets
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from licensing_service.db.models import (
    Client,
    LicenseRecord,
    Plan,
    Subscription,
)
from licensing_service.security.signer import signer


def generate_unique_license_id(client_code: str) -> str:
    """Generate a unique human-readable license ID."""
    today_str = date.today().strftime("%Y%m%d")
    rnd_suffix = secrets.token_hex(2).upper()
    clean_code = client_code.replace("-", "").upper()
    return f"LIC-{clean_code}-{today_str}-{rnd_suffix}"


def issue_license(
    db: Session,
    client_id: Optional[int] = None,
    subscription_id: Optional[int] = None,
    terminal_count: Optional[int] = None,
    activation_date: Optional[str] = None,
    expiry_date: Optional[str] = None,
    edition: Optional[str] = None,
    enabled_features: Optional[str] = None,
) -> LicenseRecord:
    """Issue a new Ed25519-signed client license."""
    sub: Optional[Subscription] = None
    if subscription_id:
        sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
        if not sub:
            raise ValueError(f"Subscription {subscription_id} not found.")
        if not client_id:
            client_id = sub.client_id

    if not client_id:
        raise ValueError("client_id or subscription_id must be provided.")

    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise ValueError(f"Client {client_id} not found.")

    act_date = activation_date or date.today().isoformat()

    # Determine expiry date from subscription if not explicitly provided
    exp_date = expiry_date
    grace_days = 0
    if sub and sub.grace_period_end and sub.current_period_end:
        grace_days = max(0, (sub.grace_period_end - sub.current_period_end).days)

    if not exp_date and sub:
        exp_date = sub.current_period_end.isoformat()

    # Determine terminal count
    terms = terminal_count
    if terms is None and sub and sub.plan:
        terms = sub.plan.maximum_terminals
    if terms is None:
        terms = 1

    features = enabled_features
    if not features and sub and sub.plan:
        features = sub.plan.enabled_features
    if not features:
        features = "ALL"

    ed = edition or ("TRIAL" if (sub and sub.plan and sub.plan.plan_code == "TRIAL") else "COMMERCIAL")

    license_id = generate_unique_license_id(client.client_code)

    payload = {
        "client_name": client.business_name.strip(),
        "license_id": license_id,
        "terminal_count": int(terms),
        "activation_date": act_date,
        "expiry_date": exp_date,
        "edition": ed,
        "features": features,
        "grace_period_days": grace_days,
        "version": 2,
    }

    # Generate Ed25519 digital signature
    signature_hex = signer.sign_license(payload)

    record = LicenseRecord(
        client_id=client.id,
        subscription_id=sub.id if sub else None,
        license_id=license_id,
        client_name=client.business_name.strip(),
        terminal_count=int(terms),
        activation_date=act_date,
        expiry_date=exp_date,
        edition=ed,
        enabled_features=features,
        version=payload.get("version", 2),
        grace_period_days=grace_days,
        signature=signature_hex,
        issued_at=datetime.now(timezone.utc),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def revoke_license(db: Session, license_id: str, reason: Optional[str] = None) -> LicenseRecord:
    """Revoke an issued license."""
    from sqlalchemy import or_

    lic = None
    if str(license_id).isdigit():
        lic = db.query(LicenseRecord).filter(
            or_(LicenseRecord.id == int(license_id), LicenseRecord.license_id == str(license_id).strip())
        ).first()
    else:
        lic = db.query(LicenseRecord).filter(LicenseRecord.license_id == str(license_id).strip()).first()

    if not lic:
        raise ValueError(f"License {license_id} not found.")

    if lic.revoked_at:
        return lic  # Already revoked

    lic.revoked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(lic)
    return lic


def get_license_download_payload(lic: LicenseRecord) -> Dict[str, Any]:
    """Format license record into the JSON token structure expected by Pharmacy POS."""
    version = getattr(lic, "version", 2) or 2
    grace = getattr(lic, "grace_period_days", 0) or 0
    if not grace and lic.subscription and lic.subscription.grace_period_end and lic.subscription.current_period_end:
        grace = max(0, (lic.subscription.grace_period_end - lic.subscription.current_period_end).days)

    data = {
        "client_name": lic.client_name,
        "license_id": lic.license_id,
        "terminal_count": lic.terminal_count,
        "activation_date": lic.activation_date,
        "expiry_date": lic.expiry_date,
        "edition": lic.edition,
        "features": lic.enabled_features,
        "signature": lic.signature,
        "version": version,
        "grace_period_days": grace,
    }
    return data


def list_client_licenses(db: Session, client_id: int) -> List[LicenseRecord]:
    return (
        db.query(LicenseRecord)
        .filter(LicenseRecord.client_id == client_id)
        .order_by(LicenseRecord.id.desc())
        .all()
    )
