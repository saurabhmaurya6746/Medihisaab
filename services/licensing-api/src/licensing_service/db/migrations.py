"""Database migrations, schema creation, and default seed data."""

import logging
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from licensing_service.db.session import engine, Base
from licensing_service.db.models import (
    VendorUser,
    VendorRole,
    Plan,
    BillingPeriod,
)

logger = logging.getLogger("licensing_service.db.migrations")
pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def init_db():
    """Create all tables in the target database (PostgreSQL or SQLite)."""
    logger.info("Initializing licensing database schema...")
    Base.metadata.create_all(bind=engine)

    # Safe migration for new columns on existing database files
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        if "licenses" in inspector.get_table_names():
            columns = [c["name"] for c in inspector.get_columns("licenses")]
            with engine.connect() as conn:
                if "version" not in columns:
                    conn.execute(text("ALTER TABLE licenses ADD COLUMN version INTEGER DEFAULT 2 NOT NULL;"))
                    conn.commit()
                if "grace_period_days" not in columns:
                    conn.execute(text("ALTER TABLE licenses ADD COLUMN grace_period_days INTEGER DEFAULT 0 NOT NULL;"))
                    conn.commit()
    except Exception as exc:
        logger.debug("Column migration skipped or already applied: %s", exc)

    logger.info("Database schema initialized successfully.")


def seed_default_data(db: Session) -> None:
    """Seed initial OWNER account and default subscription plans if empty."""
    # 1. Seed Owner User if no users exist
    existing_user = db.query(VendorUser).first()
    if not existing_user:
        logger.info("Seeding default OWNER user for vendor portal...")
        owner = VendorUser(
            full_name="Software Vendor Administrator",
            email="owner@apexhealth.local",
            password_hash=hash_password("OwnerSecurePass2026!"),
            role=VendorRole.OWNER.value,
            is_active=True,
        )
        db.add(owner)
        db.commit()
        logger.info("Default OWNER seeded: owner@apexhealth.local")

    # 2. Seed Default Plans if missing
    monthly_plan = db.query(Plan).filter(Plan.plan_code == "MONTHLY_STANDARD").first()
    if not monthly_plan:
        db.add(
            Plan(
                plan_code="MONTHLY_STANDARD",
                name="Monthly Standard Commercial",
                description="Monthly subscription for retail pharmacies with up to 2 counters.",
                billing_period=BillingPeriod.MONTHLY.value,
                price=59900,  # ₹599.00 / month
                currency="INR",
                maximum_terminals=2,
                enabled_features="ALL",
                is_active=True,
            )
        )
        db.commit()

    plan_count = db.query(Plan).count()
    if plan_count <= 1:
        logger.info("Seeding standard subscription plans...")
        default_plans = [
            Plan(
                plan_code="TRIAL",
                name="Trial Plan (15 Days)",
                description="15-day fully featured evaluation license for prospective pharmacy clients.",
                billing_period=BillingPeriod.TRIAL.value,
                price=0,
                currency="INR",
                maximum_terminals=2,
                enabled_features="ALL",
                is_active=True,
            ),
            Plan(
                plan_code="SINGLE_COUNTER",
                name="Single Counter Standard",
                description="Annual license for standalone single-workstation retail pharmacies.",
                billing_period=BillingPeriod.ANNUAL.value,
                price=600000,  # ₹6,000.00
                currency="INR",
                maximum_terminals=1,
                enabled_features="ALL",
                is_active=True,
            ),
            Plan(
                plan_code="MULTI_COUNTER",
                name="Multi-Counter LAN Commercial",
                description="Annual license for pharmacies operating up to 5 concurrent LAN billing counters.",
                billing_period=BillingPeriod.ANNUAL.value,
                price=1500000,  # ₹15,000.00
                currency="INR",
                maximum_terminals=5,
                enabled_features="ALL",
                is_active=True,
            ),
            Plan(
                plan_code="ANNUAL_STANDARD",
                name="Annual Standard Commercial",
                description="Annual subscription for retail pharmacies with up to 2 counters.",
                billing_period=BillingPeriod.ANNUAL.value,
                price=599000,  # ₹5,990.00
                currency="INR",
                maximum_terminals=2,
                enabled_features="ALL",
                is_active=True,
            ),
            Plan(
                plan_code="ANNUAL_COMMERCIAL",
                name="Enterprise Pharmacy Suite",
                description="Comprehensive commercial license for high-volume pharmacies with up to 20 counters.",
                billing_period=BillingPeriod.ANNUAL.value,
                price=3500000,  # ₹35,000.00
                currency="INR",
                maximum_terminals=20,
                enabled_features="ALL",
                is_active=True,
            ),
        ]
        db.add_all(default_plans)
        db.commit()
        logger.info("Seeded %d standard subscription plans.", len(default_plans))

    # 3. Seed Default System Settings if not present
    from licensing_service.db.models import SystemSetting
    trial_setting = db.query(SystemSetting).filter(SystemSetting.key == "default_trial_days").first()
    if not trial_setting:
        logger.info("Seeding default system settings (default_trial_days=15)...")
        settings_to_seed = [
            SystemSetting(
                key="default_trial_days",
                value="15",
                description="Default evaluation trial period in days for new pharmacy clients.",
            ),
            SystemSetting(
                key="default_grace_days",
                value="7",
                description="Default grace period in days before commercial restrictions apply.",
            ),
            SystemSetting(
                key="support_phone",
                value="+91 98765 43210",
                description="Vendor customer support telephone number.",
            ),
            SystemSetting(
                key="support_whatsapp",
                value="+91 98765 43210",
                description="Vendor support WhatsApp contact number.",
            ),
            SystemSetting(
                key="support_email",
                value="support@apexhealth.local",
                description="Vendor customer support email address.",
            ),
            SystemSetting(
                key="vendor_notification_email",
                value="vendor@apexhealth.local",
                description="Recipient email address for license renewal and trial activation alerts.",
            ),
        ]
        db.add_all(settings_to_seed)
        db.commit()
        logger.info("Seeded system settings successfully.")
    else:
        # Ensure contact settings exist even if default_trial_days was already seeded
        for key, val, desc in [
            ("support_phone", "+91 98765 43210", "Vendor customer support telephone number."),
            ("support_whatsapp", "+91 98765 43210", "Vendor support WhatsApp contact number."),
            ("support_email", "support@apexhealth.local", "Vendor customer support email address."),
            ("vendor_notification_email", "vendor@apexhealth.local", "Recipient email address for license alerts."),
        ]:
            if not db.query(SystemSetting).filter(SystemSetting.key == key).first():
                db.add(SystemSetting(key=key, value=val, description=desc))
        db.commit()
