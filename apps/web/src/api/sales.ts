/**
 * Sales POS & Counter Billing API Client Services.
 */

import type {
  ApiSuccessEnvelope,
  CreateHeldBillRequest,
  HeldBill,
  PaginatedResult,
  PrintInvoiceRequest,
  PrintInvoiceResponse,
  SaleCheckoutRequest,
  SaleDraftCalculationRequest,
  SaleDraftCalculationResponse,
  SaleInvoice,
  SubstituteMedicine,
} from "@pharmacy/api-contracts";
import { apiClient } from "./client";

export interface SearchMedicineResult {
  id: number;
  brand_name: string;
  generic_salt: string;
  dosage_form: string;
  pack_size: number;
  hsn_code: string;
  gst_rate: number;
  is_schedule_h1: boolean;
  rack_location?: string | null;
  barcode?: string | null;
  total_available_stock: number;
  fefo_batch?: {
    id: number;
    batch_number: string;
    expiry_date: string;
    mrp_paise: number;
    unit_mrp_paise: number;
    current_quantity: number;
  } | null;
}

export interface BatchItemResult {
  id: number;
  medicine_id: number;
  batch_number: string;
  expiry_date: string;
  mrp_paise: number;
  unit_mrp_paise: number;
  purchase_rate_paise: number;
  pack_size: number;
  current_quantity: number;
  reserved_quantity: number;
  is_expired: boolean;
  is_available: boolean;
  is_active: boolean;
}

export async function searchMedicines(params: {
  query?: string;
  barcode?: string;
  limit?: number;
}): Promise<SearchMedicineResult[]> {
  const queryParams: Record<string, string | number | boolean | undefined> = {};
  if (params.query) queryParams.query = params.query;
  if (params.barcode) queryParams.barcode = params.barcode;
  if (params.limit) queryParams.limit = params.limit;

  const resp = await apiClient<ApiSuccessEnvelope<SearchMedicineResult[]>>("/api/v1/sales/search-medicines", {
    params: queryParams,
  });
  return resp.data;
}

export async function listBatchesFEFO(params: {
  medicine_id: number;
  include_out_of_stock?: boolean;
  include_expired?: boolean;
}): Promise<BatchItemResult[]> {
  const queryParams: Record<string, string | number | boolean | undefined> = {
    medicine_id: params.medicine_id,
  };
  if (params.include_out_of_stock !== undefined) queryParams.include_out_of_stock = params.include_out_of_stock;
  if (params.include_expired !== undefined) queryParams.include_expired = params.include_expired;

  const resp = await apiClient<ApiSuccessEnvelope<BatchItemResult[]>>("/api/v1/sales/batches", {
    params: queryParams,
  });
  return resp.data;
}

export async function findSubstitutes(params: {
  medicine_id?: number;
  generic_salt?: string;
  dosage_form?: string;
}): Promise<SubstituteMedicine[]> {
  const queryParams: Record<string, string | number | boolean | undefined> = {};
  if (params.medicine_id !== undefined) queryParams.medicine_id = params.medicine_id;
  if (params.generic_salt) queryParams.generic_salt = params.generic_salt;
  if (params.dosage_form) queryParams.dosage_form = params.dosage_form;

  const resp = await apiClient<ApiSuccessEnvelope<SubstituteMedicine[]>>("/api/v1/sales/substitutes", {
    params: queryParams,
  });
  return resp.data;
}

export async function calculateDraft(
  payload: SaleDraftCalculationRequest
): Promise<SaleDraftCalculationResponse> {
  const resp = await apiClient<ApiSuccessEnvelope<SaleDraftCalculationResponse>>(
    "/api/v1/sales/draft-calculate",
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
  return resp.data;
}

export async function checkoutSale(payload: SaleCheckoutRequest): Promise<SaleInvoice> {
  const resp = await apiClient<ApiSuccessEnvelope<SaleInvoice>>("/api/v1/sales/checkout", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return resp.data;
}

export async function listSaleInvoices(params?: {
  query?: string;
  from_date?: string;
  to_date?: string;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResult<SaleInvoice>> {
  const queryParams: Record<string, string | number | boolean | undefined> = {};
  if (params?.query) queryParams.query = params.query;
  if (params?.from_date) queryParams.from_date = params.from_date;
  if (params?.to_date) queryParams.to_date = params.to_date;
  if (params?.page !== undefined) queryParams.page = params.page;
  if (params?.page_size !== undefined) queryParams.page_size = params.page_size;

  const resp = await apiClient<ApiSuccessEnvelope<PaginatedResult<SaleInvoice>>>("/api/v1/sales/invoices", {
    params: queryParams,
  });
  return resp.data;
}

export async function getSaleInvoice(id: number): Promise<SaleInvoice> {
  const resp = await apiClient<ApiSuccessEnvelope<SaleInvoice>>(`/api/v1/sales/invoices/${id}`);
  return resp.data;
}

export async function printInvoice(id: number, payload: PrintInvoiceRequest): Promise<PrintInvoiceResponse> {
  const resp = await apiClient<ApiSuccessEnvelope<PrintInvoiceResponse>>(`/api/v1/sales/invoices/${id}/print`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return resp.data;
}

export async function holdBill(payload: CreateHeldBillRequest): Promise<HeldBill> {
  const resp = await apiClient<ApiSuccessEnvelope<HeldBill>>("/api/v1/sales/held-bills", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return resp.data;
}

export async function listHeldBills(): Promise<HeldBill[]> {
  const resp = await apiClient<ApiSuccessEnvelope<HeldBill[]>>("/api/v1/sales/held-bills");
  return resp.data;
}

export async function getHeldBill(id: number): Promise<HeldBill> {
  const resp = await apiClient<ApiSuccessEnvelope<HeldBill>>(`/api/v1/sales/held-bills/${id}`);
  return resp.data;
}

export async function deleteHeldBill(id: number): Promise<boolean> {
  const resp = await apiClient<ApiSuccessEnvelope<boolean>>(`/api/v1/sales/held-bills/${id}`, {
    method: "DELETE",
  });
  return resp.data;
}
