"""Pydantic validation schemas and DTOs for Master Catalog endpoints."""

from typing import Any, Dict, Generic, List, Literal, Optional, TypeVar
from pydantic import BaseModel, Field, field_validator

T = TypeVar("T")

# Statutory validation regexes
GSTIN_REGEX = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
HSN_REGEX = r"^\d{4,8}$"

VALID_DOSAGE_FORMS = {
    "TABLET",
    "CAPSULE",
    "SYRUP",
    "INJECTION",
    "OINTMENT",
    "DROPS",
    "POWDER",
    "RESPULES",
    "INHALER",
}

VALID_GST_RATES = {0.0, 5.0, 12.0, 18.0, 28.0}


# ==========================================
# COMMON ENVELOPE SCHEMAS
# ==========================================

class PaginatedData(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class SuccessResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T
    message: Optional[str] = None


# ==========================================
# MANUFACTURER SCHEMAS
# ==========================================

class ManufacturerResponse(BaseModel):
    id: int
    name: str
    short_code: Optional[str] = None
    is_active: bool
    created_at: str
    updated_at: Optional[str] = None


class CreateManufacturerRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    short_code: Optional[str] = Field(None, max_length=20)


class UpdateManufacturerRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    short_code: Optional[str] = Field(None, max_length=20)
    is_active: Optional[bool] = None


# ==========================================
# MEDICINE SCHEMAS
# ==========================================

class MedicineResponse(BaseModel):
    id: int
    medicine_code: Optional[str] = None
    brand_name: str
    generic_salt: str
    dosage_form: str
    strength: Optional[str] = None
    pack_size: int
    manufacturer_id: Optional[int] = None
    manufacturer_name: Optional[str] = None
    hsn_code: str
    gst_rate: float
    is_schedule_h1: bool
    is_schedule_h: bool
    is_narcotic: bool
    min_stock_units: int
    rack_location: Optional[str] = None
    barcode: Optional[str] = None
    is_active: bool
    created_at: str
    updated_at: str


class CreateMedicineRequest(BaseModel):
    brand_name: str = Field(..., min_length=1, max_length=150)
    generic_salt: str = Field(..., min_length=1, max_length=250)
    dosage_form: str = Field(..., min_length=1)
    medicine_code: Optional[str] = Field(None, max_length=50)
    strength: Optional[str] = Field(None, max_length=50)
    pack_size: int = Field(1, ge=1)
    manufacturer_id: Optional[int] = None
    hsn_code: str = Field("3004", pattern=HSN_REGEX)
    gst_rate: float = Field(12.0)
    is_schedule_h1: bool = False
    is_schedule_h: bool = True
    is_narcotic: bool = False
    min_stock_units: int = Field(10, ge=0)
    rack_location: Optional[str] = Field(None, max_length=50)
    barcode: Optional[str] = Field(None, max_length=50)

    @field_validator("dosage_form")
    @classmethod
    def validate_dosage_form(cls, v: str) -> str:
        upper = v.strip().upper()
        if upper not in VALID_DOSAGE_FORMS:
            raise ValueError(f"Invalid dosage form '{v}'. Must be one of: {sorted(VALID_DOSAGE_FORMS)}")
        return upper

    @field_validator("gst_rate")
    @classmethod
    def validate_gst_rate(cls, v: float) -> float:
        if float(v) not in VALID_GST_RATES:
            raise ValueError(f"Invalid GST rate '{v}'. Must be one of: {sorted(VALID_GST_RATES)}")
        return float(v)


class UpdateMedicineRequest(BaseModel):
    brand_name: Optional[str] = Field(None, min_length=1, max_length=150)
    generic_salt: Optional[str] = Field(None, min_length=1, max_length=250)
    dosage_form: Optional[str] = None
    medicine_code: Optional[str] = Field(None, max_length=50)
    strength: Optional[str] = Field(None, max_length=50)
    pack_size: Optional[int] = Field(None, ge=1)
    manufacturer_id: Optional[int] = None
    hsn_code: Optional[str] = Field(None, pattern=HSN_REGEX)
    gst_rate: Optional[float] = None
    is_schedule_h1: Optional[bool] = None
    is_schedule_h: Optional[bool] = None
    is_narcotic: Optional[bool] = None
    min_stock_units: Optional[int] = Field(None, ge=0)
    rack_location: Optional[str] = Field(None, max_length=50)
    barcode: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None

    @field_validator("dosage_form")
    @classmethod
    def validate_dosage_form(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        upper = v.strip().upper()
        if upper not in VALID_DOSAGE_FORMS:
            raise ValueError(f"Invalid dosage form '{v}'. Must be one of: {sorted(VALID_DOSAGE_FORMS)}")
        return upper

    @field_validator("gst_rate")
    @classmethod
    def validate_gst_rate(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return None
        if float(v) not in VALID_GST_RATES:
            raise ValueError(f"Invalid GST rate '{v}'. Must be one of: {sorted(VALID_GST_RATES)}")
        return float(v)


# ==========================================
# SUPPLIER SCHEMAS
# ==========================================

class SupplierResponse(BaseModel):
    id: int
    name: str
    gstin: Optional[str] = None
    dl_number_20b: Optional[str] = None
    dl_number_21b: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    credit_days: int
    current_payable_paise: int
    is_active: bool
    created_at: str


class CreateSupplierRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    gstin: Optional[str] = Field(None, pattern=GSTIN_REGEX)
    dl_number_20b: Optional[str] = Field(None, min_length=3, max_length=50)
    dl_number_21b: Optional[str] = Field(None, min_length=3, max_length=50)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=250)
    credit_days: int = Field(21, ge=0)


class UpdateSupplierRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    gstin: Optional[str] = Field(None, pattern=GSTIN_REGEX)
    dl_number_20b: Optional[str] = Field(None, min_length=3, max_length=50)
    dl_number_21b: Optional[str] = Field(None, min_length=3, max_length=50)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=250)
    credit_days: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class SupplierPayableSummaryResponse(BaseModel):
    supplier_id: int
    supplier_name: str
    current_payable_paise: int
    pending_invoices_count: int = 0
    oldest_due_date: Optional[str] = None


# ==========================================
# CUSTOMER SCHEMAS
# ==========================================

class CustomerResponse(BaseModel):
    id: int
    name: str
    phone: Optional[str] = None
    gstin: Optional[str] = None
    address: Optional[str] = None
    default_doctor: Optional[str] = None
    credit_limit_paise: int
    current_balance_paise: int
    is_active: bool
    created_at: str
    updated_at: Optional[str] = None


class CreateCustomerRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    phone: Optional[str] = Field(None, min_length=5, max_length=20)
    gstin: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = Field(None, max_length=250)
    default_doctor: Optional[str] = Field(None, max_length=150)
    credit_limit_paise: int = Field(500000, ge=0)


class UpdateCustomerRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    phone: Optional[str] = Field(None, min_length=5, max_length=20)
    gstin: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = Field(None, max_length=250)
    default_doctor: Optional[str] = Field(None, max_length=150)
    credit_limit_paise: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


# ==========================================
# EXPIRY DATE NORMALIZER & VALIDATOR
# ==========================================

import calendar
from datetime import date, datetime, timezone
import re


def normalize_and_validate_expiry(val: str) -> str:
    """Normalize expiry date to ISO YYYY-MM-DD and reject past/expired dates."""
    val = val.strip()
    today = datetime.now(timezone.utc).date()

    # Format: MM/YY or MM/YYYY
    if "/" in val:
        parts = val.split("/")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            month = int(parts[0])
            year = int(parts[1])
            if year < 100:
                year += 2000
            if 1 <= month <= 12:
                last_day = calendar.monthrange(year, month)[1]
                exp_date = date(year, month, last_day)
                if exp_date < today:
                    raise ValueError(f"Batch expiry date '{val}' ({exp_date}) cannot be in the past.")
                return exp_date.isoformat()

    # Format: YYYY-MM
    if re.match(r"^\d{4}-\d{2}$", val):
        year, month = map(int, val.split("-"))
        if 1 <= month <= 12:
            last_day = calendar.monthrange(year, month)[1]
            exp_date = date(year, month, last_day)
            if exp_date < today:
                raise ValueError(f"Batch expiry date '{val}' ({exp_date}) cannot be in the past.")
            return exp_date.isoformat()

    # Format: YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", val):
        try:
            exp_date = date.fromisoformat(val)
            if exp_date < today:
                raise ValueError(f"Batch expiry date '{val}' cannot be in the past.")
            return val
        except ValueError as e:
            raise ValueError(f"Invalid date: {e}") from e

    raise ValueError(f"Invalid expiry date format '{val}'. Expected MM/YY, YYYY-MM, or YYYY-MM-DD.")


# ==========================================
# PURCHASE INVOICE SCHEMAS
# ==========================================

class PurchaseInvoiceLineInput(BaseModel):
    medicine_id: int
    batch_number: str = Field(..., min_length=1, max_length=50)
    expiry_date: str
    pack_size: int = Field(1, ge=1)
    paid_quantity: int = Field(..., ge=0)
    free_quantity: int = Field(0, ge=0)
    purchase_rate_paise: int = Field(..., ge=0)
    mrp_paise: int = Field(..., ge=0)
    discount_paise: int = Field(0, ge=0)
    gst_percentage: float = Field(12.0, ge=0.0)

    @field_validator("expiry_date")
    @classmethod
    def validate_expiry(cls, v: str) -> str:
        return normalize_and_validate_expiry(v)

    @field_validator("gst_percentage")
    @classmethod
    def validate_gst(cls, v: float) -> float:
        if v not in VALID_GST_RATES:
            raise ValueError(f"GST rate {v}% is invalid. Must be one of {sorted(VALID_GST_RATES)}")
        return v


class PurchaseInvoiceLineResponse(BaseModel):
    id: int
    purchase_invoice_id: int
    medicine_id: int
    medicine_name: Optional[str] = None
    dosage_form: Optional[str] = None
    batch_number: str
    expiry_date: str
    pack_size: int
    paid_quantity: int
    free_quantity: int
    total_received_quantity: int
    purchase_rate_paise: int
    mrp_paise: int
    discount_paise: int
    gst_percentage: float
    tax_amount_paise: int
    line_total_paise: int
    created_at: str


class CreatePurchaseInvoiceRequest(BaseModel):
    supplier_id: int
    supplier_invoice_number: str = Field(..., min_length=1, max_length=100)
    invoice_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    entry_date: Optional[str] = None
    discount_paise: int = Field(0, ge=0)
    notes: Optional[str] = None
    lines: List[PurchaseInvoiceLineInput] = Field(..., min_length=1)


class UpdatePurchaseInvoiceRequest(BaseModel):
    supplier_id: Optional[int] = None
    supplier_invoice_number: Optional[str] = Field(None, min_length=1, max_length=100)
    invoice_date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    entry_date: Optional[str] = None
    discount_paise: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None
    lines: Optional[List[PurchaseInvoiceLineInput]] = None


class PurchaseInvoiceResponse(BaseModel):
    id: int
    supplier_id: int
    supplier_name: Optional[str] = None
    supplier_invoice_number: str
    invoice_date: str
    entry_date: str
    status: str
    subtotal_paise: int
    discount_paise: int
    tax_amount_paise: int
    grand_total_paise: int
    payment_status: str
    notes: Optional[str] = None
    created_by: Optional[int] = None
    creator_name: Optional[str] = None
    created_at: str
    posted_at: Optional[str] = None
    updated_at: str
    lines: Optional[List[PurchaseInvoiceLineResponse]] = None


# ==========================================
# INVENTORY & BATCH SCHEMAS
# ==========================================

class MedicineBatchResponse(BaseModel):
    id: int
    medicine_id: int
    medicine_name: Optional[str] = None
    generic_salt: Optional[str] = None
    dosage_form: Optional[str] = None
    batch_number: str
    expiry_date: str
    mrp_paise: int
    purchase_rate_paise: int
    pack_size: int
    current_quantity: int
    available_packs: Optional[float] = None
    reserved_quantity: int
    is_active: bool
    created_at: str
    updated_at: str


class MedicineStockSummaryResponse(BaseModel):
    medicine_id: int
    brand_name: str
    generic_salt: str
    dosage_form: str
    pack_size: int
    total_stock_units: int
    total_packs: float
    earliest_expiry: Optional[str] = None
    active_batches_count: int


# ==========================================
# SUPPLIER PAYABLE LEDGER SCHEMAS
# ==========================================

class SupplierPayableEntryResponse(BaseModel):
    id: int
    supplier_id: int
    reference_type: str
    reference_id: Optional[int] = None
    entry_type: str
    amount_paise: int
    balance_paise: int
    notes: Optional[str] = None
    created_at: str


class SupplierPayableHistoryResponse(BaseModel):
    supplier_id: int
    supplier_name: str
    current_payable_paise: int
    entries: List[SupplierPayableEntryResponse]


# ==========================================
# SALES POS, FEFO, AND BILLING SCHEMAS
# ==========================================

class ScheduleH1Input(BaseModel):
    patient_name: str = Field(..., min_length=1, max_length=150)
    patient_address: str = Field(..., min_length=1, max_length=255)
    doctor_name: str = Field(..., min_length=1, max_length=150)
    doctor_address: Optional[str] = Field(None, max_length=255)


class ScheduleH1RecordResponse(BaseModel):
    id: int
    sale_item_id: int
    sale_invoice_id: Optional[int] = None
    invoice_no: Optional[str] = None
    dispensed_date: str
    medicine_name: str
    batch_number: str
    quantity_units: int
    patient_name: str
    patient_address: str
    doctor_name: str
    doctor_address: Optional[str] = None
    created_at: str


class PaymentAllocationInput(BaseModel):
    payment_mode: str = Field(..., pattern=r"^(CASH|UPI|CARD|KHATA)$")
    amount_paise: int = Field(..., gt=0)
    reference_note: Optional[str] = None


class SalePaymentResponse(BaseModel):
    id: int
    sale_invoice_id: int
    payment_mode: str
    amount_paise: int
    reference_note: Optional[str] = None
    created_at: str


class SaleLineInput(BaseModel):
    medicine_id: int
    batch_id: Optional[int] = None
    quantity_units: int = Field(..., gt=0)
    unit_rate_paise: Optional[int] = Field(None, ge=0)
    discount_percent: float = Field(0.0, ge=0.0, le=100.0)
    schedule_h1: Optional[ScheduleH1Input] = None


class SaleItemResponse(BaseModel):
    id: int
    sale_invoice_id: int
    medicine_id: int
    medicine_name: Optional[str] = None
    dosage_form: Optional[str] = None
    generic_salt: Optional[str] = None
    is_schedule_h1: bool = False
    batch_id: int
    batch_number: str
    expiry_date: str
    pack_size: int
    quantity_units: int
    unit_mrp_paise: int
    unit_rate_paise: int
    discount_percent: float
    taxable_amount_paise: int
    gst_rate: float
    cgst_amount_paise: int
    sgst_amount_paise: int
    total_amount_paise: int
    schedule_h1_record: Optional[ScheduleH1RecordResponse] = None
    created_at: str


class SaleInvoiceResponse(BaseModel):
    id: int
    invoice_no: str
    fiscal_year: str
    sequence_number: int
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    doctor_name: Optional[str] = None
    doctor_address: Optional[str] = None
    subtotal_taxable_paise: int
    total_cgst_paise: int
    total_sgst_paise: int
    total_igst_paise: int
    discount_paise: int
    round_off_paise: int
    grand_total_paise: int
    payment_mode: str
    cash_tendered_paise: int
    change_returned_paise: int
    status: str
    notes: Optional[str] = None
    created_by: Optional[int] = None
    creator_name: Optional[str] = None
    created_at: str
    updated_at: str
    items: List[SaleItemResponse] = []
    payments: List[SalePaymentResponse] = []


class CalculatedDraftLine(BaseModel):
    medicine_id: int
    medicine_name: str
    dosage_form: str
    generic_salt: str
    is_schedule_h1: bool
    batch_id: int
    batch_number: str
    expiry_date: str
    pack_size: int
    available_stock_units: int
    quantity_units: int
    unit_mrp_paise: int
    unit_rate_paise: int
    discount_percent: float
    discount_amount_paise: int
    taxable_amount_paise: int
    gst_rate: float
    cgst_amount_paise: int
    sgst_amount_paise: int
    total_amount_paise: int
    is_near_expiry: bool
    schedule_h1: Optional[ScheduleH1Input] = None


class SaleDraftCalculationRequest(BaseModel):
    lines: List[SaleLineInput]
    discount_paise: int = Field(0, ge=0)
    round_off_paise: int = 0
    customer_id: Optional[int] = None


class SaleDraftCalculationResponse(BaseModel):
    lines: List[CalculatedDraftLine]
    subtotal_taxable_paise: int
    total_cgst_paise: int
    total_sgst_paise: int
    total_tax_paise: int
    discount_paise: int
    round_off_paise: int
    grand_total_paise: int
    requires_schedule_h1: bool
    missing_schedule_h1_count: int


class SaleCheckoutRequest(BaseModel):
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    doctor_name: Optional[str] = None
    doctor_address: Optional[str] = None
    lines: List[SaleLineInput] = Field(..., min_length=1)
    payment_mode: str = Field(..., pattern=r"^(CASH|UPI|CARD|KHATA|SPLIT)$")
    payments: Optional[List[PaymentAllocationInput]] = None
    cash_tendered_paise: int = Field(0, ge=0)
    discount_paise: int = Field(0, ge=0)
    round_off_paise: int = 0
    notes: Optional[str] = None
    held_bill_id: Optional[int] = None


class CreateHeldBillRequest(BaseModel):
    hold_reference: Optional[str] = None
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    doctor_name: Optional[str] = None
    doctor_address: Optional[str] = None
    notes: Optional[str] = None
    items: List[Dict[str, Any]] = Field(..., min_length=1)


class HeldBillResponse(BaseModel):
    id: int
    hold_reference: str
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    doctor_name: Optional[str] = None
    doctor_address: Optional[str] = None
    items: List[Dict[str, Any]]
    subtotal_paise: int
    total_tax_paise: int
    grand_total_paise: int
    notes: Optional[str] = None
    created_by: Optional[int] = None
    creator_name: Optional[str] = None
    created_at: str
    updated_at: str


class SubstituteMedicineResponse(BaseModel):
    id: int
    brand_name: str
    generic_salt: str
    dosage_form: str
    pack_size: int
    rack_location: Optional[str] = None
    is_schedule_h1: bool
    gst_rate: float
    total_stock_units: int
    recommended_batch_id: Optional[int] = None
    recommended_batch_number: Optional[str] = None
    recommended_expiry_date: Optional[str] = None
    recommended_mrp_paise: Optional[int] = None
    available_batches_count: int


class PrintInvoiceRequest(BaseModel):
    printer_type: str = Field("thermal", pattern=r"^(thermal|laser)$")
    printer_name: Optional[str] = None


class PrintInvoiceResponse(BaseModel):
    printed: bool
    printer_type: str
    message: str


# ==========================================
# MILESTONE 4: EXPIRY DASHBOARD & MANAGEMENT
# ==========================================

class ExpiryBatchResponse(BaseModel):
    id: int
    medicine_id: int
    medicine_name: str
    generic_salt: str
    dosage_form: str
    batch_number: str
    expiry_date: str
    days_to_expiry: int
    is_expired: bool
    pack_size: int
    current_quantity: int
    available_packs: float
    purchase_rate_paise: int
    mrp_paise: int
    estimated_stock_value_paise: int
    rack_location: Optional[str] = None
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None


class ExpiryDashboardSummaryResponse(BaseModel):
    expired_count: int
    expired_value_paise: int
    within_30_count: int
    within_30_value_paise: int
    within_60_count: int
    within_60_value_paise: int
    within_90_count: int
    within_90_value_paise: int
    within_180_count: int
    within_180_value_paise: int
    total_at_risk_value_paise: int


class ExpiryDashboardData(BaseModel):
    summary: ExpiryDashboardSummaryResponse
    items: List[ExpiryBatchResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class SupplierReturnDumpGroupResponse(BaseModel):
    supplier_id: Optional[int] = None
    supplier_name: str
    supplier_phone: Optional[str] = None
    supplier_gstin: Optional[str] = None
    total_batches: int
    total_units: int
    total_value_paise: int
    batches: List[ExpiryBatchResponse]


# ==========================================
# MILESTONE 4: PHYSICAL STOCK AUDIT
# ==========================================

class CreateStockAdjustmentRequest(BaseModel):
    batch_id: int = Field(..., ge=1)
    physical_quantity: int = Field(..., ge=0)
    reason: Literal["BREAKAGE", "THEFT", "AUDIT_CORRECTION", "EXPIRED_SCRAP"]
    notes: Optional[str] = None


class StockAdjustmentResponse(BaseModel):
    id: int
    adjustment_number: str
    batch_id: int
    medicine_id: int
    medicine_name: str
    generic_salt: str
    dosage_form: str
    batch_number: str
    expiry_date: str
    pack_size: int
    system_quantity: int
    physical_quantity: int
    delta_quantity: int
    reason: str
    estimated_loss_paise: int
    notes: Optional[str] = None
    user_id: Optional[int] = None
    username: Optional[str] = None
    created_at: str


class BatchAuditDetailsResponse(BaseModel):
    batch_id: int
    medicine_id: int
    medicine_name: str
    generic_salt: str
    dosage_form: str
    batch_number: str
    expiry_date: str
    pack_size: int
    current_quantity: int
    purchase_rate_paise: int
    mrp_paise: int
    rack_location: Optional[str] = None


# ==========================================
# MILESTONE 4: WANT-BOOK & REORDER
# ==========================================

class LowStockMedicineResponse(BaseModel):
    medicine_id: int
    brand_name: str
    generic_salt: str
    dosage_form: str
    pack_size: int
    min_stock_units: int
    current_stock_units: int
    current_packs: float
    suggested_reorder_packs: int
    rack_location: Optional[str] = None
    preferred_supplier_id: Optional[int] = None
    preferred_supplier_name: Optional[str] = None


class CreateWantBookRequest(BaseModel):
    medicine_id: int = Field(..., ge=1)
    requested_quantity_packs: int = Field(..., ge=1)
    supplier_id: Optional[int] = None
    notes: Optional[str] = None


class UpdateWantBookStatusRequest(BaseModel):
    status: Literal["PENDING", "ORDERED", "RECEIVED"]
    notes: Optional[str] = None


class WantBookResponse(BaseModel):
    id: int
    medicine_id: int
    medicine_name: str
    generic_salt: str
    dosage_form: str
    pack_size: int
    requested_quantity_packs: int
    current_stock_units: int
    min_stock_units: int
    status: str
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    notes: Optional[str] = None
    requested_by: Optional[int] = None
    requested_by_name: Optional[str] = None
    ordered_at: Optional[str] = None
    received_at: Optional[str] = None
    created_at: str
    updated_at: str


# ==========================================
# MILESTONE 5: CUSTOMER KHATA & AGING
# ==========================================

class KhataLedgerEntryResponse(BaseModel):
    id: int
    customer_id: int
    customer_name: Optional[str] = None
    transaction_type: str
    entry_type: str
    amount_paise: int
    balance_paise: int
    payment_mode: Optional[str] = None
    reference_type: str
    reference_id: Optional[int] = None
    receipt_no: Optional[str] = None
    notes: Optional[str] = None
    user_id: Optional[int] = None
    username: Optional[str] = None
    created_at: str


class CustomerDepositRequest(BaseModel):
    amount_paise: int = Field(..., ge=1)
    payment_mode: Literal["CASH", "UPI", "CARD", "BANK_TRANSFER", "CHEQUE"] = "CASH"
    notes: Optional[str] = None


class CustomerDepositReceiptResponse(BaseModel):
    receipt_no: str
    customer_id: int
    customer_name: str
    customer_phone: Optional[str] = None
    amount_paise: int
    previous_balance_paise: int
    new_balance_paise: int
    payment_mode: str
    notes: Optional[str] = None
    operator_name: Optional[str] = None
    created_at: str


class CustomerAgingBucketResponse(BaseModel):
    customer_id: int
    customer_name: str
    customer_phone: Optional[str] = None
    total_outstanding_paise: int
    credit_limit_paise: int
    bucket_0_30_paise: int
    bucket_31_60_paise: int
    bucket_60_plus_paise: int
    last_payment_date: Optional[str] = None


class CustomerAgingReportResponse(BaseModel):
    total_customers: int
    total_outstanding_paise: int
    total_0_30_paise: int
    total_31_60_paise: int
    total_60_plus_paise: int
    customers: List[CustomerAgingBucketResponse]


# ==========================================
# MILESTONE 5: CUSTOMER SALES RETURNS (CREDIT NOTES)
# ==========================================

class SalesReturnItemInput(BaseModel):
    sale_item_id: int = Field(..., ge=1)
    quantity_units: int = Field(..., ge=1)
    is_resellable: bool = True
    reason: Optional[str] = None


class SalesReturnCreateRequest(BaseModel):
    sale_invoice_id: int = Field(..., ge=1)
    refund_mode: Literal["CASH", "UPI", "CARD", "KHATA", "STORE_CREDIT"] = "CASH"
    reason: str = Field(..., min_length=1)
    notes: Optional[str] = None
    items: List[SalesReturnItemInput] = Field(..., min_length=1)


class SalesReturnItemResponse(BaseModel):
    id: int
    sales_return_id: int
    sale_item_id: int
    medicine_id: int
    medicine_name: str
    dosage_form: str
    pack_size: int
    batch_id: int
    batch_number: str
    expiry_date: str
    quantity_units: int
    unit_rate_paise: int
    taxable_amount_paise: int
    gst_rate: float
    cgst_amount_paise: int
    sgst_amount_paise: int
    total_amount_paise: int
    is_resellable: bool
    created_at: str


class SalesReturnResponse(BaseModel):
    id: int
    return_number: str
    sale_invoice_id: int
    invoice_no: str
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    refund_mode: str
    subtotal_taxable_paise: int
    total_cgst_paise: int
    total_sgst_paise: int
    total_igst_paise: int
    refund_amount_paise: int
    reason: str
    notes: Optional[str] = None
    created_by: Optional[int] = None
    created_by_name: Optional[str] = None
    created_at: str
    items: List[SalesReturnItemResponse]


class InvoiceReturnableItemResponse(BaseModel):
    sale_item_id: int
    medicine_id: int
    medicine_name: str
    dosage_form: str
    pack_size: int
    batch_id: int
    batch_number: str
    expiry_date: str
    is_expired: bool
    sold_quantity_units: int
    previously_returned_units: int
    returnable_quantity_units: int
    unit_rate_paise: int
    gst_rate: float
    discount_percent: float


class InvoiceForReturnLookupResponse(BaseModel):
    invoice_id: int
    invoice_no: str
    fiscal_year: str
    invoice_date: str
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_balance_paise: Optional[int] = None
    grand_total_paise: int
    payment_mode: str
    items: List[InvoiceReturnableItemResponse]


# ==========================================
# MILESTONE 5: SUPPLIER PURCHASE RETURNS (DEBIT NOTES)
# ==========================================

class PurchaseReturnItemInput(BaseModel):
    purchase_invoice_line_id: int = Field(..., ge=1)
    return_packs: Optional[int] = 0
    return_units: int = Field(..., ge=1)


class PurchaseReturnCreateRequest(BaseModel):
    purchase_invoice_id: int = Field(..., ge=1)
    reason: str = Field(..., min_length=1)
    notes: Optional[str] = None
    items: List[PurchaseReturnItemInput] = Field(..., min_length=1)


class PurchaseReturnItemResponse(BaseModel):
    id: int
    purchase_return_id: int
    purchase_invoice_line_id: int
    medicine_id: int
    medicine_name: str
    batch_id: int
    batch_number: str
    expiry_date: str
    return_packs: int
    return_units: int
    purchase_rate_paise: int
    taxable_amount_paise: int
    gst_percentage: float
    tax_amount_paise: int
    line_total_paise: int
    created_at: str


class PurchaseReturnResponse(BaseModel):
    id: int
    debit_note_number: str
    purchase_invoice_id: int
    supplier_invoice_number: str
    supplier_id: int
    supplier_name: str
    subtotal_taxable_paise: int
    total_tax_paise: int
    total_amount_paise: int
    reason: str
    notes: Optional[str] = None
    created_by: Optional[int] = None
    created_by_name: Optional[str] = None
    created_at: str
    items: List[PurchaseReturnItemResponse]


class PurchaseInvoiceReturnableLineResponse(BaseModel):
    purchase_invoice_line_id: int
    medicine_id: int
    medicine_name: str
    batch_id: int
    batch_number: str
    expiry_date: str
    pack_size: int
    total_received_units: int
    previously_returned_units: int
    available_return_units: int
    current_batch_stock_units: int
    purchase_rate_paise: int
    gst_percentage: float


class PurchaseInvoiceForReturnLookupResponse(BaseModel):
    invoice_id: int
    supplier_invoice_number: str
    supplier_id: int
    supplier_name: str
    invoice_date: str
    grand_total_paise: int
    supplier_current_payable_paise: int
    lines: List[PurchaseInvoiceReturnableLineResponse]


# ==========================================
# MILESTONE 5: WASTAGE & BREAKAGE REGISTER
# ==========================================

class WastageCreateRequest(BaseModel):
    batch_id: int = Field(..., ge=1)
    quantity_units: int = Field(..., ge=1)
    reason: Literal["EXPIRED", "BREAKAGE", "DAMAGED", "WASTAGE", "OTHER"]
    notes: Optional[str] = None

    @field_validator("notes")
    @classmethod
    def validate_notes_for_loss(cls, v: Optional[str], info) -> Optional[str]:
        reason = info.data.get("reason")
        if reason and reason != "EXPIRED":
            if not v or len(v.strip()) < 3:
                raise ValueError("Notes are mandatory (at least 3 characters) for non-expired breakage, damage, or wastage write-offs.")
        return v


class WastageRecordResponse(BaseModel):
    id: int
    reference_no: str
    batch_id: int
    medicine_id: int
    medicine_name: str
    batch_number: str
    expiry_date: str
    quantity_units: int
    pack_size: int
    reason: str
    cost_impact_paise: int
    notes: Optional[str] = None
    reference_type: Optional[str] = None
    reference_id: Optional[int] = None
    created_by: Optional[int] = None
    created_by_name: Optional[str] = None
    created_at: str


# =========================================================================
# MILESTONE 6: COMPLIANCE REPORTS, AUDITS, BACKUPS & LAN
# =========================================================================

# 1. Schedule H1 Register
class ScheduleH1ReportResponse(BaseModel):
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    total_records: int
    records: List[ScheduleH1RecordResponse]


# 2. GSTR-1 Tax Filing
class Gstr1B2BInvoiceResponse(BaseModel):
    customer_gstin: str
    customer_name: str
    invoice_no: str
    invoice_date: str
    invoice_value_paise: int
    taxable_value_paise: int
    gst_rate: float
    cgst_paise: int
    sgst_paise: int
    igst_paise: int
    place_of_supply: Optional[str] = None


class Gstr1B2CInvoiceResponse(BaseModel):
    invoice_no: str
    invoice_date: str
    customer_name: Optional[str] = None
    invoice_value_paise: int
    taxable_value_paise: int
    gst_rate: float
    cgst_paise: int
    sgst_paise: int
    igst_paise: int


class Gstr1HsnSummaryResponse(BaseModel):
    hsn_code: str
    description: str
    uqc: str
    total_quantity: int
    total_value_paise: int
    taxable_value_paise: int
    igst_paise: int
    cgst_paise: int
    sgst_paise: int


class Gstr1DocSequenceResponse(BaseModel):
    doc_type: str
    from_serial: str
    to_serial: str
    total_number: int
    cancelled_number: int
    net_number: int


class Gstr1TotalsResponse(BaseModel):
    total_taxable_paise: int
    total_cgst_paise: int
    total_sgst_paise: int
    total_igst_paise: int
    grand_total_paise: int


class Gstr1ReportResponse(BaseModel):
    from_date: str
    to_date: str
    fiscal_year: str
    b2b_invoices: List[Gstr1B2BInvoiceResponse]
    b2c_invoices: List[Gstr1B2CInvoiceResponse]
    hsn_summary: List[Gstr1HsnSummaryResponse]
    doc_summary: List[Gstr1DocSequenceResponse]
    totals: Gstr1TotalsResponse


# 3. GSTR-2 Purchase Register
class Gstr2SupplierGroupResponse(BaseModel):
    supplier_id: int
    supplier_name: str
    supplier_gstin: str
    invoice_count: int
    subtotal_taxable_paise: int
    total_tax_paise: int
    grand_total_paise: int


class Gstr2TotalsResponse(BaseModel):
    total_invoices: int
    total_taxable_paise: int
    total_tax_paise: int
    grand_total_paise: int


class Gstr2ReportResponse(BaseModel):
    from_date: str
    to_date: str
    suppliers: List[Gstr2SupplierGroupResponse]
    totals: Gstr2TotalsResponse


# 4. Sales & Purchase Registers
class SalesRegisterItemResponse(BaseModel):
    invoice_id: int
    invoice_no: str
    invoice_date: str
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    payment_mode: str
    item_count: int
    subtotal_taxable_paise: int
    total_cgst_paise: int
    total_sgst_paise: int
    total_igst_paise: int
    discount_paise: int
    round_off_paise: int
    grand_total_paise: int
    status: str


class PurchaseRegisterItemResponse(BaseModel):
    invoice_id: int
    supplier_invoice_number: str
    invoice_date: str
    supplier_name: str
    supplier_gstin: Optional[str] = None
    subtotal_paise: int
    discount_paise: int
    tax_amount_paise: int
    grand_total_paise: int
    status: str


# 5. Day-Book Cash Reconciliation
class DayBookSessionResponse(BaseModel):
    id: int
    session_date: str
    opening_float_paise: int
    cash_sales_paise: int
    cash_deposits_paise: int
    cash_refunds_paise: int
    expected_cash_paise: int
    actual_cash_paise: Optional[int] = None
    variance_paise: Optional[int] = None
    status: str
    closed_by: Optional[int] = None
    closed_by_name: Optional[str] = None
    closed_at: Optional[str] = None
    notes: Optional[str] = None
    created_at: str
    updated_at: str


class DayBookSummaryResponse(BaseModel):
    opening_float_paise: int
    cash_sales_paise: int
    cash_deposits_paise: int
    cash_refunds_paise: int
    expected_cash_paise: int


class DayBookCurrentResponse(BaseModel):
    session: DayBookSessionResponse
    payment_breakdown: Dict[str, int]
    summary: DayBookSummaryResponse


class DayBookOpeningFloatRequest(BaseModel):
    opening_float_paise: int = Field(..., ge=0)
    session_date: Optional[str] = None


class DayBookCloseRequest(BaseModel):
    actual_cash_paise: int = Field(..., ge=0)
    notes: Optional[str] = None


# 6. Hot Backups & Manifests
class BackupCreateRequest(BaseModel):
    notes: Optional[str] = None
    backup_type: Literal["MANUAL", "AUTOMATED", "PRE_RESTORE_SAFETY"] = "MANUAL"


class BackupManifestResponse(BaseModel):
    id: int
    filename: str
    filepath: str
    file_size_bytes: int
    sha256_hash: str
    backup_type: str
    status: str
    schema_version: int
    invoice_count: int
    medicine_count: int
    revenue_total_paise: int
    khata_balance_paise: int
    notes: Optional[str] = None
    created_by: Optional[int] = None
    created_by_name: Optional[str] = None
    created_at: str
    verified_at: Optional[str] = None


class BackupVerifyResponse(BaseModel):
    id: int
    filename: str
    is_valid: bool
    sha256_hash: str
    integrity_status: str
    message: str
    verified_at: str


# 7. Disaster Recovery & Safe Restore
class RestorePreviewResponse(BaseModel):
    staging_token: str
    filename: str
    created_at: str
    schema_version: int
    invoice_count: int
    medicine_count: int
    revenue_total_paise: int
    khata_balance_paise: int
    sha256_hash: str
    integrity_status: str
    is_compatible: bool
    message: str


class RestoreExecuteRequest(BaseModel):
    staging_token: str
    confirm: bool = Field(..., description="Must be true to execute restore")


class RestoreExecuteResponse(BaseModel):
    success: bool
    message: str
    safety_backup_filename: str
    restored_schema_version: int
    restored_at: str


# 8. System Config & LAN Discovery
class SystemConfigResponse(BaseModel):
    configs: Dict[str, str]


class SystemConfigUpdateRequest(BaseModel):
    configs: Dict[str, str]


class SystemDiscoveryResponse(BaseModel):
    server_name: str
    version: str
    server_mode: str
    host: str
    port: int
    lan_ips: List[str]
    database_status: str
    database_size_kb: float
    uptime_seconds: float
    platform: str
    mdns_enabled: bool


# 9. Hardware & Diagnostic Schemas
class HardwareTestRequest(BaseModel):
    printer_type: str = Field(default="thermal", description="thermal, laser, or network")
    target: Optional[str] = Field(default=None, description="Printer name or host:port")
    test_type: str = Field(default="receipt", description="receipt, invoice, or drawer_kick")
    simulation_mode: bool = Field(default=False, description="Simulate without hardware")


class HardwareTestResponse(BaseModel):
    success: bool
    printer_type: str
    target: str
    bytes_generated: int
    message: str
    is_simulated: bool
    hex_sample: Optional[str] = None
    ascii_preview: Optional[str] = None



