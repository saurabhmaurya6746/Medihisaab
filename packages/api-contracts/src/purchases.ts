/**
 * Purchase Inwarding, Distributor Invoices, and Purchase Lines Contracts.
 */

export type PurchaseInvoiceStatus = "DRAFT" | "POSTED" | "CANCELLED";
export type PurchasePaymentStatus = "PAID" | "UNPAID" | "PARTIAL";

export interface PurchaseInvoiceLineInput {
  medicine_id: number;
  batch_number: string;
  expiry_date: string; // YYYY-MM or YYYY-MM-DD
  pack_size: number;
  paid_quantity: number;
  free_quantity?: number;
  purchase_rate_paise: number;
  mrp_paise: number;
  discount_paise?: number;
  gst_percentage?: number;
}

export interface PurchaseInvoiceLine {
  id: number;
  purchase_invoice_id: number;
  medicine_id: number;
  medicine_name?: string;
  dosage_form?: string;
  batch_number: string;
  expiry_date: string;
  pack_size: number;
  paid_quantity: number;
  free_quantity: number;
  total_received_quantity: number;
  purchase_rate_paise: number;
  mrp_paise: number;
  discount_paise: number;
  gst_percentage: number;
  tax_amount_paise: number;
  line_total_paise: number;
  created_at: string;
}

export interface CreatePurchaseInvoiceInput {
  supplier_id: number;
  supplier_invoice_number: string;
  invoice_date: string; // YYYY-MM-DD
  entry_date?: string; // YYYY-MM-DD
  discount_paise?: number;
  notes?: string | null;
  lines: PurchaseInvoiceLineInput[];
}

export interface UpdatePurchaseInvoiceInput {
  supplier_id?: number;
  supplier_invoice_number?: string;
  invoice_date?: string;
  entry_date?: string;
  discount_paise?: number;
  notes?: string | null;
  lines?: PurchaseInvoiceLineInput[];
}

export interface PurchaseInvoice {
  id: number;
  supplier_id: number;
  supplier_name?: string;
  supplier_invoice_number: string;
  invoice_date: string;
  entry_date: string;
  status: PurchaseInvoiceStatus;
  subtotal_paise: number;
  discount_paise: number;
  tax_amount_paise: number;
  grand_total_paise: number;
  payment_status: PurchasePaymentStatus;
  notes?: string | null;
  created_by?: number | null;
  creator_name?: string | null;
  created_at: string;
  posted_at?: string | null;
  updated_at: string;
  lines?: PurchaseInvoiceLine[];
}

export interface PurchaseFilterParams {
  supplier_id?: number;
  status?: PurchaseInvoiceStatus;
  from_date?: string;
  to_date?: string;
  query?: string;
  page?: number;
  page_size?: number;
}
