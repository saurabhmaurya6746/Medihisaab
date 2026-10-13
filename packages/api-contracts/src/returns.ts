/**
 * Sales Returns (Credit Notes), Purchase Returns (Debit Notes), and Wastage Register Contracts.
 */

// ==========================================
// 1. CUSTOMER SALES RETURNS (CREDIT NOTES)
// ==========================================

export type SalesReturnRefundMode =
  | "CASH"
  | "UPI"
  | "CARD"
  | "KHATA"
  | "STORE_CREDIT";

export interface SalesReturnItemInput {
  sale_item_id: number;
  quantity_units: number;
  is_resellable: boolean;
  reason?: string | null;
}

export interface SalesReturnCreateInput {
  sale_invoice_id: number;
  refund_mode: SalesReturnRefundMode;
  reason: string;
  notes?: string | null;
  items: SalesReturnItemInput[];
}

export interface SalesReturnItem {
  id: number;
  sales_return_id: number;
  sale_item_id: number;
  medicine_id: number;
  medicine_name: string;
  dosage_form: string;
  pack_size: number;
  batch_id: number;
  batch_number: string;
  expiry_date: string;
  quantity_units: number;
  unit_rate_paise: number;
  taxable_amount_paise: number;
  gst_rate: number;
  cgst_amount_paise: number;
  sgst_amount_paise: number;
  total_amount_paise: number;
  is_resellable: boolean;
  created_at: string;
}

export interface SalesReturn {
  id: number;
  return_number: string;
  sale_invoice_id: number;
  invoice_no: string;
  customer_id?: number | null;
  customer_name?: string | null;
  refund_mode: SalesReturnRefundMode;
  subtotal_taxable_paise: number;
  total_cgst_paise: number;
  total_sgst_paise: number;
  total_igst_paise: number;
  refund_amount_paise: number;
  reason: string;
  notes?: string | null;
  created_by?: number | null;
  created_by_name?: string | null;
  created_at: string;
  items: SalesReturnItem[];
}

export interface InvoiceReturnableItem {
  sale_item_id: number;
  medicine_id: number;
  medicine_name: string;
  dosage_form: string;
  pack_size: number;
  batch_id: number;
  batch_number: string;
  expiry_date: string;
  is_expired: boolean;
  sold_quantity_units: number;
  previously_returned_units: number;
  returnable_quantity_units: number;
  unit_rate_paise: number;
  gst_rate: number;
  discount_percent: number;
}

export interface InvoiceForReturnLookup {
  invoice_id: number;
  invoice_no: string;
  fiscal_year: string;
  invoice_date: string;
  customer_id?: number | null;
  customer_name?: string | null;
  customer_phone?: string | null;
  customer_balance_paise?: number | null;
  grand_total_paise: number;
  payment_mode: string;
  items: InvoiceReturnableItem[];
}

// ==========================================
// 2. SUPPLIER PURCHASE RETURNS (DEBIT NOTES)
// ==========================================

export interface PurchaseReturnItemInput {
  purchase_invoice_line_id: number;
  return_packs?: number;
  return_units: number;
}

export interface PurchaseReturnCreateInput {
  purchase_invoice_id: number;
  reason: string;
  notes?: string | null;
  items: PurchaseReturnItemInput[];
}

export interface PurchaseReturnItem {
  id: number;
  purchase_return_id: number;
  purchase_invoice_line_id: number;
  medicine_id: number;
  medicine_name: string;
  batch_id: number;
  batch_number: string;
  expiry_date: string;
  return_packs: number;
  return_units: number;
  purchase_rate_paise: number;
  taxable_amount_paise: number;
  gst_percentage: number;
  tax_amount_paise: number;
  line_total_paise: number;
  created_at: string;
}

export interface PurchaseReturn {
  id: number;
  debit_note_number: string;
  purchase_invoice_id: number;
  supplier_invoice_number: string;
  supplier_id: number;
  supplier_name: string;
  subtotal_taxable_paise: number;
  total_tax_paise: number;
  total_amount_paise: number;
  reason: string;
  notes?: string | null;
  created_by?: number | null;
  created_by_name?: string | null;
  created_at: string;
  items: PurchaseReturnItem[];
}

export interface PurchaseInvoiceReturnableLine {
  purchase_invoice_line_id: number;
  medicine_id: number;
  medicine_name: string;
  batch_id: number;
  batch_number: string;
  expiry_date: string;
  pack_size: number;
  total_received_units: number;
  previously_returned_units: number;
  available_return_units: number;
  current_batch_stock_units: number;
  purchase_rate_paise: number;
  gst_percentage: number;
}

export interface PurchaseInvoiceForReturnLookup {
  invoice_id: number;
  supplier_invoice_number: string;
  supplier_id: number;
  supplier_name: string;
  invoice_date: string;
  grand_total_paise: number;
  supplier_current_payable_paise: number;
  lines: PurchaseInvoiceReturnableLine[];
}

// ==========================================
// 3. WASTAGE & BREAKAGE REGISTER
// ==========================================

export type WastageReason =
  | "EXPIRED"
  | "BREAKAGE"
  | "DAMAGED"
  | "WASTAGE"
  | "OTHER";

export interface WastageCreateInput {
  batch_id: number;
  quantity_units: number;
  reason: WastageReason;
  notes?: string | null;
}

export interface WastageRecord {
  id: number;
  reference_no: string;
  batch_id: number;
  medicine_id: number;
  medicine_name: string;
  batch_number: string;
  expiry_date: string;
  quantity_units: number;
  pack_size: number;
  reason: WastageReason;
  cost_impact_paise: number;
  notes?: string | null;
  reference_type?: string | null;
  reference_id?: number | null;
  created_by?: number | null;
  created_by_name?: string | null;
  created_at: string;
}
