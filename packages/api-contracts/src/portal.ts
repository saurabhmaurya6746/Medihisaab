/**
 * API Contracts and TypeScript interfaces for the Online Pharmacy Portal.
 * Covers public storefront, customer portal, staff management, catalog, and orders.
 */

export type StaffPortalRole = "ADMIN" | "PHARMACIST" | "STAFF";

export interface PortalStaffUser {
  id: string;
  email: string;
  full_name: string;
  role: StaffPortalRole;
  is_active: boolean;
  created_at: string;
}

export interface CustomerProfile {
  id: string;
  email: string;
  full_name: string;
  phone: string;
  delivery_address: string;
  created_at: string;
}

export interface CustomerAuthResponse {
  access_token: string;
  token_type: "bearer";
  customer: CustomerProfile;
}

export interface StaffAuthResponse {
  access_token: string;
  token_type: "bearer";
  staff: PortalStaffUser;
}

export interface ProductCategory {
  id: string;
  name: string;
  slug: string;
  description: string;
  display_order: number;
  is_active: boolean;
  product_count?: number;
}

export type StockStatus = "IN_STOCK" | "LOW_STOCK" | "OUT_OF_STOCK";

export interface CatalogProduct {
  id: string;
  category_id: string;
  category_name?: string;
  category_slug?: string;
  name: string;
  slug: string;
  generic_name: string;
  dosage_form: string; // e.g. "Tablet", "Syrup", "Ointment"
  pack_size: string; // e.g. "10 Tablets", "100 ml"
  mrp_paise: number;
  selling_price_paise: number;
  is_prescription_required: boolean;
  is_available: boolean;
  stock_status: StockStatus;
  image_url: string;
  description: string;
  usage_instructions: string;
  side_effects: string;
  created_at: string;
  updated_at: string;
}

export interface ProductCreateUpdatePayload {
  category_id: string;
  name: string;
  slug?: string;
  generic_name?: string;
  dosage_form?: string;
  pack_size?: string;
  mrp_paise: number;
  selling_price_paise: number;
  is_prescription_required: boolean;
  is_available?: boolean;
  stock_status?: StockStatus;
  image_url?: string;
  description?: string;
  usage_instructions?: string;
  side_effects?: string;
}

export type FulfillmentType = "PICKUP" | "DELIVERY";

export type PaymentMethod = "PAY_AT_PICKUP" | "CASH_ON_DELIVERY" | "UPI_ON_DELIVERY";

export type OnlineOrderStatus =
  | "PENDING_CONFIRMATION"
  | "PHARMACIST_REVIEW"
  | "CONFIRMED"
  | "PREPARING"
  | "READY_FOR_PICKUP"
  | "OUT_FOR_DELIVERY"
  | "DELIVERED"
  | "CANCELLED";

export interface OrderItemDetail {
  id: string;
  product_id: string;
  product_name: string;
  generic_name: string;
  dosage_form: string;
  pack_size: string;
  unit_price_paise: number;
  quantity: number;
  total_paise: number;
  is_prescription_required: boolean;
}

export interface OrderStatusHistoryEntry {
  id: string;
  order_id: string;
  from_status: OnlineOrderStatus | null;
  to_status: OnlineOrderStatus;
  changed_by_type: "CUSTOMER" | "STAFF" | "SYSTEM";
  changed_by_name: string;
  notes: string;
  created_at: string;
}

export interface PortalOrder {
  id: string;
  order_number: string;
  customer_id: string;
  customer_name: string;
  customer_email: string;
  customer_phone: string;
  fulfillment_type: FulfillmentType;
  delivery_address: string;
  payment_method: PaymentMethod;
  status: OnlineOrderStatus;
  subtotal_paise: number;
  delivery_fee_paise: number;
  total_paise: number;
  has_prescription_items: boolean;
  pharmacist_notes: string;
  rejection_reason: string;
  created_at: string;
  updated_at: string;
  items: OrderItemDetail[];
  status_history?: OrderStatusHistoryEntry[];
}

export interface CreateOrderItemInput {
  product_id: string;
  quantity: number;
}

export interface CreateOrderRequest {
  fulfillment_type: FulfillmentType;
  delivery_address?: string;
  payment_method: PaymentMethod;
  customer_phone?: string;
  prescription_acknowledged?: boolean;
  items: CreateOrderItemInput[];
}

export interface UpdateOrderStatusRequest {
  status: OnlineOrderStatus;
  notes?: string;
  rejection_reason?: string;
  pharmacist_notes?: string;
}

export interface PharmacyStoreInfo {
  store_name: string;
  tagline: string;
  license_number: string;
  phone: string;
  email: string;
  address: string;
  operating_hours: string;
  delivery_fee_paise: number;
  free_delivery_threshold_paise: number;
  estimated_delivery_time: string;
  estimated_pickup_time: string;
  rx_policy_notice: string;
}

export type StoreInfoResponse = PharmacyStoreInfo;

export interface StaffDashboardMetrics {
  total_orders: number;
  pending_confirmation_count: number;
  pharmacist_review_count: number;
  ready_orders_count: number;
  delivered_today_count: number;
  total_products_count: number;
  low_stock_count: number;
  total_customers_count: number;
  revenue_today_paise: number;
}

export interface StaffAuditLogEntry {
  id: string;
  staff_user_id: string;
  staff_email: string;
  action: string;
  entity_type: string;
  entity_id: string;
  details_json: string;
  created_at: string;
}

export interface OperationalCustomerLookup {
  id: string;
  email: string;
  full_name: string;
  phone: string;
  delivery_address: string;
  orders_count: number;
  last_order_date: string | null;
  created_at: string;
}
