/**
 * Medicine, Dosage Forms, Manufacturers, and Catalog Search Contracts.
 */

export const VALID_DOSAGE_FORMS = [
  "TABLET",
  "CAPSULE",
  "SYRUP",
  "INJECTION",
  "OINTMENT",
  "DROPS",
  "POWDER",
  "RESPULES",
  "INHALER",
] as const;

export type DosageForm = (typeof VALID_DOSAGE_FORMS)[number];

export const VALID_GST_RATES = [0, 5, 12, 18, 28] as const;
export type GSTRate = (typeof VALID_GST_RATES)[number];

/**
 * Manufacturer / Pharmaceutical Company.
 */
export interface Manufacturer {
  id: number;
  name: string;
  short_code: string | null;
  is_active: boolean;
  created_at: string;
  updated_at?: string | null;
}

export interface CreateManufacturerInput {
  name: string;
  short_code?: string | null;
}

export interface UpdateManufacturerInput {
  name?: string;
  short_code?: string | null;
  is_active?: boolean;
}

export interface ManufacturerFilterParams {
  query?: string;
  is_active?: boolean;
  page?: number;
  page_size?: number;
}

/**
 * Medicine / Product Master entity.
 */
export interface Medicine {
  id: number;
  medicine_code: string | null; // Unique item code/SKU
  brand_name: string;
  generic_salt: string;
  dosage_form: DosageForm;
  strength: string | null; // e.g. "650mg", "500mg/5ml"
  pack_size: number; // Fundamental units per strip/pack (e.g. 10, 15, 1)
  manufacturer_id: number | null;
  manufacturer_name?: string | null;
  hsn_code: string; // Statutory HSN, defaults to 3004
  gst_rate: GSTRate; // GST rate slab (default 12.0)
  is_schedule_h1: boolean; // 1 = restricted antibiotic/sedative (statutory register required)
  is_schedule_h: boolean; // 1 = prescription required
  is_narcotic: boolean; // Schedule X flag
  min_stock_units: number; // Reorder threshold
  rack_location: string | null; // Shelf coordinate (e.g. "B-04")
  barcode: string | null; // EAN-13 / UPC barcode
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateMedicineInput {
  medicine_code?: string | null;
  brand_name: string;
  generic_salt: string;
  dosage_form: DosageForm;
  strength?: string | null;
  pack_size?: number;
  manufacturer_id?: number | null;
  hsn_code?: string;
  gst_rate?: GSTRate;
  is_schedule_h1?: boolean;
  is_schedule_h?: boolean;
  is_narcotic?: boolean;
  min_stock_units?: number;
  rack_location?: string | null;
  barcode?: string | null;
}

export interface UpdateMedicineInput {
  medicine_code?: string | null;
  brand_name?: string;
  generic_salt?: string;
  dosage_form?: DosageForm;
  strength?: string | null;
  pack_size?: number;
  manufacturer_id?: number | null;
  hsn_code?: string;
  gst_rate?: GSTRate;
  is_schedule_h1?: boolean;
  is_schedule_h?: boolean;
  is_narcotic?: boolean;
  min_stock_units?: number;
  rack_location?: string | null;
  barcode?: string | null;
  is_active?: boolean;
}

export interface MedicineFilterParams {
  query?: string;
  dosage_form?: DosageForm;
  is_schedule_h1?: boolean;
  manufacturer_id?: number;
  is_active?: boolean;
  page?: number;
  page_size?: number;
}

/**
 * High-speed search result for counter billing and inventory browsers.
 * Aggregates real-time batch stock information alongside master attributes.
 */
export interface MedicineSearchResult {
  id: number;
  medicine_code?: string | null;
  brand_name: string;
  generic_salt: string;
  dosage_form: DosageForm;
  strength?: string | null;
  pack_size: number;
  manufacturer_name?: string | null;
  gst_rate: GSTRate;
  is_schedule_h1: boolean;
  is_schedule_h: boolean;
  is_narcotic: boolean;
  rack_location?: string | null;
  barcode?: string | null;
  total_available_stock_units: number;
  earliest_expiry?: string | null; // Normalized YYYY-MM-DD
  min_mrp_paise?: number | null;
  max_mrp_paise?: number | null;
}
