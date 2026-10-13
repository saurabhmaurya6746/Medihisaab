"""SQLAlchemy ORM models for Central Vendor Licensing & Subscription System."""

from datetime import datetime, timezone
import enum
from typing import Any, Dict, Optional
import json

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from licensing_service.db.session import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ClientStatus(str, enum.Enum):
    LEAD = "LEAD"
    TRIAL = "TRIAL"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"


class BillingPeriod(str, enum.Enum):
    MONTHLY = "MONTHLY"
    ANNUAL = "ANNUAL"
    TRIAL = "TRIAL"


class SubscriptionStatus(str, enum.Enum):
    TRIALING = "TRIALING"
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    SUSPENDED = "SUSPENDED"


class VendorRole(str, enum.Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    SUPPORT = "SUPPORT"
    READ_ONLY = "READ_ONLY"


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    client_code = Column(String(64), unique=True, index=True, nullable=False)
    business_name = Column(String(255), index=True, nullable=False)
    owner_name = Column(String(255), nullable=False)
    phone = Column(String(32), index=True, nullable=False)
    email = Column(String(255), index=True, nullable=False)
    address = Column(String(500), default="", nullable=False)
    city = Column(String(100), default="", nullable=False)
    state = Column(String(100), default="", nullable=False)
    postal_code = Column(String(32), default="", nullable=False)
    gstin = Column(String(32), nullable=True)
    retail_drug_license = Column(String(100), nullable=True)
    wholesale_drug_license = Column(String(100), nullable=True)
    primary_contact_name = Column(String(255), nullable=False)
    notes = Column(Text, nullable=True)
    status = Column(String(32), default=ClientStatus.LEAD.value, nullable=False, index=True)

    password_hash = Column(String(255), nullable=True)
    email_verified = Column(Boolean, default=True, nullable=False)
    verification_token = Column(String(128), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    subscriptions = relationship("Subscription", back_populates="client", cascade="all, delete-orphan")
    licenses = relationship("LicenseRecord", back_populates="client", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="client", cascade="all, delete-orphan")
    renewal_requests = relationship("RenewalRequest", back_populates="client", cascade="all, delete-orphan")


class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    plan_code = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    billing_period = Column(String(32), default=BillingPeriod.ANNUAL.value, nullable=False)
    price = Column(Integer, default=0, nullable=False)  # in currency smallest units or rupees
    currency = Column(String(8), default="INR", nullable=False)
    maximum_terminals = Column(Integer, default=1, nullable=False)
    enabled_features = Column(Text, default="ALL", nullable=False)  # JSON array string or "ALL"
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    subscriptions = relationship("Subscription", back_populates="plan")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False, index=True)
    status = Column(String(32), default=SubscriptionStatus.ACTIVE.value, nullable=False, index=True)

    start_date = Column(Date, nullable=False)
    current_period_start = Column(Date, nullable=False)
    current_period_end = Column(Date, nullable=False)
    grace_period_end = Column(Date, nullable=False)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    payment_reference = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    trial_days = Column(Integer, nullable=True)
    is_trial = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    client = relationship("Client", back_populates="subscriptions")
    plan = relationship("Plan", back_populates="subscriptions")
    licenses = relationship("LicenseRecord", back_populates="subscription")
    payments = relationship("Payment", back_populates="subscription")


class LicenseRecord(Base):
    __tablename__ = "licenses"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True, index=True)

    license_id = Column(String(128), unique=True, index=True, nullable=False)
    client_name = Column(String(255), nullable=False)
    terminal_count = Column(Integer, default=1, nullable=False)
    activation_date = Column(String(32), nullable=False)  # YYYY-MM-DD
    expiry_date = Column(String(32), nullable=True)  # YYYY-MM-DD or None for perpetual
    edition = Column(String(64), default="COMMERCIAL", nullable=False)
    enabled_features = Column(Text, default="ALL", nullable=False)
    version = Column(Integer, default=2, nullable=False)
    grace_period_days = Column(Integer, default=0, nullable=False)
    signature = Column(String(256), nullable=False)  # 128-char hex Ed25519 signature

    issued_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    client = relationship("Client", back_populates="licenses")
    subscription = relationship("Subscription", back_populates="licenses")


class VendorUser(Base):
    __tablename__ = "vendor_users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), default=VendorRole.SUPPORT.value, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    last_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_email = Column(String(255), index=True, nullable=False)
    action = Column(String(128), index=True, nullable=False)
    entity_type = Column(String(64), index=True, nullable=False)
    entity_id = Column(String(128), nullable=True, index=True)
    timestamp = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    ip_address = Column(String(64), nullable=True)
    metadata_json = Column(Text, nullable=True)  # JSON-encoded sanitized metadata dictionary

    def get_metadata(self) -> Dict[str, Any]:
        if not self.metadata_json:
            return {}
        try:
            return json.loads(self.metadata_json)
        except Exception:
            return {}


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True, index=True)
    plan_id = Column(Integer, ForeignKey("plans.id", ondelete="SET NULL"), nullable=True, index=True)

    amount = Column(Integer, nullable=False)  # in paise
    currency = Column(String(8), default="INR", nullable=False)
    payment_date = Column(Date, nullable=False)
    payment_method = Column(String(64), default="UPI", nullable=False)  # UPI, BANK_TRANSFER, CHEQUE, CASH, OTHER
    payment_reference = Column(String(255), index=True, nullable=False)  # UTR / Transaction ID
    status = Column(String(32), default="CONFIRMED", nullable=False, index=True)  # CONFIRMED, PENDING, REJECTED, REFUNDED
    notes = Column(Text, nullable=True)
    recorded_by_email = Column(String(255), nullable=True)
    reviewed_by_email = Column(String(255), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    client = relationship("Client", back_populates="payments")
    subscription = relationship("Subscription", back_populates="payments")
    plan = relationship("Plan")


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    key = Column(String(128), unique=True, index=True, nullable=False)
    value = Column(Text, nullable=False)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class RenewalRequest(Base):
    __tablename__ = "renewal_requests"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True, index=True)
    plan_id = Column(Integer, ForeignKey("plans.id", ondelete="SET NULL"), nullable=True, index=True)
    requested_plan_code = Column(String(64), default="MONTHLY_STANDARD", nullable=False)

    store_name = Column(String(255), nullable=False)
    contact_name = Column(String(255), nullable=False)
    email = Column(String(255), index=True, nullable=False)
    phone = Column(String(32), index=True, nullable=False)

    status = Column(String(32), default="PENDING", nullable=False, index=True)  # PENDING, APPROVED, REJECTED
    notes = Column(Text, nullable=True)
    payment_reference = Column(String(255), nullable=True)
    payment_amount = Column(Integer, default=0, nullable=False)

    vendor_notification_sent = Column(Boolean, default=False, nullable=False)
    vendor_notification_error = Column(String(255), nullable=True)

    reviewed_by_email = Column(String(255), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    client = relationship("Client", back_populates="renewal_requests")
    subscription = relationship("Subscription")
    plan = relationship("Plan")

