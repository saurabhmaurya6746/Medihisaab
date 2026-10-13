/**
 * Sales Returns (Credit Notes), Purchase Returns (Debit Notes), and Wastage API client service.
 */

import type {
  ApiSuccessEnvelope,
  PaginatedResult,
  InvoiceForReturnLookup,
  SalesReturnCreateInput,
  SalesReturn,
  PurchaseInvoiceForReturnLookup,
  PurchaseReturnCreateInput,
  PurchaseReturn,
  WastageCreateInput,
  WastageRecord,
} from "@pharmacy/api-contracts";
import { apiClient } from "./client";

/**
 * Look up a sale invoice by invoice number or ID to inspect returnable items.
 */
export async function lookupSaleInvoiceForReturn(
  invoiceIdentifier: string
): Promise<InvoiceForReturnLookup> {
  const resp = await apiClient<ApiSuccessEnvelope<InvoiceForReturnLookup>>(
    `/api/v1/returns/sales/invoice/${encodeURIComponent(invoiceIdentifier)}`
  );
  return resp.data;
}

/**
 * Process a customer sales return (credit note).
 */
export async function processSalesReturn(
  payload: SalesReturnCreateInput
): Promise<SalesReturn> {
  const resp = await apiClient<ApiSuccessEnvelope<SalesReturn>>(
    "/api/v1/returns/sales",
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
  return resp.data;
}

/**
 * List historical sales returns.
 */
export async function listSalesReturns(params?: {
  query?: string;
  customer_id?: number;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResult<SalesReturn>> {
  const queryParams: Record<string, string | number | boolean | undefined> = {};
  if (params?.query) queryParams.query = params.query;
  if (params?.customer_id) queryParams.customer_id = params.customer_id;
  if (params?.page !== undefined) queryParams.page = params.page;
  if (params?.page_size !== undefined) queryParams.page_size = params.page_size;

  const resp = await apiClient<ApiSuccessEnvelope<PaginatedResult<SalesReturn>>>(
    "/api/v1/returns/sales",
    { params: queryParams }
  );
  return resp.data;
}

/**
 * Get sales return details by ID.
 */
export async function getSalesReturn(id: number): Promise<SalesReturn> {
  const resp = await apiClient<ApiSuccessEnvelope<SalesReturn>>(
    `/api/v1/returns/sales/${id}`
  );
  return resp.data;
}

/**
 * Look up a purchase invoice by supplier invoice number or ID to inspect returnable items.
 */
export async function lookupPurchaseInvoiceForReturn(
  invoiceIdentifier: string
): Promise<PurchaseInvoiceForReturnLookup> {
  const resp = await apiClient<ApiSuccessEnvelope<PurchaseInvoiceForReturnLookup>>(
    `/api/v1/returns/purchases/invoice/${encodeURIComponent(invoiceIdentifier)}`
  );
  return resp.data;
}

/**
 * Process a supplier purchase return (debit note).
 */
export async function processPurchaseReturn(
  payload: PurchaseReturnCreateInput
): Promise<PurchaseReturn> {
  const resp = await apiClient<ApiSuccessEnvelope<PurchaseReturn>>(
    "/api/v1/returns/purchases",
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
  return resp.data;
}

/**
 * List historical purchase returns (debit notes).
 */
export async function listPurchaseReturns(params?: {
  query?: string;
  supplier_id?: number;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResult<PurchaseReturn>> {
  const queryParams: Record<string, string | number | boolean | undefined> = {};
  if (params?.query) queryParams.query = params.query;
  if (params?.supplier_id) queryParams.supplier_id = params.supplier_id;
  if (params?.page !== undefined) queryParams.page = params.page;
  if (params?.page_size !== undefined) queryParams.page_size = params.page_size;

  const resp = await apiClient<ApiSuccessEnvelope<PaginatedResult<PurchaseReturn>>>(
    "/api/v1/returns/purchases",
    { params: queryParams }
  );
  return resp.data;
}

/**
 * Get purchase return details by ID.
 */
export async function getPurchaseReturn(id: number): Promise<PurchaseReturn> {
  const resp = await apiClient<ApiSuccessEnvelope<PurchaseReturn>>(
    `/api/v1/returns/purchases/${id}`
  );
  return resp.data;
}

/**
 * Record a stock write-off (breakage, damage, expiry, scrap) in wastage register.
 */
export async function recordWastage(payload: WastageCreateInput): Promise<WastageRecord> {
  const resp = await apiClient<ApiSuccessEnvelope<WastageRecord>>(
    "/api/v1/inventory/wastage",
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
  return resp.data;
}

/**
 * List wastage register entries.
 */
export async function listWastage(params?: {
  reason?: string;
  batch_id?: number;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResult<WastageRecord>> {
  const queryParams: Record<string, string | number | boolean | undefined> = {};
  if (params?.reason) queryParams.reason = params.reason;
  if (params?.batch_id) queryParams.batch_id = params.batch_id;
  if (params?.page !== undefined) queryParams.page = params.page;
  if (params?.page_size !== undefined) queryParams.page_size = params.page_size;

  const resp = await apiClient<ApiSuccessEnvelope<PaginatedResult<WastageRecord>>>(
    "/api/v1/inventory/wastage",
    { params: queryParams }
  );
  return resp.data;
}
