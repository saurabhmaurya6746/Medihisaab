/**
 * Compliance and Statutory Reports Contracts:
 * Schedule H1 Register, GSTR-1, GSTR-2, Sales/Purchase Registers, and Day-Book Cash Reconciliation.
 */

// ==========================================
// 1. SCHEDULE H1 REGISTER
// ==========================================

export interface ScheduleH1RecordItem {
  id: number;
  sale_item_id: number;
  sale_invoice_id: number;
  invoice_no: string;
  dispensed_date: string;
  medicine_name: string;
  batch_number: string;
  quantity_units: number;
  patient_name: string;
  patient_address: string;
  doctor_name: string;
  doctor_address?: string | null;
  created_at: string;
}

export interface ScheduleH1ReportResponse {
  from_date?: string | null;
  to_date?: string | null;
  total_records: number;
  records: ScheduleH1RecordItem[];
}

// ==========================================
// 2. GSTR-1 TAX FILING
// ==========================================

export interface Gstr1B2BInvoiceItem {
  customer_gstin: string;
  customer_name: string;
  invoice_no: string;
  invoice_date: string;
  invoice_value_paise: number;
  taxable_value_paise: number;
  gst_rate: number;
  cgst_paise: number;
  sgst_paise: number;
  igst_paise: number;
  place_of_supply?: string | null;
}

export interface Gstr1B2CInvoiceItem {
  invoice_no: string;
  invoice_date: string;
  customer_name?: string | null;
  invoice_value_paise: number;
  taxable_value_paise: number;
  gst_rate: number;
  cgst_paise: number;
  sgst_paise: number;
  igst_paise: number;
}

export interface Gstr1HsnSummaryItem {
  hsn_code: string;
  description: string;
  uqc: string;
  total_quantity: number;
  total_value_paise: number;
  taxable_value_paise: number;
  igst_paise: number;
  cgst_paise: number;
  sgst_paise: number;
}

export interface Gstr1DocSequenceItem {
  doc_type: string;
  from_serial: string;
  to_serial: string;
  total_number: number;
  cancelled_number: number;
  net_number: number;
}

export interface Gstr1ReportResponse {
  from_date: string;
  to_date: string;
  fiscal_year: string;
  b2b_invoices: Gstr1B2BInvoiceItem[];
  b2c_invoices: Gstr1B2CInvoiceItem[];
  hsn_summary: Gstr1HsnSummaryItem[];
  doc_summary: Gstr1DocSequenceItem[];
  totals: {
    total_taxable_paise: number;
    total_cgst_paise: number;
    total_sgst_paise: number;
    total_igst_paise: number;
    grand_total_paise: number;
  };
}

// ==========================================
// 3. GSTR-2 PURCHASE REGISTER
// ==========================================

export interface Gstr2SupplierGroupItem {
  supplier_id: number;
  supplier_name: string;
  supplier_gstin: string;
  invoice_count: number;
  subtotal_taxable_paise: number;
  total_tax_paise: number;
  grand_total_paise: number;
}

export interface Gstr2ReportResponse {
  from_date: string;
  to_date: string;
  suppliers: Gstr2SupplierGroupItem[];
  totals: {
    total_invoices: number;
    total_taxable_paise: number;
    total_tax_paise: number;
    grand_total_paise: number;
  };
}

// ==========================================
// 4. SALES & PURCHASE REGISTERS
// ==========================================

export interface SalesRegisterItem {
  invoice_id: number;
  invoice_no: string;
  invoice_date: string;
  customer_name?: string | null;
  customer_phone?: string | null;
  payment_mode: string;
  item_count: number;
  subtotal_taxable_paise: number;
  total_cgst_paise: number;
  total_sgst_paise: number;
  total_igst_paise: number;
  discount_paise: number;
  round_off_paise: number;
  grand_total_paise: number;
  status: string;
}

export interface PurchaseRegisterItem {
  invoice_id: number;
  supplier_invoice_number: string;
  invoice_date: string;
  supplier_name: string;
  supplier_gstin?: string | null;
  subtotal_paise: number;
  discount_paise: number;
  tax_amount_paise: number;
  grand_total_paise: number;
  status: string;
}

// ==========================================
// 5. DAY-BOOK & CASH RECONCILIATION
// ==========================================

export type CashSessionStatus = "OPEN" | "CLOSED";

export interface DayBookSession {
  id: number;
  session_date: string;
  opening_float_paise: number;
  cash_sales_paise: number;
  cash_deposits_paise: number;
  cash_refunds_paise: number;
  expected_cash_paise: number;
  actual_cash_paise?: number | null;
  variance_paise?: number | null;
  status: CashSessionStatus;
  closed_by?: number | null;
  closed_by_name?: string | null;
  closed_at?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface DayBookCurrentResponse {
  session: DayBookSession;
  payment_breakdown: Record<string, number>; // mode -> total paise
  summary: {
    opening_float_paise: number;
    cash_sales_paise: number;
    cash_deposits_paise: number;
    cash_refunds_paise: number;
    expected_cash_paise: number;
  };
}

export interface DayBookCloseInput {
  actual_cash_paise: number;
  notes?: string | null;
}

export interface DayBookOpeningFloatInput {
  opening_float_paise: number;
  session_date?: string | null;
}
