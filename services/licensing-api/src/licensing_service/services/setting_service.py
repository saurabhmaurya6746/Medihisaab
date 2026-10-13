"""System settings management service (configurable trial durations, grace periods, etc.)."""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from licensing_service.db.models import SystemSetting


def get_setting(db: Session, key: str, default: str = "") -> str:
    """Retrieve raw string setting by key."""
    s = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    return s.value if s else default


def get_int_setting(db: Session, key: str, default: int = 0) -> int:
    """Retrieve integer setting with safe fallback."""
    val = get_setting(db, key, str(default))
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def set_setting(
    db: Session,
    key: str,
    value: str,
    description: Optional[str] = None,
) -> SystemSetting:
    """Create or update a system setting."""
    s = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if s:
        s.value = str(value).strip()
        if description:
            s.description = description
        s.updated_at = datetime.now(timezone.utc)
    else:
        s = SystemSetting(
            key=key.strip(),
            value=str(value).strip(),
            description=description,
        )
        db.add(s)

    db.commit()
    db.refresh(s)
    return s


def list_settings(db: Session) -> List[SystemSetting]:
    """Retrieve all configurable system settings."""
    return db.query(SystemSetting).order_by(SystemSetting.key.asc()).all()


def get_default_trial_days(db: Session) -> int:
    """Retrieve vendor-configured default trial duration (default: 15 days)."""
    return get_int_setting(db, "default_trial_days", default=15)


def get_default_grace_days(db: Session) -> int:
    """Retrieve vendor-configured default grace period (default: 7 days)."""
    return get_int_setting(db, "default_grace_days", default=7)


def get_support_contacts(db: Session) -> Dict[str, str]:
    """Retrieve vendor support contacts for client app and public display."""
    return {
        "phone": get_setting(db, "support_phone", "+91 98765 43210"),
        "whatsapp": get_setting(db, "support_whatsapp", "+91 98765 43210"),
        "email": get_setting(db, "support_email", "support@apexhealth.com"),
        "vendor_notification_email": get_setting(db, "vendor_notification_email", "vendor@apexhealth.com"),
    }


def set_support_contacts(
    db: Session,
    phone: Optional[str] = None,
    whatsapp: Optional[str] = None,
    email: Optional[str] = None,
    vendor_notification_email: Optional[str] = None,
) -> Dict[str, str]:
    """Update vendor support contact details."""
    if phone:
        set_setting(db, "support_phone", phone.strip(), "Vendor customer support telephone number.")
    if whatsapp:
        set_setting(db, "support_whatsapp", whatsapp.strip(), "Vendor support WhatsApp contact number.")
    if email:
        set_setting(db, "support_email", email.strip().lower(), "Vendor customer support email address.")
    if vendor_notification_email:
        set_setting(db, "vendor_notification_email", vendor_notification_email.strip().lower(), "Recipient email for renewal alerts.")

    return get_support_contacts(db)
