/**
 * Master Catalog API service functions for Medicines, Manufacturers, Suppliers, and Customers.
 */

import type {
  Medicine,
  CreateMedicineInput,
  UpdateMedicineInput,
  Manufacturer,
  CreateManufacturerInput,
  UpdateManufacturerInput,
  Supplier,
  CreateSupplierInput,
  UpdateSupplierInput,
  Customer,
  CreateCustomerInput,
  UpdateCustomerInput,
  PaginatedResult,
  ApiSuccessEnvelope,
} from "@pharmacy/api-contracts";
import { apiClient } from "./client";

// ==========================================
// 1. MEDICINES API
// ==========================================

export interface MedicineQueryParams {
  query?: string;
  dosage_form?: string;
  is_schedule_h1?: boolean;
  is_active?: boolean;
  manufacturer_id?: number;
  page?: number;
  page_size?: number;
}

export async function listMedicines(
  params?: MedicineQueryParams
): Promise<PaginatedResult<Medicine>> {
  const queryParams: Record<string, string | number | boolean | undefined> = {};
  if (params?.query) queryParams.query = params.query;
  if (params?.dosage_form) queryParams.dosage_form = params.dosage_form;
  if (params?.is_schedule_h1 !== undefined) queryParams.is_schedule_h1 = params.is_schedule_h1;
  if (params?.is_active !== undefined) queryParams.is_active = params.is_active;
  if (params?.manufacturer_id !== undefined) queryParams.manufacturer_id = params.manufacturer_id;
  if (params?.page !== undefined) queryParams.page = params.page;
  if (params?.page_size !== undefined) queryParams.page_size = params.page_size;

  const resp = await apiClient<ApiSuccessEnvelope<PaginatedResult<Medicine>>>("/api/v1/masters/medicines", {
    params: queryParams,
  });
  return resp.data;
}

export async function getMedicine(id: number): Promise<Medicine> {
  const resp = await apiClient<ApiSuccessEnvelope<Medicine>>(`/api/v1/masters/medicines/${id}`);
  return resp.data;
}

export async function createMedicine(payload: CreateMedicineInput): Promise<Medicine> {
  const resp = await apiClient<ApiSuccessEnvelope<Medicine>>("/api/v1/masters/medicines", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return resp.data;
}

export async function updateMedicine(id: number, payload: UpdateMedicineInput): Promise<Medicine> {
  const resp = await apiClient<ApiSuccessEnvelope<Medicine>>(`/api/v1/masters/medicines/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  return resp.data;
}

export async function deactivateMedicine(id: number): Promise<Medicine> {
  const resp = await apiClient<ApiSuccessEnvelope<Medicine>>(`/api/v1/masters/medicines/${id}`, {
    method: "DELETE",
  });
  return resp.data;
}

// ==========================================
// 2. MANUFACTURERS API
// ==========================================

export interface ManufacturerQueryParams {
  query?: string;
  is_active?: boolean;
  page?: number;
  page_size?: number;
}

export async function listManufacturers(
  params?: ManufacturerQueryParams
): Promise<PaginatedResult<Manufacturer>> {
  const queryParams: Record<string, string | number | boolean | undefined> = {};
  if (params?.query) queryParams.query = params.query;
  if (params?.is_active !== undefined) queryParams.is_active = params.is_active;
  if (params?.page !== undefined) queryParams.page = params.page;
  if (params?.page_size !== undefined) queryParams.page_size = params.page_size;

  const resp = await apiClient<ApiSuccessEnvelope<PaginatedResult<Manufacturer>>>("/api/v1/masters/manufacturers", {
    params: queryParams,
  });
  return resp.data;
}

export async function createManufacturer(payload: CreateManufacturerInput): Promise<Manufacturer> {
  const resp = await apiClient<ApiSuccessEnvelope<Manufacturer>>("/api/v1/masters/manufacturers", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return resp.data;
}

export async function updateManufacturer(id: number, payload: UpdateManufacturerInput): Promise<Manufacturer> {
  const resp = await apiClient<ApiSuccessEnvelope<Manufacturer>>(`/api/v1/masters/manufacturers/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  return resp.data;
}

export async function deactivateManufacturer(id: number): Promise<Manufacturer> {
  const resp = await apiClient<ApiSuccessEnvelope<Manufacturer>>(`/api/v1/masters/manufacturers/${id}`, {
    method: "DELETE",
  });
  return resp.data;
}

// ==========================================
// 3. SUPPLIERS API
// ==========================================

export interface SupplierQueryParams {
  query?: string;
  is_active?: boolean;
  page?: number;
  page_size?: number;
}

export async function listSuppliers(
  params?: SupplierQueryParams
): Promise<PaginatedResult<Supplier>> {
  const queryParams: Record<string, string | number | boolean | undefined> = {};
  if (params?.query) queryParams.query = params.query;
  if (params?.is_active !== undefined) queryParams.is_active = params.is_active;
  if (params?.page !== undefined) queryParams.page = params.page;
  if (params?.page_size !== undefined) queryParams.page_size = params.page_size;

  const resp = await apiClient<ApiSuccessEnvelope<PaginatedResult<Supplier>>>("/api/v1/masters/suppliers", {
    params: queryParams,
  });
  return resp.data;
}

export async function getSupplier(id: number): Promise<Supplier> {
  const resp = await apiClient<ApiSuccessEnvelope<Supplier>>(`/api/v1/masters/suppliers/${id}`);
  return resp.data;
}

export async function createSupplier(payload: CreateSupplierInput): Promise<Supplier> {
  const resp = await apiClient<ApiSuccessEnvelope<Supplier>>("/api/v1/masters/suppliers", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return resp.data;
}

export async function updateSupplier(id: number, payload: UpdateSupplierInput): Promise<Supplier> {
  const resp = await apiClient<ApiSuccessEnvelope<Supplier>>(`/api/v1/masters/suppliers/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  return resp.data;
}

export async function deactivateSupplier(id: number): Promise<Supplier> {
  const resp = await apiClient<ApiSuccessEnvelope<Supplier>>(`/api/v1/masters/suppliers/${id}`, {
    method: "DELETE",
  });
  return resp.data;
}

// ==========================================
// 4. CUSTOMERS API
// ==========================================

export interface CustomerQueryParams {
  query?: string;
  is_active?: boolean;
  page?: number;
  page_size?: number;
}

export async function listCustomers(
  params?: CustomerQueryParams
): Promise<PaginatedResult<Customer>> {
  const queryParams: Record<string, string | number | boolean | undefined> = {};
  if (params?.query) queryParams.query = params.query;
  if (params?.is_active !== undefined) queryParams.is_active = params.is_active;
  if (params?.page !== undefined) queryParams.page = params.page;
  if (params?.page_size !== undefined) queryParams.page_size = params.page_size;

  const resp = await apiClient<ApiSuccessEnvelope<PaginatedResult<Customer>>>("/api/v1/masters/customers", {
    params: queryParams,
  });
  return resp.data;
}

export async function getCustomer(id: number): Promise<Customer> {
  const resp = await apiClient<ApiSuccessEnvelope<Customer>>(`/api/v1/masters/customers/${id}`);
  return resp.data;
}

export async function createCustomer(payload: CreateCustomerInput): Promise<Customer> {
  const resp = await apiClient<ApiSuccessEnvelope<Customer>>("/api/v1/masters/customers", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return resp.data;
}

export async function updateCustomer(id: number, payload: UpdateCustomerInput): Promise<Customer> {
  const resp = await apiClient<ApiSuccessEnvelope<Customer>>(`/api/v1/masters/customers/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  return resp.data;
}

export async function deactivateCustomer(id: number): Promise<Customer> {
  const resp = await apiClient<ApiSuccessEnvelope<Customer>>(`/api/v1/masters/customers/${id}`, {
    method: "DELETE",
  });
  return resp.data;
}
