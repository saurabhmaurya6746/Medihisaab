/**
 * Customer Khata ledger, aging reports, and deposit receipt API client functions.
 */

import type {
  ApiSuccessEnvelope,
  PaginatedResult,
  KhataLedgerEntry,
  CustomerDepositInput,
  CustomerDepositReceipt,
  CustomerAgingReport,
} from "@pharmacy/api-contracts";
import { apiClient } from "./client";

export interface CustomerBalanceInfo {
  customer_id: number;
  customer_name: string;
  phone?: string | null;
  current_balance_paise: number;
  credit_limit_paise: number;
  available_credit_paise: number;
  is_blocked: boolean;
}

/**
 * Fetch customer credit aging report across all outstanding accounts.
 */
export async function getCustomerAging(): Promise<CustomerAgingReport> {
  const resp = await apiClient<ApiSuccessEnvelope<CustomerAgingReport>>(
    "/api/v1/customers/aging"
  );
  return resp.data;
}

/**
 * Fetch ledger transactions for a specific customer.
 */
export async function getCustomerKhata(
  customerId: number,
  params?: { page?: number; page_size?: number }
): Promise<PaginatedResult<KhataLedgerEntry>> {
  const queryParams: Record<string, string | number | boolean | undefined> = {};
  if (params?.page !== undefined) queryParams.page = params.page;
  if (params?.page_size !== undefined) queryParams.page_size = params.page_size;

  const resp = await apiClient<ApiSuccessEnvelope<PaginatedResult<KhataLedgerEntry>>>(
    `/api/v1/customers/${customerId}/khata`,
    { params: queryParams }
  );
  return resp.data;
}

/**
 * Fetch live balance and credit limit headroom for a specific customer.
 */
export async function getCustomerBalance(customerId: number): Promise<CustomerBalanceInfo> {
  const resp = await apiClient<ApiSuccessEnvelope<CustomerBalanceInfo>>(
    `/api/v1/customers/${customerId}/balance`
  );
  return resp.data;
}

/**
 * Record a customer payment/deposit into their Khata account.
 */
export async function recordCustomerDeposit(
  customerId: number,
  payload: CustomerDepositInput
): Promise<CustomerDepositReceipt> {
  const resp = await apiClient<ApiSuccessEnvelope<CustomerDepositReceipt>>(
    `/api/v1/customers/${customerId}/payments`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
  return resp.data;
}

/**
 * Fetch deposit receipt details by receipt number.
 */
export async function getCustomerReceipt(receiptNo: string): Promise<CustomerDepositReceipt> {
  const resp = await apiClient<ApiSuccessEnvelope<CustomerDepositReceipt>>(
    `/api/v1/customers/receipts/${encodeURIComponent(receiptNo)}`
  );
  return resp.data;
}
