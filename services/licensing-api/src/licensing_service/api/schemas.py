"""Pydantic request and response schemas for Vendor Licensing API."""

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


# Generic API response envelope
class ApiEnvelope(BaseModel):
    success: bool = True
    data: Any
    message: Optional[str] = None


# Auth & Vendor Users
class LoginRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=6)


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: str
    role: str
    is_active: bool
    last_login_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class VendorUserCreateRequest(BaseModel):
    full_name: str = Field(min_length=2)
    email: str = Field(min_length=3)
    password: str = Field(min_length=6)
    role: str = "SUPPORT"


class VendorUserStatusRequest(BaseModel):
    is_active: bool


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: UserResponse


# Client
class ClientCreateRequest(BaseModel):
    client_code: Optional[str] = None
    business_name: str = Field(min_length=2)
    owner_name: str = Field(min_length=2)
    phone: str = Field(min_length=5)
    email: Optional[str] = "contact@client.example"
    address: Optional[str] = ""
    city: Optional[str] = ""
    state: Optional[str] = ""
    postal_code: Optional[str] = ""
    gstin: Optional[str] = None
    retail_drug_license: Optional[str] = None
    wholesale_drug_license: Optional[str] = None
    primary_contact_name: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = "ACTIVE"


class ClientUpdateRequest(BaseModel):
    business_name: Optional[str] = None
    owner_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    gstin: Optional[str] = None
    retail_drug_license: Optional[str] = None
    wholesale_drug_license: Optional[str] = None
    primary_contact_name: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class ClientStatusChangeRequest(BaseModel):
    status: str
    reason: Optional[str] = None


class ClientResponse(BaseModel):
    id: int
    client_code: str
    business_name: str
    owner_name: str
    phone: str
    email: str
    address: str
    city: str
    state: str
    postal_code: str
    gstin: Optional[str] = None
    retail_drug_license: Optional[str] = None
    wholesale_drug_license: Optional[str] = None
    primary_contact_name: str
    notes: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Plan
class PlanCreateRequest(BaseModel):
    plan_code: str = Field(min_length=2)
    name: str = Field(min_length=2)
    description: str = ""
    billing_period: str = "ANNUAL"  # MONTHLY, ANNUAL, TRIAL
    price: int = Field(ge=0)  # in paise
    currency: str = "INR"
    maximum_terminals: int = Field(ge=1)
    enabled_features: str = "ALL"
    is_active: bool = True


class PlanUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    billing_period: Optional[str] = None
    price: Optional[int] = None
    maximum_terminals: Optional[int] = None
    enabled_features: Optional[str] = None
    is_active: Optional[bool] = None


class PlanResponse(BaseModel):
    id: int
    plan_code: str
    name: str
    description: str
    billing_period: str
    price: int
    currency: str
    maximum_terminals: int
    enabled_features: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Subscriptions
class StartTrialRequest(BaseModel):
    client_id: int
    trial_days: Optional[int] = None
    grace_days: Optional[int] = None
    notes: Optional[str] = None


class CreatePaidSubscriptionRequest(BaseModel):
    client_id: int
    plan_id: Optional[int] = None
    plan_code: Optional[str] = None
    billing_period: Optional[str] = None
    start_date: Optional[date] = None
    expiry_date: Optional[date] = None
    payment_reference: Optional[str] = None
    amount: Optional[int] = 0
    payment_method: Optional[str] = "UPI"
    notes: Optional[str] = None


class ConvertTrialRequest(BaseModel):
    plan_id: int
    expiry_date: Optional[date] = None
    payment_reference: Optional[str] = None
    amount: Optional[int] = 0
    payment_method: Optional[str] = "UPI"
    notes: Optional[str] = None


class RecordPaymentRequest(BaseModel):
    payment_reference: str
    amount: int
    payment_method: str = "UPI"
    notes: Optional[str] = None


class RenewSubscriptionRequest(BaseModel):
    payment_reference: Optional[str] = None
    amount: Optional[int] = 0
    payment_method: Optional[str] = "UPI"
    notes: Optional[str] = None
    new_expiry_date: Optional[date] = None


class ActionReasonRequest(BaseModel):
    reason: Optional[str] = None
    notes: Optional[str] = None


class SubscriptionResponse(BaseModel):
    id: int
    client_id: int
    plan_id: int
    status: str
    start_date: date
    current_period_start: date
    current_period_end: date
    grace_period_end: date
    cancelled_at: Optional[datetime] = None
    payment_reference: Optional[str] = None
    notes: Optional[str] = None
    trial_days: Optional[int] = None
    is_trial: Optional[bool] = False
    created_at: datetime
    updated_at: datetime
    plan: Optional[PlanResponse] = None

    model_config = ConfigDict(from_attributes=True)


# Payments
class PaymentCreateRequest(BaseModel):
    client_id: int
    subscription_id: Optional[int] = None
    amount: int = Field(ge=0)
    payment_reference: str = Field(min_length=1)
    payment_date: Optional[date] = None
    payment_method: str = "UPI"
    notes: Optional[str] = None


class PaymentResponse(BaseModel):
    id: int
    client_id: int
    subscription_id: Optional[int] = None
    plan_id: Optional[int] = None
    amount: int
    currency: str = "INR"
    payment_date: date
    payment_method: str
    payment_reference: str
    status: str
    notes: Optional[str] = None
    recorded_by_email: Optional[str] = None
    reviewed_by_email: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# System Settings
class SystemSettingResponse(BaseModel):
    id: int
    key: str
    value: str
    description: Optional[str] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UpdateTrialDurationRequest(BaseModel):
    default_trial_days: int = Field(ge=1, le=365)
    default_grace_days: Optional[int] = Field(default=None, ge=0, le=90)


# Licenses
class GenerateLicenseRequest(BaseModel):
    client_id: Optional[int] = None
    subscription_id: Optional[int] = None
    terminal_count: Optional[int] = None
    activation_date: Optional[str] = None
    expiry_date: Optional[str] = None
    edition: Optional[str] = None
    enabled_features: Optional[str] = None


class LicenseResponse(BaseModel):
    id: int
    client_id: int
    subscription_id: Optional[int] = None
    license_id: str
    client_name: str
    terminal_count: int
    activation_date: str
    expiry_date: Optional[str] = None
    edition: str
    enabled_features: str
    signature: str
    issued_at: datetime
    revoked_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Dashboard
class DashboardStatsResponse(BaseModel):
    total_clients: int
    active_subscriptions: int
    trial_clients: int
    expiring_soon_subscriptions: int
    expired_subscriptions: int
    suspended_clients: int
    total_licenses_issued: int
    recent_licenses: List[LicenseResponse]


# Client Portal Schemas
class ClientSignupRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=8)
    pharmacy_name: Optional[str] = None
    business_name: Optional[str] = None
    contact_person: Optional[str] = None
    owner_name: Optional[str] = None
    phone: str = Field(min_length=7)
    drug_license_number: Optional[str] = None
    gstin: Optional[str] = None


class ClientAuthResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    client: ClientResponse
    business_name: Optional[str] = None
    owner_name: Optional[str] = None
    email: Optional[str] = None
    trial_days: Optional[int] = 15
    subscription_status: Optional[str] = "TRIALING"
    license_token: Optional[Dict[str, Any]] = None


class RefreshTokenRequest(BaseModel):
    refresh_token: Optional[str] = None


class EmailVerifyRequest(BaseModel):
    token: str


class ClientPaymentSubmitRequest(BaseModel):
    plan_id: Optional[int] = None
    plan_code: Optional[str] = None
    amount: int = Field(gt=0)
    payment_reference: str = Field(min_length=2)
    payment_method: str = "UPI"
    notes: Optional[str] = None


class PaymentRejectRequest(BaseModel):
    reason: str = Field(min_length=2)


class ClientDashboardResponse(BaseModel):
    client: ClientResponse
    subscription: Optional[SubscriptionResponse] = None
    active_license: Optional[LicenseResponse] = None
    license_token: Optional[Dict[str, Any]] = None
    days_remaining: Optional[int] = None
    grace_period_active: bool = False
    status: str
    maximum_terminals: int
    last_refreshed: str
    can_renew: bool = True
    recent_payments: List[PaymentResponse] = []


# Renewal Request Schemas
class RenewalRequestCreateInput(BaseModel):
    store_name: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    requested_plan_code: Optional[str] = "MONTHLY_STANDARD"
    payment_reference: Optional[str] = None
    payment_amount: Optional[int] = 0
    notes: Optional[str] = None


class RenewalRequestResponse(BaseModel):
    id: int
    client_id: int
    subscription_id: Optional[int] = None
    plan_id: Optional[int] = None
    requested_plan_code: str
    store_name: str
    contact_name: str
    email: str
    phone: str
    status: str
    notes: Optional[str] = None
    payment_reference: Optional[str] = None
    payment_amount: int
    vendor_notification_sent: bool
    vendor_notification_error: Optional[str] = None
    reviewed_by_email: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    client: Optional[ClientResponse] = None

    model_config = ConfigDict(from_attributes=True)


class RenewalRequestApproveInput(BaseModel):
    plan_id: Optional[int] = None
    payment_reference: Optional[str] = None
    amount: Optional[int] = None
    notes: Optional[str] = None


class RenewalRequestRejectInput(BaseModel):
    reason: str = Field(min_length=2)


# Support Contacts Schemas
class SupportContactsResponse(BaseModel):
    phone: str
    whatsapp: str
    email: str
    vendor_notification_email: Optional[str] = None


class SupportContactsUpdateRequest(BaseModel):
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[str] = None
    vendor_notification_email: Optional[str] = None

