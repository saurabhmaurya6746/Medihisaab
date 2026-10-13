/**
 * Customer Master and Patient Profile Contracts.
 */

export interface Customer {
  id: number;
  name: string;
  phone: string | null;
  address: string | null;
  default_doctor: string | null;
  credit_limit_paise: number; // Max allowed Khata debit in paise (default ₹5,000 = 500,000 paise)
  current_balance_paise: number; // Positive = Customer owes money to store in paise
  is_active: boolean;
  created_at: string;
  updated_at?: string | null;
}

export interface CreateCustomerInput {
  name: string;
  phone?: string | null;
  address?: string | null;
  default_doctor?: string | null;
  credit_limit_paise?: number;
}

export interface UpdateCustomerInput {
  name?: string;
  phone?: string | null;
  address?: string | null;
  default_doctor?: string | null;
  credit_limit_paise?: number;
  is_active?: boolean;
}

export interface CustomerFilterParams {
  query?: string;
  has_khata_debt?: boolean;
  is_active?: boolean;
  page?: number;
  page_size?: number;
}

export interface CustomerKhataProfile {
  customer: Customer;
  available_credit_paise: number;
  is_credit_exceeded: boolean;
  last_transaction_date?: string | null;
}

// ==========================================
// MILESTONE 5: CUSTOMER KHATA LEDGER & AGING
// ==========================================

export type KhataTransactionType =
  | "SALE_CREDIT"
  | "PAYMENT"
  | "RETURN_REFUND"
  | "ADJUSTMENT";

export type KhataEntryType = "DEBIT" | "CREDIT";

export type KhataPaymentMode = "CASH" | "UPI" | "CARD" | "BANK_TRANSFER" | "CHEQUE";

export interface KhataLedgerEntry {
  id: number;
  customer_id: number;
  customer_name?: string;
  transaction_type: KhataTransactionType;
  entry_type: KhataEntryType;
  amount_paise: number;
  balance_paise: number;
  payment_mode?: KhataPaymentMode | null;
  reference_type: string;
  reference_id?: number | null;
  receipt_no?: string | null;
  notes?: string | null;
  user_id?: number | null;
  username?: string | null;
  created_at: string;
}

export interface CustomerDepositInput {
  amount_paise: number;
  payment_mode: KhataPaymentMode;
  notes?: string | null;
}

export interface CustomerDepositReceipt {
  receipt_no: string;
  customer_id: number;
  customer_name: string;
  customer_phone?: string | null;
  amount_paise: number;
  previous_balance_paise: number;
  new_balance_paise: number;
  payment_mode: KhataPaymentMode;
  notes?: string | null;
  operator_name?: string | null;
  created_at: string;
}

export interface CustomerAgingBucket {
  customer_id: number;
  customer_name: string;
  customer_phone?: string | null;
  total_outstanding_paise: number;
  credit_limit_paise: number;
  bucket_0_30_paise: number;
  bucket_31_60_paise: number;
  bucket_60_plus_paise: number;
  last_payment_date?: string | null;
}

export interface CustomerAgingReport {
  total_customers: number;
  total_outstanding_paise: number;
  total_0_30_paise: number;
  total_31_60_paise: number;
  total_60_plus_paise: number;
  customers: CustomerAgingBucket[];
}
