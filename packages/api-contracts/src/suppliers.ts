/**
 * Supplier, Distributor, and Stockist Master Contracts.
 */

export interface Supplier {
  id: number;
  name: string;
  gstin: string | null;
  dl_number_20b: string | null; // Retail/Wholesale Drug License 20B
  dl_number_21b: string | null; // Retail/Wholesale Drug License 21B
  phone: string | null;
  email: string | null;
  address: string | null;
  credit_days: number; // Payment terms (e.g. 21 days)
  current_payable_paise: number; // Net amount owed to distributor in paise
  is_active: boolean;
  created_at: string;
}

export interface CreateSupplierInput {
  name: string;
  gstin?: string | null;
  dl_number_20b?: string | null;
  dl_number_21b?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  credit_days?: number;
}

export interface UpdateSupplierInput {
  name?: string;
  gstin?: string | null;
  dl_number_20b?: string | null;
  dl_number_21b?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  credit_days?: number;
  is_active?: boolean;
}

export interface SupplierFilterParams {
  query?: string;
  has_outstanding?: boolean;
  is_active?: boolean;
  page?: number;
  page_size?: number;
}

export interface SupplierPayableSummary {
  supplier_id: number;
  supplier_name: string;
  current_payable_paise: number;
  pending_invoices_count: number;
  oldest_due_date?: string | null;
}
