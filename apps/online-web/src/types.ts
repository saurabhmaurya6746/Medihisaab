/**
 * TypeScript Data Models for MediHisaab Pharmacy POS Software Website & Portal
 */

export interface SystemRequirements {
  os: string;
  processor: string;
  ram: string;
  disk: string;
  ports: string;
  dependencies: string;
}

export interface SoftwareCapability {
  id: string;
  title: string;
  shortcut?: string;
  summary: string;
  bullets: string[];
  category: "Billing" | "Inventory" | "Statutory" | "Infrastructure";
}

export interface ReleaseNoteItem {
  version: string;
  date: string;
  highlights: string[];
  architecture: string;
}

export interface SetupGuide {
  id: string;
  title: string;
  stepNumber: number;
  description: string;
  instructions: string[];
  commandSnippet?: string;
}

export interface HardwareCompatibility {
  deviceType: string;
  standards: string;
  details: string;
  recommended: string;
}

export interface ClientPlan {
  id: number;
  plan_code: string;
  name: string;
  price: number;
  duration_days: number;
  maximum_terminals: number;
  description: string;
}

export interface DownloadItem {
  id: string;
  title: string;
  filename: string;
  size: string;
  version: string;
  targetPlatform: string;
  url: string;
  isAvailable: boolean;
  sha256?: string;
  isInstaller?: boolean;
}

export interface SupportContacts {
  phone: string;
  whatsapp: string;
  email: string;
}

export interface ClientUser {
  id: number;
  client_code: string;
  business_name: string;
  owner_name: string;
  email: string;
  phone: string;
  status: string;
  created_at?: string;
}

export interface VendorUser {
  id: number;
  full_name: string;
  email: string;
  role: "OWNER" | "ADMIN" | "SUPPORT" | "READ_ONLY";
  is_active: boolean;
  last_login_at?: string;
}

export type AuthRole = "client" | "admin";

export interface AuthState {
  role: AuthRole | null;
  clientUser: ClientUser | null;
  vendorUser: VendorUser | null;
  token: string | null;
  refreshToken: string | null;
  isLoading: boolean;
}

export interface EvaluationSignupPayload {
  email: string;
  password: string;
  pharmacy_name: string;
  contact_person: string;
  phone: string;
}

export interface EvaluationSignupResponse {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  client: ClientUser;
  trial_days: number;
  subscription_status: string;
  license_token?: any;
}

export interface ActiveLicense {
  id: number;
  license_id: string;
  client_id: number;
  edition: string;
  valid_until: string;
  maximum_terminals: number;
  grace_period_days: number;
  version?: number;
  issued_at: string;
  revoked_at?: string | null;
}

export interface SubscriptionInfo {
  id: number;
  status: "TRIAL" | "ACTIVE" | "GRACE" | "EXPIRED" | "SUSPENDED" | "CANCELLED";
  plan_id?: number;
  trial_days?: number;
  current_period_start: string;
  current_period_end: string;
  grace_period_end: string;
}

export interface RenewalRequestItem {
  id: number;
  client_id: number;
  store_name: string;
  contact_name: string;
  email: string;
  phone: string;
  requested_plan_code: string;
  payment_reference?: string;
  payment_amount?: number;
  status: "PENDING" | "APPROVED" | "REJECTED";
  vendor_notified?: boolean;
  notes?: string;
  created_at: string;
}

export interface PaymentRecord {
  id: number;
  amount: number;
  payment_reference: string;
  payment_method: string;
  status: string;
  created_at: string;
}

export interface ClientDashboardData {
  client: ClientUser;
  subscription: SubscriptionInfo | null;
  active_license: ActiveLicense | null;
  license_token?: any;
  days_remaining: number | null;
  grace_period_active: boolean;
  status: string;
  maximum_terminals: number;
  last_refreshed: string;
  can_renew: boolean;
  recent_payments: PaymentRecord[];
}
