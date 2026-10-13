/**
 * Purchase Inwarding & Inventory API client service functions.
 */

import type {
  PurchaseInvoice,
  CreatePurchaseInvoiceInput,
  UpdatePurchaseInvoiceInput,
  PurchaseFilterParams,
  MedicineBatch,
  SupplierPayableHistoryResponse,
  PaginatedResult,
  ApiSuccessEnvelope,
} from "@pharmacy/api-contracts";
import { apiClient } from "./client";

export async function listPurchases(
  params?: PurchaseFilterParams
): Promise<PaginatedResult<PurchaseInvoice>> {
  const queryParams: Record<string, string | number | boolean | undefined> = {};
  if (params?.supplier_id !== undefined) queryParams.supplier_id = params.supplier_id;
  if (params?.status) queryParams.status = params.status;
  if (params?.from_date) queryParams.from_date = params.from_date;
  if (params?.to_date) queryParams.to_date = params.to_date;
  if (params?.query) queryParams.query = params.query;
  if (params?.page !== undefined) queryParams.page = params.page;
  if (params?.page_size !== undefined) queryParams.page_size = params.page_size;

  const resp = await apiClient<ApiSuccessEnvelope<PaginatedResult<PurchaseInvoice>>>("/api/v1/purchases", {
    params: queryParams,
  });
  return resp.data;
}

export async function getPurchaseInvoice(id: number): Promise<PurchaseInvoice> {
  const resp = await apiClient<ApiSuccessEnvelope<PurchaseInvoice>>(`/api/v1/purchases/${id}`);
  return resp.data;
}

export async function createPurchaseInvoice(payload: CreatePurchaseInvoiceInput): Promise<PurchaseInvoice> {
  const resp = await apiClient<ApiSuccessEnvelope<PurchaseInvoice>>("/api/v1/purchases", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return resp.data;
}

export async function updatePurchaseInvoice(
  id: number,
  payload: UpdatePurchaseInvoiceInput
): Promise<PurchaseInvoice> {
  const resp = await apiClient<ApiSuccessEnvelope<PurchaseInvoice>>(`/api/v1/purchases/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  return resp.data;
}

export async function postPurchaseInvoice(id: number): Promise<PurchaseInvoice> {
  const resp = await apiClient<ApiSuccessEnvelope<PurchaseInvoice>>(`/api/v1/purchases/${id}/post`, {
    method: "POST",
  });
  return resp.data;
}

export async function listBatches(params?: {
  medicine_id?: number;
  query?: string;
  is_active?: boolean;
  in_stock_only?: boolean;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResult<MedicineBatch>> {
  const queryParams: Record<string, string | number | boolean | undefined> = {};
  if (params?.medicine_id !== undefined) queryParams.medicine_id = params.medicine_id;
  if (params?.query) queryParams.query = params.query;
  if (params?.is_active !== undefined) queryParams.is_active = params.is_active;
  if (params?.in_stock_only !== undefined) queryParams.in_stock_only = params.in_stock_only;
  if (params?.page !== undefined) queryParams.page = params.page;
  if (params?.page_size !== undefined) queryParams.page_size = params.page_size;

  const resp = await apiClient<ApiSuccessEnvelope<PaginatedResult<MedicineBatch>>>("/api/v1/inventory/batches", {
    params: queryParams,
  });
  return resp.data;
}

export async function getSupplierPayablesHistory(supplierId: number): Promise<SupplierPayableHistoryResponse> {
  const resp = await apiClient<ApiSuccessEnvelope<SupplierPayableHistoryResponse>>(
    `/api/v1/suppliers/${supplierId}/payables`
  );
  return resp.data;
}
