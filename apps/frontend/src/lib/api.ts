/**
 * Centralized API Client for MediHisaab Licensing & Software Management.
 * Communicates with the FastAPI Licensing Service and strictly normalizes ApiEnvelope responses.
 */

export interface ApiEnvelope<T> {
  success: boolean;
  data: T;
  message?: string;
}

export interface ClientProfile {
  id: number;
  client_code: string;
  business_name: string;
  owner_name: string;
  phone: string;
  email: string;
  address?: string;
  city?: string;
  state?: string;
  postal_code?: string;
  gstin?: string | null;
  retail_drug_license?: string | null;
  wholesale_drug_license?: string | null;
  primary_contact_name?: string;
  notes?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface ClientPlan {
  id: number;
  plan_code: string;
  name: string;
  description: string;
  billing_period: string;
  price: number; // in paise
  currency: string;
  maximum_terminals: number;
  enabled_features: string;
  is_active: boolean;
  created_at?: string;
}

export interface SubscriptionInfo {
  id: number;
  client_id: number;
  plan_id: number;
  status: string;
  start_date: string;
  current_period_start: string;
  current_period_end: string;
  grace_period_end: string;
  trial_days?: number | null;
  is_trial?: boolean;
  payment_reference?: string | null;
  notes?: string | null;
  plan?: ClientPlan | null;
}

export interface LicenseInfo {
  id: number;
  client_id: number;
  subscription_id?: number | null;
  license_id: string;
  client_name: string;
  terminal_count: number;
  activation_date: string;
  expiry_date?: string | null;
  edition: string;
  enabled_features: string;
  signature: string;
  issued_at: string;
  revoked_at?: string | null;
}

export interface ClientAuthResponse {
  access_token: string;
  refresh_token?: string | null;
  token_type: string;
  client: ClientProfile;
  business_name?: string;
  owner_name?: string;
  email?: string;
  trial_days?: number;
  subscription_status?: string;
  license_token?: Record<string, unknown> | null;
}

export interface VendorUser {
  id: number;
  full_name: string;
  email: string;
  role: string;
  is_active: boolean;
  last_login_at?: string | null;
}

export interface VendorLoginResponse {
  access_token: string;
  token_type: string;
  expires_in_minutes: number;
  user: VendorUser;
}

export interface ClientDashboardData {
  client: ClientProfile;
  subscription?: SubscriptionInfo | null;
  active_license?: LicenseInfo | null;
  license_token?: Record<string, unknown> | null;
  days_remaining?: number | null;
  grace_period_active: boolean;
  status: string;
  maximum_terminals: number;
  last_refreshed: string;
  can_renew: boolean;
  recent_payments: PaymentInfo[];
}

export interface PaymentInfo {
  id: number;
  client_id: number;
  subscription_id?: number | null;
  plan_id?: number | null;
  amount: number;
  currency: string;
  payment_date: string;
  payment_method: string;
  payment_reference: string;
  status: string;
  notes?: string | null;
  recorded_by_email?: string | null;
  reviewed_by_email?: string | null;
  rejection_reason?: string | null;
  created_at: string;
}

export interface RenewalRequestItem {
  id: number;
  client_id: number;
  subscription_id?: number | null;
  plan_id?: number | null;
  requested_plan_code: string;
  store_name: string;
  contact_name: string;
  email: string;
  phone: string;
  status: string;
  notes?: string | null;
  payment_reference?: string | null;
  payment_amount: number;
  vendor_notification_sent: boolean;
  vendor_notification_error?: string | null;
  reviewed_by_email?: string | null;
  reviewed_at?: string | null;
  rejection_reason?: string | null;
  created_at: string;
  client?: ClientProfile | null;
}

export interface DownloadItem {
  id: string;
  title: string;
  filename: string;
  file_size: string;
  os: string;
  download_url: string;
  sha256: string;
  is_installer: boolean;
  description: string;
}

export interface SupportContacts {
  phone: string;
  whatsapp: string;
  email: string;
  vendor_notification_email?: string | null;
}

export interface DashboardStats {
  total_clients: number;
  active_subscriptions: number;
  trial_clients: number;
  expiring_soon_subscriptions: number;
  expired_subscriptions: number;
  suspended_clients: number;
  total_licenses_issued: number;
  recent_licenses: LicenseInfo[];
}

export interface AuditEventItem {
  id: number;
  user_email: string;
  action: string;
  entity_type: string;
  entity_id?: string | null;
  timestamp: string;
  ip_address?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface SystemSettingItem {
  id: number;
  key: string;
  value: string;
  description?: string | null;
  updated_at: string;
}

export interface SystemSettingsData {
  settings: SystemSettingItem[];
  default_trial_days: number;
  default_grace_days: number;
  support_contacts: SupportContacts;
}

export class ApiError extends Error {
  status: number;
  detail?: string | undefined;
  isNetworkError?: boolean | undefined;
  isValidationError?: boolean | undefined;
  validationErrors?: string[] | undefined;

  constructor(
    message: string,
    status: number,
    detail?: string | undefined,
    isNetworkError?: boolean | undefined,
    isValidationError?: boolean | undefined,
    validationErrors?: string[] | undefined
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.isNetworkError = isNetworkError ?? (status === 0);
    this.isValidationError = isValidationError ?? (status === 400 || status === 422);
    this.validationErrors = validationErrors;
  }
}

export function normalizeApiBaseUrl(rawUrl?: string | null): string {
  if (!rawUrl || !rawUrl.trim()) {
    return "/api/v1";
  }
  const trimmed = rawUrl.trim().replace(/\/+$/, "");
  return trimmed.endsWith("/api/v1") ? trimmed : `${trimmed}/api/v1`;
}

export function getApiBaseUrl(): string {
  const envUrl = (import.meta.env as Record<string, string | undefined>)["VITE_LICENSING_API_URL"];
  return normalizeApiBaseUrl(envUrl);
}

class ApiClient {
  private get baseUrl(): string {
    return getApiBaseUrl();
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    token?: string | null
  ): Promise<T> {
    const url = endpoint.startsWith("http")
      ? endpoint
      : `${this.baseUrl}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;

    const headers: Record<string, string> = {
      Accept: "application/json",
      ...(options.headers as Record<string, string>),
    };

    if (!(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    let response: Response;
    try {
      response = await fetch(url, { ...options, headers });
    } catch {
      const isOffline = typeof navigator !== "undefined" && !navigator.onLine;
      const msg = isOffline
        ? "You appear to be offline. Please check your internet connection."
        : "Unable to connect to the MediHisaab licensing server. The server may be unreachable or the request was blocked by network/CORS policy.";
      throw new ApiError(msg, 0, undefined, true);
    }

    // Handle file downloads (e.g., json or blob)
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/octet-stream") || contentType.includes("application/vnd.microsoft.portable-executable")) {
      if (!response.ok) {
        throw new ApiError(`Download failed with status ${response.status}`, response.status);
      }
      return (await response.blob()) as unknown as T;
    }

    let bodyText = "";
    try {
      bodyText = await response.text();
    } catch {
      bodyText = "";
    }

    let json: any = null;
    if (bodyText) {
      try {
        json = JSON.parse(bodyText);
      } catch {
        json = null;
      }
    }

    if (!response.ok) {
      let errorMsg = `Request failed with HTTP status ${response.status}`;
      let detailString: string | undefined = undefined;
      const validationList: string[] = [];

      if (json && typeof json === "object") {
        if (typeof json.detail === "string") {
          errorMsg = json.detail;
          detailString = json.detail;
        } else if (Array.isArray(json.detail)) {
          // Format FastAPI 422 validation error array into readable messages
          for (const item of json.detail) {
            if (typeof item === "string") {
              validationList.push(item);
            } else if (item && typeof item === "object") {
              const field = Array.isArray(item.loc)
                ? item.loc.filter((part: unknown) => part !== "body").join(".")
                : "";
              const msg = item.msg || "Invalid input";
              validationList.push(field ? `${field}: ${msg}` : msg);
            }
          }
          if (validationList.length > 0) {
            errorMsg = validationList.join(" | ");
            detailString = errorMsg;
          }
        } else if (typeof json.message === "string") {
          errorMsg = json.message;
          detailString = json.message;
        }
      }

      const isValidation = response.status === 400 || response.status === 422;
      throw new ApiError(
        errorMsg,
        response.status,
        detailString,
        false,
        isValidation,
        validationList.length > 0 ? validationList : undefined
      );
    }

    if (json && typeof json === "object" && "data" in json) {
      return json.data as T;
    }

    return (json ?? ({} as unknown)) as T;
  }

  // ==========================================
  // Client Authentication & Account
  // ==========================================

  async clientLogin(credentials: { email: string; password: string }): Promise<ClientAuthResponse> {
    return this.request<ClientAuthResponse>("/client/auth/login", {
      method: "POST",
      body: JSON.stringify(credentials),
    });
  }

  async clientSignup(data: {
    email: string;
    password: string;
    pharmacy_name: string;
    contact_person: string;
    phone: string;
  }): Promise<ClientAuthResponse> {
    return this.request<ClientAuthResponse>("/client/auth/signup", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async clientRefreshToken(refreshToken?: string, token?: string): Promise<{
    access_token: string;
    refresh_token: string;
    token_type: string;
    client_id: number;
    business_name: string;
    owner_name: string;
    email: string;
  }> {
    return this.request("/client/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    }, token);
  }

  async clientGetMe(token: string): Promise<ClientProfile> {
    return this.request<ClientProfile>("/client/me", { method: "GET" }, token);
  }

  async clientGetDashboard(token: string): Promise<ClientDashboardData> {
    return this.request<ClientDashboardData>("/client/dashboard", { method: "GET" }, token);
  }

  async clientDownloadLicense(token: string): Promise<Record<string, unknown>> {
    const url = `${this.baseUrl}/client/license/download`;
    const response = await fetch(url, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
    });
    if (!response.ok) {
      throw new ApiError("Failed to download license file", response.status);
    }
    return response.json();
  }

  async clientGetPlans(): Promise<ClientPlan[]> {
    return this.request<ClientPlan[]>("/client/plans", { method: "GET" });
  }

  async clientGetDownloads(token: string): Promise<DownloadItem[]> {
    return this.request<DownloadItem[]>("/client/downloads", { method: "GET" }, token);
  }

  async clientRecordDownloadRequest(
    itemId: string,
    token: string
  ): Promise<{ download_url: string; filename: string; sha256: string; version: string }> {
    return this.request(`/client/downloads/${itemId}/request`, {
      method: "POST",
    }, token);
  }

  async clientSubmitRenewal(
    data: {
      requested_plan_code: string;
      payment_reference?: string | undefined;
      payment_amount?: number | undefined;
      notes?: string | undefined;
    },
    token: string
  ): Promise<RenewalRequestItem> {
    return this.request<RenewalRequestItem>("/client/renewal-requests", {
      method: "POST",
      body: JSON.stringify(data),
    }, token);
  }

  async clientGetRenewalRequests(token: string): Promise<RenewalRequestItem[]> {
    return this.request<RenewalRequestItem[]>("/client/renewal-requests", { method: "GET" }, token);
  }

  async clientGetSupportContacts(): Promise<SupportContacts> {
    return this.request<SupportContacts>("/client/support-contacts", { method: "GET" });
  }

  // ==========================================
  // Vendor Admin Authentication & Console
  // ==========================================

  async vendorLogin(credentials: { email: string; password: string }): Promise<VendorLoginResponse> {
    return this.request<VendorLoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(credentials),
    });
  }

  async vendorGetMe(token: string): Promise<VendorUser> {
    return this.request<VendorUser>("/auth/me", { method: "GET" }, token);
  }

  async vendorGetStats(token: string): Promise<DashboardStats> {
    return this.request<DashboardStats>("/dashboard/stats", { method: "GET" }, token);
  }

  async vendorGetClients(
    params: { q?: string; status?: string; limit?: number; offset?: number } = {},
    token: string
  ): Promise<ClientProfile[]> {
    const qp = new URLSearchParams();
    if (params.q) qp.set("q", params.q);
    if (params.status) qp.set("status", params.status);
    if (params.limit) qp.set("limit", String(params.limit));
    if (params.offset) qp.set("offset", String(params.offset));
    const qs = qp.toString() ? `?${qp.toString()}` : "";
    return this.request<ClientProfile[]>(`/clients${qs}`, { method: "GET" }, token);
  }

  async vendorGetClientDetail(clientId: number, token: string): Promise<{
    client: ClientProfile;
    subscriptions: SubscriptionInfo[];
    licenses: LicenseInfo[];
  }> {
    return this.request(`/clients/${clientId}`, { method: "GET" }, token);
  }

  async vendorUpdateClient(
    clientId: number,
    data: Partial<ClientProfile>,
    token: string
  ): Promise<ClientProfile> {
    return this.request<ClientProfile>(`/clients/${clientId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }, token);
  }

  async vendorChangeClientStatus(
    clientId: number,
    newStatus: string,
    reason: string | undefined,
    token: string
  ): Promise<ClientProfile> {
    return this.request<ClientProfile>(`/clients/${clientId}/status`, {
      method: "POST",
      body: JSON.stringify({ status: newStatus, reason }),
    }, token);
  }

  async vendorGetSubscriptions(
    params: { client_id?: number; status?: string } = {},
    token: string
  ): Promise<SubscriptionInfo[]> {
    const qp = new URLSearchParams();
    if (params.client_id) qp.set("client_id", String(params.client_id));
    if (params.status) qp.set("status", params.status);
    const qs = qp.toString() ? `?${qp.toString()}` : "";
    return this.request<SubscriptionInfo[]>(`/subscriptions${qs}`, { method: "GET" }, token);
  }

  async vendorStartTrial(
    data: { client_id: number; trial_days?: number; grace_days?: number; notes?: string },
    token: string
  ): Promise<SubscriptionInfo> {
    return this.request<SubscriptionInfo>("/subscriptions/trial", {
      method: "POST",
      body: JSON.stringify(data),
    }, token);
  }

  async vendorCreatePaidSubscription(
    data: {
      client_id: number;
      plan_code?: string;
      plan_id?: number;
      payment_reference?: string;
      amount?: number;
      payment_method?: string;
      notes?: string;
    },
    token: string
  ): Promise<SubscriptionInfo> {
    return this.request<SubscriptionInfo>("/subscriptions/paid", {
      method: "POST",
      body: JSON.stringify(data),
    }, token);
  }

  async vendorConvertTrialToPaid(
    subId: number,
    data: { plan_id: number; payment_reference?: string; amount?: number; notes?: string },
    token: string
  ): Promise<SubscriptionInfo> {
    return this.request<SubscriptionInfo>(`/subscriptions/${subId}/convert-to-paid`, {
      method: "POST",
      body: JSON.stringify(data),
    }, token);
  }

  async vendorRenewSubscription(
    subId: number,
    data: { payment_reference?: string; amount?: number; notes?: string; new_expiry_date?: string },
    token: string
  ): Promise<SubscriptionInfo> {
    return this.request<SubscriptionInfo>(`/subscriptions/${subId}/renew`, {
      method: "POST",
      body: JSON.stringify(data),
    }, token);
  }

  async vendorCancelSubscription(subId: number, reason: string, token: string): Promise<SubscriptionInfo> {
    return this.request<SubscriptionInfo>(`/subscriptions/${subId}/cancel`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }, token);
  }

  async vendorSuspendSubscription(subId: number, reason: string, token: string): Promise<SubscriptionInfo> {
    return this.request<SubscriptionInfo>(`/subscriptions/${subId}/suspend`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }, token);
  }

  async vendorGetLicenses(
    params: { client_id?: number; revoked?: boolean; limit?: number; offset?: number } = {},
    token: string
  ): Promise<LicenseInfo[]> {
    const qp = new URLSearchParams();
    if (params.client_id) qp.set("client_id", String(params.client_id));
    if (params.revoked !== undefined) qp.set("revoked", String(params.revoked));
    if (params.limit) qp.set("limit", String(params.limit));
    if (params.offset) qp.set("offset", String(params.offset));
    const qs = qp.toString() ? `?${qp.toString()}` : "";
    return this.request<LicenseInfo[]>(`/licenses${qs}`, { method: "GET" }, token);
  }

  async vendorGenerateLicense(
    data: {
      client_id?: number;
      subscription_id?: number;
      terminal_count?: number;
      activation_date?: string;
      expiry_date?: string;
      edition?: string;
      enabled_features?: string;
    },
    token: string
  ): Promise<LicenseInfo> {
    return this.request<LicenseInfo>("/licenses/generate", {
      method: "POST",
      body: JSON.stringify(data),
    }, token);
  }

  async vendorRevokeLicense(licenseId: string, reason: string, token: string): Promise<LicenseInfo> {
    const qp = new URLSearchParams({ reason });
    return this.request<LicenseInfo>(`/licenses/${licenseId}/revoke?${qp.toString()}`, {
      method: "POST",
    }, token);
  }

  async vendorDownloadLicenseFile(licenseId: string, token: string): Promise<Record<string, unknown>> {
    const url = `${this.baseUrl}/licenses/${licenseId}/download`;
    const response = await fetch(url, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
    });
    if (!response.ok) {
      throw new ApiError("Failed to download license file", response.status);
    }
    return response.json();
  }

  async vendorGetRenewalRequests(
    params: { status?: string; limit?: number; offset?: number } = {},
    token: string
  ): Promise<RenewalRequestItem[]> {
    const qp = new URLSearchParams();
    if (params.status) qp.set("status", params.status);
    if (params.limit) qp.set("limit", String(params.limit));
    if (params.offset) qp.set("offset", String(params.offset));
    const qs = qp.toString() ? `?${qp.toString()}` : "";
    return this.request<RenewalRequestItem[]>(`/renewal-requests${qs}`, { method: "GET" }, token);
  }

  async vendorApproveRenewal(
    requestId: number,
    data: { plan_id?: number | undefined; payment_reference?: string | undefined; amount?: number | undefined; notes?: string | undefined },
    token: string
  ): Promise<{ renewal_request: RenewalRequestItem; license: Record<string, unknown>; new_expiry_date: string }> {
    return this.request(`/renewal-requests/${requestId}/approve`, {
      method: "POST",
      body: JSON.stringify(data),
    }, token);
  }

  async vendorRejectRenewal(requestId: number, reason: string, token: string): Promise<RenewalRequestItem> {
    return this.request<RenewalRequestItem>(`/renewal-requests/${requestId}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }, token);
  }

  async vendorGetSettings(token: string): Promise<SystemSettingsData> {
    return this.request<SystemSettingsData>("/settings", { method: "GET" }, token);
  }

  async vendorUpdateTrialSettings(
    data: { default_trial_days: number; default_grace_days?: number | undefined },
    token: string
  ): Promise<{ default_trial_days: number; default_grace_days?: number }> {
    return this.request("/settings/trial-duration", {
      method: "PUT",
      body: JSON.stringify(data),
    }, token);
  }

  async vendorUpdateSupportContacts(data: Partial<SupportContacts>, token: string): Promise<SupportContacts> {
    return this.request<SupportContacts>("/settings/support-contacts", {
      method: "PUT",
      body: JSON.stringify(data),
    }, token);
  }

  async vendorGetAuditEvents(
    params: { entity_type?: string; action?: string; limit?: number; offset?: number } = {},
    token: string
  ): Promise<AuditEventItem[]> {
    const qp = new URLSearchParams();
    if (params.entity_type) qp.set("entity_type", params.entity_type);
    if (params.action) qp.set("action", params.action);
    if (params.limit) qp.set("limit", String(params.limit));
    if (params.offset) qp.set("offset", String(params.offset));
    const qs = qp.toString() ? `?${qp.toString()}` : "";
    return this.request<AuditEventItem[]>(`/audit${qs}`, { method: "GET" }, token);
  }
}

export const api = new ApiClient();
