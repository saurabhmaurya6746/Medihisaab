"""SQLAlchemy models for the Online Pharmacy Portal."""

import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from portal_service.db.session import Base


def utcnow():
    return datetime.now(timezone.utc)


class StaffRole(str, enum.Enum):
    ADMIN = "ADMIN"
    PHARMACIST = "PHARMACIST"
    STAFF = "STAFF"


class StockStatusEnum(str, enum.Enum):
    IN_STOCK = "IN_STOCK"
    LOW_STOCK = "LOW_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"


class FulfillmentTypeEnum(str, enum.Enum):
    PICKUP = "PICKUP"
    DELIVERY = "DELIVERY"


class PaymentMethodEnum(str, enum.Enum):
    PAY_AT_PICKUP = "PAY_AT_PICKUP"
    CASH_ON_DELIVERY = "CASH_ON_DELIVERY"
    UPI_ON_DELIVERY = "UPI_ON_DELIVERY"


class OrderStatusEnum(str, enum.Enum):
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    PHARMACIST_REVIEW = "PHARMACIST_REVIEW"
    CONFIRMED = "CONFIRMED"
    PREPARING = "PREPARING"
    READY_FOR_PICKUP = "READY_FOR_PICKUP"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class PortalStaffUser(Base):
    __tablename__ = "portal_staff_users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(32), default=StaffRole.STAFF.value, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class Customer(Base):
    __tablename__ = "portal_customers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(32), nullable=False, index=True)
    delivery_address = Column(Text, default="", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    orders = relationship("Order", back_populates="customer", cascade="all, delete-orphan")


class Category(Base):
    __tablename__ = "portal_categories"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(128), unique=True, nullable=False)
    slug = Column(String(128), unique=True, nullable=False, index=True)
    description = Column(Text, default="", nullable=False)
    display_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    products = relationship("Product", back_populates="category")


class Product(Base):
    __tablename__ = "portal_products"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    category_id = Column(String(36), ForeignKey("portal_categories.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    generic_name = Column(String(255), default="", nullable=False)
    dosage_form = Column(String(64), default="Tablet", nullable=False)
    pack_size = Column(String(64), default="10 Tablets", nullable=False)
    mrp_paise = Column(Integer, nullable=False)  # ₹ in paise
    selling_price_paise = Column(Integer, nullable=False)  # ₹ in paise
    is_prescription_required = Column(Boolean, default=False, nullable=False)
    is_available = Column(Boolean, default=True, nullable=False)
    stock_status = Column(String(32), default=StockStatusEnum.IN_STOCK.value, nullable=False)
    image_url = Column(String(512), default="", nullable=False)
    description = Column(Text, default="", nullable=False)
    usage_instructions = Column(Text, default="", nullable=False)
    side_effects = Column(Text, default="", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    category = relationship("Category", back_populates="products")


class Order(Base):
    __tablename__ = "portal_orders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_number = Column(String(64), unique=True, nullable=False, index=True)
    customer_id = Column(String(36), ForeignKey("portal_customers.id"), nullable=False, index=True)
    customer_name = Column(String(255), nullable=False)
    customer_email = Column(String(255), nullable=False)
    customer_phone = Column(String(32), nullable=False)
    fulfillment_type = Column(String(32), default=FulfillmentTypeEnum.PICKUP.value, nullable=False)
    delivery_address = Column(Text, default="", nullable=False)
    payment_method = Column(String(32), default=PaymentMethodEnum.PAY_AT_PICKUP.value, nullable=False)
    status = Column(String(32), default=OrderStatusEnum.PENDING_CONFIRMATION.value, nullable=False, index=True)
    subtotal_paise = Column(Integer, default=0, nullable=False)
    delivery_fee_paise = Column(Integer, default=0, nullable=False)
    total_paise = Column(Integer, default=0, nullable=False)
    has_prescription_items = Column(Boolean, default=False, nullable=False)
    pharmacist_notes = Column(Text, default="", nullable=False)
    rejection_reason = Column(Text, default="", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    customer = relationship("Customer", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    status_history = relationship(
        "OrderStatusHistory",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderStatusHistory.created_at.asc()",
    )


class OrderItem(Base):
    __tablename__ = "portal_order_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String(36), ForeignKey("portal_orders.id"), nullable=False, index=True)
    product_id = Column(String(36), ForeignKey("portal_products.id"), nullable=False)
    product_name = Column(String(255), nullable=False)
    generic_name = Column(String(255), default="", nullable=False)
    dosage_form = Column(String(64), default="", nullable=False)
    pack_size = Column(String(64), default="", nullable=False)
    unit_price_paise = Column(Integer, nullable=False)
    quantity = Column(Integer, nullable=False)
    total_paise = Column(Integer, nullable=False)
    is_prescription_required = Column(Boolean, default=False, nullable=False)

    order = relationship("Order", back_populates="items")
    product = relationship("Product")


class OrderStatusHistory(Base):
    __tablename__ = "portal_order_status_history"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String(36), ForeignKey("portal_orders.id"), nullable=False, index=True)
    from_status = Column(String(32), nullable=True)
    to_status = Column(String(32), nullable=False)
    changed_by_type = Column(String(32), default="STAFF", nullable=False)  # "STAFF", "CUSTOMER", "SYSTEM"
    changed_by_name = Column(String(255), default="", nullable=False)
    notes = Column(Text, default="", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    order = relationship("Order", back_populates="status_history")


class PortalAuditLog(Base):
    __tablename__ = "portal_audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    staff_user_id = Column(String(36), nullable=False, index=True)
    staff_email = Column(String(255), nullable=False)
    action = Column(String(128), nullable=False, index=True)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(String(64), nullable=False)
    details_json = Column(Text, default="{}", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
