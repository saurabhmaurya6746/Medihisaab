/**
 * Sales POS, Counter Billing, FEFO Dispensing, and Schedule H1 Compliance Contracts.
 * All monetary amounts are strictly modeled as integer paise.
 */

export type SalePaymentMode = "CASH" | "UPI" | "CARD" | "KHATA" | "SPLIT";
export type SinglePaymentMode = "CASH" | "UPI" | "CARD" | "KHATA";
export type SaleInvoiceStatus = "COMPLETED" | "CANCELLED";

export interface ScheduleH1Input {
  patient_name: string;
  patient_address: string;
  doctor_name: string;
  doctor_address?: string | null;
}

export interface ScheduleH1Record {
  id: number;
  sale_item_id: number;
  patient_name: string;
  patient_address: string;
  doctor_name: string;
  doctor_address?: string | null;
  medicine_name: string;
  batch_number: string;
  quantity_units: number;
  dispensed_date: string;
  created_at: string;
}

export interface PaymentAllocationInput {
  payment_mode: SinglePaymentMode;
  amount_paise: number;
  reference_note?: string | null;
}

export interface SalePaymentRecord {
  id: number;
  sale_invoice_id: number;
  payment_mode: SinglePaymentMode;
  amount_paise: number;
  reference_note?: string | null;
  created_at: string;
}

export interface SaleLineInput {
  medicine_id: number;
  batch_id?: number | null; // Nullable for auto-picking earliest non-expired FEFO batch
  quantity_units: number; // Fundamental stock units (e.g. loose tablets)
  unit_rate_paise?: number | null; // Pro-rata unit rate; defaults to batch unit MRP
  discount_percent?: number; // Line discount percent (0.0 to 100.0)
  schedule_h1?: ScheduleH1Input | null;
}

export interface SaleItem {
  id: number;
  sale_invoice_id: number;
  medicine_id: number;
  medicine_name?: string;
  dosage_form?: string;
  generic_salt?: string;
  is_schedule_h1?: boolean;
  batch_id: number;
  batch_number: string;
  expiry_date: string;
  pack_size: number;
  quantity_units: number;
  unit_mrp_paise: number;
  unit_rate_paise: number;
  discount_percent: number;
  taxable_amount_paise: number;
  gst_rate: number;
  cgst_amount_paise: number;
  sgst_amount_paise: number;
  total_amount_paise: number;
  schedule_h1_record?: ScheduleH1Record | null;
  created_at: string;
}

export interface SaleInvoice {
  id: number;
  invoice_no: string;
  fiscal_year: string;
  sequence_number: number;
  customer_id?: number | null;
  customer_name?: string | null;
  customer_phone?: string | null;
  doctor_name?: string | null;
  doctor_address?: string | null;
  subtotal_taxable_paise: number;
  total_cgst_paise: number;
  total_sgst_paise: number;
  total_igst_paise: number;
  discount_paise: number;
  round_off_paise: number;
  grand_total_paise: number;
  payment_mode: SalePaymentMode;
  cash_tendered_paise: number;
  change_returned_paise: number;
  status: SaleInvoiceStatus;
  notes?: string | null;
  created_by?: number | null;
  creator_name?: string | null;
  created_at: string;
  updated_at: string;
  items: SaleItem[];
  payments: SalePaymentRecord[];
}

export interface SaleDraftCalculationRequest {
  lines: SaleLineInput[];
  discount_paise?: number;
  round_off_paise?: number;
  customer_id?: number | null;
}

export interface CalculatedDraftLine {
  medicine_id: number;
  medicine_name: string;
  dosage_form: string;
  generic_salt: string;
  is_schedule_h1: boolean;
  batch_id: number;
  batch_number: string;
  expiry_date: string;
  pack_size: number;
  available_stock_units: number;
  quantity_units: number;
  unit_mrp_paise: number;
  unit_rate_paise: number;
  discount_percent: number;
  discount_amount_paise: number;
  taxable_amount_paise: number;
  gst_rate: number;
  cgst_amount_paise: number;
  sgst_amount_paise: number;
  total_amount_paise: number;
  is_near_expiry: boolean;
  schedule_h1?: ScheduleH1Input | null;
}

export interface SaleDraftCalculationResponse {
  lines: CalculatedDraftLine[];
  subtotal_taxable_paise: number;
  total_cgst_paise: number;
  total_sgst_paise: number;
  total_tax_paise: number;
  discount_paise: number;
  round_off_paise: number;
  grand_total_paise: number;
  requires_schedule_h1: boolean;
  missing_schedule_h1_count: number;
}

export interface SaleCheckoutRequest {
  customer_id?: number | null;
  customer_name?: string | null;
  customer_phone?: string | null;
  doctor_name?: string | null;
  doctor_address?: string | null;
  lines: SaleLineInput[];
  payment_mode: SalePaymentMode;
  payments?: PaymentAllocationInput[];
  cash_tendered_paise?: number;
  discount_paise?: number;
  round_off_paise?: number;
  notes?: string | null;
  held_bill_id?: number | null;
}

export interface HeldBillItem {
  medicine_id: number;
  medicine_name: string;
  dosage_form: string;
  generic_salt?: string;
  is_schedule_h1: boolean;
  batch_id: number;
  batch_number: string;
  expiry_date: string;
  pack_size: number;
  quantity_units: number;
  unit_mrp_paise: number;
  unit_rate_paise: number;
  discount_percent: number;
  gst_rate: number;
  total_amount_paise: number;
  schedule_h1?: ScheduleH1Input | null;
}

export interface CreateHeldBillRequest {
  hold_reference?: string | null;
  customer_id?: number | null;
  customer_name?: string | null;
  customer_phone?: string | null;
  doctor_name?: string | null;
  doctor_address?: string | null;
  notes?: string | null;
  items: HeldBillItem[];
}

export interface HeldBill {
  id: number;
  hold_reference: string;
  customer_id?: number | null;
  customer_name?: string | null;
  customer_phone?: string | null;
  doctor_name?: string | null;
  doctor_address?: string | null;
  items: HeldBillItem[];
  subtotal_paise: number;
  total_tax_paise: number;
  grand_total_paise: number;
  notes?: string | null;
  created_by?: number | null;
  creator_name?: string | null;
  created_at: string;
  updated_at: string;
}

export interface SubstituteMedicine {
  id: number;
  brand_name: string;
  generic_salt: string;
  dosage_form: string;
  pack_size: number;
  rack_location?: string | null;
  is_schedule_h1: boolean;
  gst_rate: number;
  total_stock_units: number;
  recommended_batch_id?: number | null;
  recommended_batch_number?: string | null;
  recommended_expiry_date?: string | null;
  recommended_mrp_paise?: number | null;
  available_batches_count: number;
}

export interface PrintInvoiceRequest {
  printer_type: "thermal" | "laser";
  printer_name?: string | null;
}

export interface PrintInvoiceResponse {
  printed: boolean;
  printer_type: "thermal" | "laser";
  message: string;
}
