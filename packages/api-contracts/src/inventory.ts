/**
 * Medicine Batches, Inventory Ledger, Stock Balances, Expiry Dashboard, Stock Audits, and Want-Book Contracts.
 */

export interface MedicineBatch {
  id: number;
  medicine_id: number;
  medicine_name?: string;
  generic_salt?: string;
  dosage_form?: string;
  batch_number: string;
  expiry_date: string;
  mrp_paise: number;
  purchase_rate_paise: number;
  pack_size: number;
  current_quantity: number; // Base units (e.g. tablets, capsules)
  available_packs?: number; // current_quantity / pack_size
  reserved_quantity: number;
  is_active: boolean;
  rack_location?: string | null;
  created_at: string;
  updated_at: string;
}

export type InventoryTransactionType =
  | "PURCHASE_INWARD"
  | "SALE_DISPENSE"
  | "ADJUSTMENT"
  | "PURCHASE_RETURN"
  | "SALE_RETURN";

export interface InventoryLedgerEntry {
  id: number;
  medicine_id: number;
  medicine_name?: string;
  batch_id: number;
  batch_number?: string;
  transaction_type: InventoryTransactionType;
  quantity_change: number; // In base units (+ / -)
  quantity_balance: number; // Resulting balance in base units
  reference_type: string;
  reference_id?: number | null;
  notes?: string | null;
  user_id?: number | null;
  username?: string | null;
  created_at: string;
}

export interface MedicineStockSummary {
  medicine_id: number;
  brand_name: string;
  generic_salt: string;
  dosage_form: string;
  pack_size: number;
  total_stock_units: number;
  total_packs: number;
  earliest_expiry?: string | null;
  active_batches_count: number;
  min_stock_units?: number;
  rack_location?: string | null;
}

export interface SupplierPayableEntry {
  id: number;
  supplier_id: number;
  reference_type: string;
  reference_id?: number | null;
  entry_type: "DEBIT" | "CREDIT";
  amount_paise: number;
  balance_paise: number;
  notes?: string | null;
  created_at: string;
}

export interface SupplierPayableHistoryResponse {
  supplier_id: number;
  supplier_name: string;
  current_payable_paise: number;
  entries: SupplierPayableEntry[];
}

// ==========================================
// MILESTONE 4: EXPIRY & FEFO MANAGEMENT
// ==========================================

export type ExpiryFilterType =
  | "ALL"
  | "EXPIRED"
  | "WITHIN_30_DAYS"
  | "WITHIN_60_DAYS"
  | "WITHIN_90_DAYS"
  | "WITHIN_180_DAYS";

export interface ExpiryBatchItem {
  id: number;
  medicine_id: number;
  medicine_name: string;
  generic_salt: string;
  dosage_form: string;
  batch_number: string;
  expiry_date: string;
  days_to_expiry: number;
  is_expired: boolean;
  pack_size: number;
  current_quantity: number; // base units
  available_packs: number;
  purchase_rate_paise: number;
  mrp_paise: number;
  estimated_stock_value_paise: number;
  rack_location?: string | null;
  supplier_id?: number | null;
  supplier_name?: string | null;
}

export interface ExpiryDashboardSummary {
  expired_count: number;
  expired_value_paise: number;
  within_30_count: number;
  within_30_value_paise: number;
  within_60_count: number;
  within_60_value_paise: number;
  within_90_count: number;
  within_90_value_paise: number;
  within_180_count: number;
  within_180_value_paise: number;
  total_at_risk_value_paise: number;
}

export interface ExpiryDashboardResponse {
  summary: ExpiryDashboardSummary;
  items: ExpiryBatchItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface SupplierReturnDumpGroup {
  supplier_id: number | null;
  supplier_name: string;
  supplier_phone?: string | null;
  supplier_gstin?: string | null;
  total_batches: number;
  total_units: number;
  total_value_paise: number;
  batches: ExpiryBatchItem[];
}

// ==========================================
// MILESTONE 4: PHYSICAL STOCK AUDIT
// ==========================================

export type StockAdjustmentReason =
  | "BREAKAGE"
  | "THEFT"
  | "AUDIT_CORRECTION"
  | "EXPIRED_SCRAP";

export interface StockAdjustmentCreateInput {
  batch_id: number;
  physical_quantity: number; // base units
  reason: StockAdjustmentReason;
  notes?: string | null;
}

export interface StockAdjustmentRecord {
  id: number;
  adjustment_number: string;
  batch_id: number;
  medicine_id: number;
  medicine_name: string;
  generic_salt: string;
  dosage_form: string;
  batch_number: string;
  expiry_date: string;
  pack_size: number;
  system_quantity: number;
  physical_quantity: number;
  delta_quantity: number;
  reason: StockAdjustmentReason;
  estimated_loss_paise: number;
  notes?: string | null;
  user_id?: number | null;
  username?: string | null;
  created_at: string;
}

export interface BatchAuditDetails {
  batch_id: number;
  medicine_id: number;
  medicine_name: string;
  generic_salt: string;
  dosage_form: string;
  batch_number: string;
  expiry_date: string;
  pack_size: number;
  current_quantity: number;
  purchase_rate_paise: number;
  mrp_paise: number;
  rack_location?: string | null;
}

// ==========================================
// MILESTONE 4: WANT-BOOK & REORDER
// ==========================================

export type WantBookStatus = "PENDING" | "ORDERED" | "RECEIVED";

export interface LowStockMedicineItem {
  medicine_id: number;
  brand_name: string;
  generic_salt: string;
  dosage_form: string;
  pack_size: number;
  min_stock_units: number;
  current_stock_units: number;
  current_packs: number;
  suggested_reorder_packs: number;
  rack_location?: string | null;
  preferred_supplier_id?: number | null;
  preferred_supplier_name?: string | null;
}

export interface WantBookCreateInput {
  medicine_id: number;
  requested_quantity_packs: number;
  supplier_id?: number | null;
  notes?: string | null;
}

export interface WantBookStatusUpdateInput {
  status: WantBookStatus;
  notes?: string | null;
}

export interface WantBookItem {
  id: number;
  medicine_id: number;
  medicine_name: string;
  generic_salt: string;
  dosage_form: string;
  pack_size: number;
  requested_quantity_packs: number;
  current_stock_units: number;
  min_stock_units: number;
  status: WantBookStatus;
  supplier_id?: number | null;
  supplier_name?: string | null;
  notes?: string | null;
  requested_by?: number | null;
  requested_by_name?: string | null;
  ordered_at?: string | null;
  received_at?: string | null;
  created_at: string;
  updated_at: string;
}
