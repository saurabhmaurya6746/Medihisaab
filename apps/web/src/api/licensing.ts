/**
 * API client for Central Vendor Licensing & Subscription Portal.
 * Connects over HTTPS to vendor server for trial signups, license tokens, and renewal requests.
 */

const CLIENT_TOKEN_KEY = "medihisaab_client_portal_token";
const CLIENT_REFRESH_TOKEN_KEY = "medihisaab_client_portal_refresh_token";

/**
 * Resolve licensing API base URL with production environment validation.
 */
export function getLicensingApiBase(): string {
  const envUrl = (import.meta as any).env?.VITE_LICENSING_API_URL;
  const isProd = (import.meta as any).env?.PROD;

  if (isProd) {
    if (!envUrl || envUrl.includes("127.0.0.1") || envUrl.includes("localhost")) {
      throw new Error(
        "Production configuration error: VITE_LICENSING_API_URL must be configured with a valid remote licensing server URL in production builds (cannot be empty or point to localhost/127.0.0.1)."
      );
    }
    return envUrl.replace(/\/+$/, "");
  }

  return (envUrl || "http://127.0.0.1:8000").replace(/\/+$/, "");
}

export interface ClientSignupInput {
  business_name: string;
  owner_name: string;
  email: string;
  phone: string;
  password: string;
  drug_license_number?: string;
  gstin?: string;
}

export interface ClientLoginInput {
  email: string;
  password: string;
}

export interface ClientAuthResponse {
  client_id?: number;
  client_code?: string;
  business_name?: string;
  owner_name?: string;
  email?: string;
  phone?: string;
  access_token: string;
  refresh_token?: string;
  token_type: string;
  trial_days?: number;
  subscription_status?: string;
  client?: {
    id: number;
    client_code: string;
    business_name: string;
    owner_name: string;
    email: string;
    phone: string;
  };
  license_token?: Record<string, any> | null;
}

export interface RenewalRequestInput {
  requested_plan_code?: string;
  payment_reference?: string;
  notes?: string;
}

export interface RenewalRequestResult {
  id: number;
  client_id: number;
  store_name: string;
  contact_name: string;
  email: string;
  phone: string;
  requested_plan_code: string;
  payment_reference?: string | null;
  payment_amount?: number | null;
  notes?: string | null;
  status: string; // PENDING, APPROVED, REJECTED
  vendor_notification_sent: boolean;
  vendor_notification_error?: string | null;
  created_at: string;
}

export interface SupportContacts {
  phone: string;
  whatsapp: string;
  email: string;
}

export const DEFAULT_SUPPORT_CONTACTS: SupportContacts = {
  phone: "+91 98765 43210",
  whatsapp: "+91 98765 43210",
  email: "support@apexhealth.local",
};

export function getStoredClientToken(): string | null {
  return localStorage.getItem(CLIENT_TOKEN_KEY);
}

export function setStoredClientToken(token: string): void {
  localStorage.setItem(CLIENT_TOKEN_KEY, token);
}

export function getStoredClientRefreshToken(): string | null {
  return localStorage.getItem(CLIENT_REFRESH_TOKEN_KEY);
}

export function setStoredClientRefreshToken(token: string): void {
  localStorage.setItem(CLIENT_REFRESH_TOKEN_KEY, token);
}

export function clearStoredClientToken(): void {
  localStorage.removeItem(CLIENT_TOKEN_KEY);
  localStorage.removeItem(CLIENT_REFRESH_TOKEN_KEY);
}

/**
 * Perform a request to the Central Licensing Service with ApiEnvelope unwrapping and network fault tolerance.
 */
async function licensingFetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const base = getLicensingApiBase();
  const url = `${base}${endpoint}`;
  try {
    const res = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...(options.headers || {}),
      },
    });

    const body = await res.json().catch(() => null);

    if (!res.ok) {
      const errorMsg =
        (typeof body?.detail === "string" ? body.detail : null) ||
        (Array.isArray(body?.detail) ? body.detail.map((e: any) => e.msg || JSON.stringify(e)).join(", ") : null) ||
        body?.message ||
        `Server returned ${res.status}: ${res.statusText}`;
      throw new Error(errorMsg);
    }

    if (body && typeof body === "object" && "success" in body) {
      if (body.success === false) {
        throw new Error(body.message || body.error || "Licensing operation failed.");
      }
      return (body.data !== undefined ? body.data : body) as T;
    }

    return body as T;
  } catch (err: any) {
    if (err.name === "TypeError" && err.message?.includes("fetch")) {
      throw new Error(
        "Could not connect to central licensing server. Please check your internet connection or try again later."
      );
    }
    throw err;
  }
}

/**
 * Refresh an expired or expiring client portal session token.
 */
export async function refreshClientToken(): Promise<string> {
  const refreshToken = getStoredClientRefreshToken();
  const accessToken = getStoredClientToken();
  if (!refreshToken && !accessToken) {
    throw new Error("No stored session tokens available to refresh.");
  }

  const res = await licensingFetch<{
    access_token: string;
    refresh_token?: string;
    token_type: string;
  }>("/api/v1/client/auth/refresh", {
    method: "POST",
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
    body: JSON.stringify({ refresh_token: refreshToken || undefined }),
  });

  if (res.access_token) {
    setStoredClientToken(res.access_token);
  }
  if (res.refresh_token) {
    setStoredClientRefreshToken(res.refresh_token);
  }
  return res.access_token;
}

/**
 * Register pharmacy owner account and receive initial signed trial license token.
 */
export async function clientSignup(input: ClientSignupInput): Promise<ClientAuthResponse> {
  const data = await licensingFetch<ClientAuthResponse>("/api/v1/client/signup", {
    method: "POST",
    body: JSON.stringify(input),
  });
  if (data.access_token) {
    setStoredClientToken(data.access_token);
  }
  if (data.refresh_token) {
    setStoredClientRefreshToken(data.refresh_token);
  }
  return data;
}

/**
 * Sign in to existing pharmacy client account to retrieve active signed license token.
 */
export async function clientLogin(input: ClientLoginInput): Promise<ClientAuthResponse> {
  const data = await licensingFetch<ClientAuthResponse>("/api/v1/client/login", {
    method: "POST",
    body: JSON.stringify(input),
  });
  if (data.access_token) {
    setStoredClientToken(data.access_token);
  }
  if (data.refresh_token) {
    setStoredClientRefreshToken(data.refresh_token);
  }
  return data;
}

/**
 * Submit in-app license renewal request to vendor.
 */
export async function submitRenewalRequest(
  input: RenewalRequestInput,
  clientToken?: string
): Promise<RenewalRequestResult> {
  const token = clientToken || getStoredClientToken();
  if (!token) {
    throw new Error(
      "No client portal session active. Please sign in with your pharmacy account or contact support directly."
    );
  }

  try {
    return await licensingFetch<RenewalRequestResult>("/api/v1/client/renewal-requests", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(input),
    });
  } catch (err: any) {
    if (
      err.message?.includes("expired") ||
      err.message?.includes("401") ||
      err.message?.includes("credentials")
    ) {
      try {
        const freshToken = await refreshClientToken();
        return await licensingFetch<RenewalRequestResult>("/api/v1/client/renewal-requests", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${freshToken}`,
          },
          body: JSON.stringify(input),
        });
      } catch {
        throw err;
      }
    }
    throw err;
  }
}

/**
 * Fetch vendor customer support contact channels.
 */
export async function fetchSupportContacts(): Promise<SupportContacts> {
  try {
    const data = await licensingFetch<SupportContacts>("/api/v1/client/support-contacts");
    return {
      phone: data.phone || DEFAULT_SUPPORT_CONTACTS.phone,
      whatsapp: data.whatsapp || DEFAULT_SUPPORT_CONTACTS.whatsapp,
      email: data.email || DEFAULT_SUPPORT_CONTACTS.email,
    };
  } catch {
    return DEFAULT_SUPPORT_CONTACTS;
  }
}
