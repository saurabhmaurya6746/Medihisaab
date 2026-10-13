"""Pydantic schemas and validation for online pharmacy portal endpoints."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


# ==================== Customer Auth ====================


class CustomerRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, description="Plaintext password (min 6 characters)")
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: str = Field(..., min_length=7, max_length=32)
    delivery_address: Optional[str] = Field(default="", max_length=1000)


class CustomerLoginRequest(BaseModel):
    email: EmailStr
    password: str


class CustomerProfileResponse(BaseModel):
    id: str
    email: str
    full_name: str
    phone: str
    delivery_address: str
    created_at: datetime


class CustomerAuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    customer: CustomerProfileResponse


class CustomerUpdateProfileRequest(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    phone: Optional[str] = Field(None, min_length=7, max_length=32)
    delivery_address: Optional[str] = Field(None, max_length=1000)


# ==================== Staff Auth ====================


class StaffLoginRequest(BaseModel):
    email: EmailStr
    password: str


class StaffProfileResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


class StaffAuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    staff: StaffProfileResponse


# ==================== Categories ====================


class CategoryResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: str
    display_order: int
    is_active: bool
    product_count: Optional[int] = 0


class CategoryCreateUpdateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=128)
    slug: Optional[str] = Field(None, max_length=128)
    description: Optional[str] = Field("", max_length=1000)
    display_order: Optional[int] = 0
    is_active: Optional[bool] = True


# ==================== Products ====================


class ProductResponse(BaseModel):
    id: str
    category_id: str
    category_name: Optional[str] = ""
    category_slug: Optional[str] = ""
    name: str
    slug: str
    generic_name: str
    dosage_form: str
    pack_size: str
    mrp_paise: int
    selling_price_paise: int
    is_prescription_required: bool
    is_available: bool
    stock_status: str
    image_url: str
    description: str
    usage_instructions: str
    side_effects: str
    created_at: datetime
    updated_at: datetime


class ProductCreateUpdateRequest(BaseModel):
    category_id: str
    name: str = Field(..., min_length=2, max_length=255)
    slug: Optional[str] = None
    generic_name: Optional[str] = ""
    dosage_form: Optional[str] = "Tablet"
    pack_size: Optional[str] = "10 Tablets"
    mrp_paise: int = Field(..., ge=0)
    selling_price_paise: int = Field(..., ge=0)
    is_prescription_required: bool = False
    is_available: bool = True
    stock_status: Optional[str] = "IN_STOCK"
    image_url: Optional[str] = ""
    description: Optional[str] = ""
    usage_instructions: Optional[str] = ""
    side_effects: Optional[str] = ""


class ProductListResponse(BaseModel):
    items: List[ProductResponse]
    total: int
    page: int
    limit: int


# ==================== Orders ====================


class CreateOrderItemInput(BaseModel):
    product_id: str
    quantity: int = Field(..., ge=1, le=100)


class CreateOrderRequest(BaseModel):
    fulfillment_type: str = Field("PICKUP", description="PICKUP or DELIVERY")
    delivery_address: Optional[str] = ""
    payment_method: str = Field("PAY_AT_PICKUP", description="PAY_AT_PICKUP, CASH_ON_DELIVERY, or UPI_ON_DELIVERY")
    customer_phone: Optional[str] = None
    prescription_acknowledged: Optional[bool] = False
    items: List[CreateOrderItemInput] = Field(..., min_length=1)


class OrderItemDetailResponse(BaseModel):
    id: str
    product_id: str
    product_name: str
    generic_name: str
    dosage_form: str
    pack_size: str
    unit_price_paise: int
    quantity: int
    total_paise: int
    is_prescription_required: bool


class OrderStatusHistoryResponse(BaseModel):
    id: str
    order_id: str
    from_status: Optional[str]
    to_status: str
    changed_by_type: str
    changed_by_name: str
    notes: str
    created_at: datetime


class OrderResponse(BaseModel):
    id: str
    order_number: str
    customer_id: str
    customer_name: str
    customer_email: str
    customer_phone: str
    fulfillment_type: str
    delivery_address: str
    payment_method: str
    status: str
    subtotal_paise: int
    delivery_fee_paise: int
    total_paise: int
    has_prescription_items: bool
    pharmacist_notes: str
    rejection_reason: str
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemDetailResponse]
    status_history: List[OrderStatusHistoryResponse] = []


class UpdateOrderStatusRequest(BaseModel):
    status: str = Field(..., description="Target order status")
    notes: Optional[str] = ""
    rejection_reason: Optional[str] = ""
    pharmacist_notes: Optional[str] = ""


# ==================== Dashboard, Audits, Store Info ====================


class StaffDashboardMetrics(BaseModel):
    total_orders: int
    pending_confirmation_count: int
    pharmacist_review_count: int
    ready_orders_count: int
    delivered_today_count: int
    total_products_count: int
    low_stock_count: int
    total_customers_count: int
    revenue_today_paise: int


class StaffAuditLogResponse(BaseModel):
    id: str
    staff_user_id: str
    staff_email: str
    action: str
    entity_type: str
    entity_id: str
    details_json: str
    created_at: datetime


class OperationalCustomerLookup(BaseModel):
    id: str
    email: str
    full_name: str
    phone: str
    delivery_address: str
    orders_count: int
    last_order_date: Optional[datetime] = None
    created_at: datetime


class StoreInfoResponse(BaseModel):
    store_name: str
    tagline: str
    license_number: str
    phone: str
    email: str
    address: str
    operating_hours: str
    delivery_fee_paise: int
    free_delivery_threshold_paise: int
    estimated_delivery_time: str
    estimated_pickup_time: str
    rx_policy_notice: str
