/**
 * Inventory Control, Expiry Dashboard, Stock Audits, and Want-Book API client service functions.
 */

import type {
  ApiSuccessEnvelope,
  PaginatedResult,
  ExpiryFilterType,
  ExpiryDashboardResponse,
  SupplierReturnDumpGroup,
  StockAdjustmentRecord,
  StockAdjustmentCreateInput,
  BatchAuditDetails,
  LowStockMedicineItem,
  WantBookItem,
  WantBookCreateInput,
  WantBookStatusUpdateInput,
  WantBookStatus,
  OpeningStockImportPreviewResponse,
  OpeningStockImportExecuteInput,
  OpeningStockImportExecuteResponse,
} from "@pharmacy/api-contracts";
export type { OpeningStockDuplicatePolicy } from "@pharmacy/api-contracts";
import { apiClient, getStoredToken, ApiError } from "./client";

/**
 * Expiry Dashboard & Batches
 */
export async function getExpiryDashboard(params?: {
  filter?: ExpiryFilterType;
  query?: string;
  page?: number;
  page_size?: number;
}): Promise<ExpiryDashboardResponse> {
  const queryParams: Record<string, string | number | boolean | undefined> = {};
  if (params?.filter) queryParams.filter = params.filter;
  if (params?.query) queryParams.query = params.query;
  if (params?.page !== undefined) queryParams.page = params.page;
  if (params?.page_size !== undefined) queryParams.page_size = params.page_size;

  const resp = await apiClient<ApiSuccessEnvelope<ExpiryDashboardResponse>>(
    "/api/v1/inventory/expiry",
    { params: queryParams }
  );
  return resp.data;
}

/**
 * Near-expiry return dump grouped by supplier
 */
export async function getSupplierReturnDump(params?: {
  days?: number;
  supplier_id?: number;
}): Promise<SupplierReturnDumpGroup[]> {
  const queryParams: Record<string, string | number | boolean | undefined> = {};
  if (params?.days !== undefined) queryParams.days = params.days;
  if (params?.supplier_id !== undefined) queryParams.supplier_id = params.supplier_id;

  const resp = await apiClient<ApiSuccessEnvelope<SupplierReturnDumpGroup[]>>(
    "/api/v1/inventory/expiry/return-dump",
    { params: queryParams }
  );
  return resp.data;
}

/**
 * Stock Audits - List adjustment history
 */
export async function listStockAudits(params?: {
  search?: string;
  reason?: string;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResult<StockAdjustmentRecord>> {
  const queryParams: Record<string, string | number | boolean | undefined> = {};
  if (params?.search) queryParams.search = params.search;
  if (params?.reason) queryParams.reason = params.reason;
  if (params?.page !== undefined) queryParams.page = params.page;
  if (params?.page_size !== undefined) queryParams.page_size = params.page_size;

  const resp = await apiClient<ApiSuccessEnvelope<PaginatedResult<StockAdjustmentRecord>>>(
    "/api/v1/inventory/audits",
    { params: queryParams }
  );
  return resp.data;
}

/**
 * Stock Audits - Get single batch count details
 */
export async function getBatchAuditDetails(batchId: number): Promise<BatchAuditDetails> {
  const resp = await apiClient<ApiSuccessEnvelope<BatchAuditDetails>>(
    `/api/v1/inventory/audits/batch/${batchId}`
  );
  return resp.data;
}

/**
 * Stock Audits - Submit physical count variance adjustment
 */
export async function submitStockAudit(
  input: StockAdjustmentCreateInput
): Promise<StockAdjustmentRecord> {
  const resp = await apiClient<ApiSuccessEnvelope<StockAdjustmentRecord>>(
    "/api/v1/inventory/audits",
    {
      method: "POST",
      body: JSON.stringify(input),
    }
  );
  return resp.data;
}

/**
 * Want-Book - Automatic low-stock detection
 */
export async function getLowStockMedicines(params?: {
  query?: string;
  limit?: number;
}): Promise<LowStockMedicineItem[]> {
  const queryParams: Record<string, string | number | boolean | undefined> = {};
  if (params?.query) queryParams.query = params.query;
  if (params?.limit !== undefined) queryParams.limit = params.limit;

  const resp = await apiClient<ApiSuccessEnvelope<LowStockMedicineItem[]>>(
    "/api/v1/inventory/want-book/low-stock",
    { params: queryParams }
  );
  return resp.data;
}

/**
 * Want-Book - List items
 */
export async function listWantBook(params?: {
  status?: WantBookStatus;
  query?: string;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResult<WantBookItem>> {
  const queryParams: Record<string, string | number | boolean | undefined> = {};
  if (params?.status) queryParams.status = params.status;
  if (params?.query) queryParams.query = params.query;
  if (params?.page !== undefined) queryParams.page = params.page;
  if (params?.page_size !== undefined) queryParams.page_size = params.page_size;

  const resp = await apiClient<ApiSuccessEnvelope<PaginatedResult<WantBookItem>>>(
    "/api/v1/inventory/want-book",
    { params: queryParams }
  );
  return resp.data;
}

/**
 * Want-Book - Create reorder item
 */
export async function createWantBookItem(
  input: WantBookCreateInput
): Promise<WantBookItem> {
  const resp = await apiClient<ApiSuccessEnvelope<WantBookItem>>(
    "/api/v1/inventory/want-book",
    {
      method: "POST",
      body: JSON.stringify(input),
    }
  );
  return resp.data;
}

/**
 * Want-Book - Update status
 */
export async function updateWantBookStatus(
  id: number,
  input: WantBookStatusUpdateInput
): Promise<WantBookItem> {
  const resp = await apiClient<ApiSuccessEnvelope<WantBookItem>>(
    `/api/v1/inventory/want-book/${id}/status`,
    {
      method: "PATCH",
      body: JSON.stringify(input),
    }
  );
  return resp.data;
}

/**
 * Want-Book - Delete item
 */
export async function deleteWantBookItem(id: number): Promise<void> {
  await apiClient<ApiSuccessEnvelope<{ deleted: boolean }>>(
    `/api/v1/inventory/want-book/${id}`,
    { method: "DELETE" }
  );
}

// ==========================================
// 5. BULK OPENING STOCK IMPORT
// ==========================================

export async function downloadOpeningStockImportTemplate(format: "csv" | "xlsx" = "xlsx"): Promise<void> {
  const token = getStoredToken();
  const res = await fetch(`/api/v1/inventory/opening-stock/import/template?format=${format}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    throw new ApiError(res.status, "Failed to download opening stock template");
  }
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `medihisaab_opening_stock_template.${format}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Keep the object URL alive until the browser has consumed the download.
  window.setTimeout(() => window.URL.revokeObjectURL(url), 1000);
}

export async function previewOpeningStockImport(file: File): Promise<OpeningStockImportPreviewResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const resp = await apiClient<ApiSuccessEnvelope<OpeningStockImportPreviewResponse>>(
    "/api/v1/inventory/opening-stock/import-preview",
    {
      method: "POST",
      body: formData,
    }
  );
  return resp.data;
}

export async function executeOpeningStockImport(
  payload: OpeningStockImportExecuteInput
): Promise<OpeningStockImportExecuteResponse> {
  const resp = await apiClient<ApiSuccessEnvelope<OpeningStockImportExecuteResponse>>(
    "/api/v1/inventory/opening-stock/import-execute",
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
  return resp.data;
}

