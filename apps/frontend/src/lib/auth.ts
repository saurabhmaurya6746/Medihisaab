import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";

/**
 * THREAT MODEL & STORAGE ARCHITECTURE:
 *
 * 1. Passwords & Secrets:
 *    - Raw passwords and password hashes are NEVER stored in browser storage (localStorage,
 *      sessionStorage, cookies, or history).
 *    - Passwords are submitted solely over encrypted HTTPS POST bodies directly to the
 *      licensing backend endpoints (/client/auth/login or /auth/login).
 *    - Vendor private Ed25519 signing keys reside exclusively on the server and are never
 *      transmitted to or cached in the browser.
 *
 * 2. Tokens & Sessions:
 *    - Ephemeral JWT access tokens are stored in browser localStorage strictly for session
 *      continuity across page reloads and deep navigation in the portal.
 *    - A refresh token is stored alongside for proactive session extension (/client/auth/refresh).
 *    - Access tokens are cryptographically signed with HMAC-SHA256 and subject to strict server-side
 *      expiration (60 minutes).
 *
 * 3. Role Derivation & Authorization:
 *    - User roles ('client' vs 'admin') are determined exclusively by the authenticated server
 *      response. The client never dictates its own authorization privileges.
 *    - All sensitive backend operations (license generation, renewal approvals, client status
 *      changes) require server-side RBAC validation.
 *
 * 4. Pharmacy Isolation:
 *    - Store POS transactional data (bills, inventory, customer medical histories, khata ledgers)
 *      belongs exclusively on the local pharmacy workstation. The licensing API neither receives
 *      nor stores sensitive pharmacy patient or sales information.
 *    - An expired web licensing token never inhibits local offline pharmacy counter billing.
 */

export type Role = "client" | "admin";

export interface Session {
  email: string;
  role: Role;
  pharmacyName: string;
  ownerName: string;
  clientCode?: string;
  vendorRole?: string;
  displayName?: string;
}

const STORAGE_SESSION = "medihisaab_session";
const STORAGE_TOKEN = "medihisaab_token";
const STORAGE_REFRESH_TOKEN = "medihisaab_refresh_token";

export function getSession(): Session | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(STORAGE_SESSION);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(STORAGE_TOKEN);
  } catch {
    return null;
  }
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(STORAGE_REFRESH_TOKEN);
  } catch {
    return null;
  }
}

function persistSession(session: Session | null, token: string | null = null, refreshToken: string | null = null) {
  if (session && token) {
    localStorage.setItem(STORAGE_SESSION, JSON.stringify(session));
    localStorage.setItem(STORAGE_TOKEN, token);
    if (refreshToken) {
      localStorage.setItem(STORAGE_REFRESH_TOKEN, refreshToken);
    } else {
      localStorage.removeItem(STORAGE_REFRESH_TOKEN);
    }
  } else {
    localStorage.removeItem(STORAGE_SESSION);
    localStorage.removeItem(STORAGE_TOKEN);
    localStorage.removeItem(STORAGE_REFRESH_TOKEN);
  }
  window.dispatchEvent(new Event("medihisaab-session"));
}

/**
 * Unified sign-in for Pharmacy Clients and Vendor Administrators.
 * Authenticates against the appropriate server-side account system and
 * strictly resolves the role from the verified response.
 */
export async function signIn(email: string, password: string): Promise<Session> {
  const cleanEmail = email.trim().toLowerCase();

  // 1. First attempt Pharmacy Client Authentication
  try {
    const clientRes = await api.clientLogin({ email: cleanEmail, password });
    if (clientRes && clientRes.access_token) {
      const session: Session = {
        email: clientRes.email || clientRes.client.email || cleanEmail,
        role: "client",
        pharmacyName: clientRes.business_name || clientRes.client.business_name || "Retail Pharmacy",
        ownerName: clientRes.owner_name || clientRes.client.owner_name || "Store Owner",
        clientCode: clientRes.client.client_code,
      };
      persistSession(session, clientRes.access_token, clientRes.refresh_token || null);
      return session;
    }
  } catch (err) {
    // If client account is suspended/closed (403), surface the exact server error
    if (err instanceof ApiError && err.status === 403) {
      throw new Error(err.message || "Your client account is suspended. Please contact support.");
    }
    // Network / connectivity error: pass through
    if (err instanceof ApiError && err.status === 0) {
      throw err;
    }
  }

  // 2. If client login returned 401 or 404, attempt Vendor Admin Authentication
  try {
    const vendorRes = await api.vendorLogin({ email: cleanEmail, password });
    if (vendorRes && vendorRes.access_token) {
      const session: Session = {
        email: vendorRes.user.email,
        role: "admin",
        pharmacyName: "MediHisaab Administration",
        ownerName: vendorRes.user.full_name,
        vendorRole: vendorRes.user.role,
        displayName: vendorRes.user.full_name,
      };
      persistSession(session, vendorRes.access_token, null);
      return session;
    }
  } catch (adminErr) {
    // If vendor account is deactivated (403), surface the message
    if (adminErr instanceof ApiError && adminErr.status === 403) {
      throw new Error(adminErr.message || "Account is deactivated. Contact the system owner.");
    }
    // Network / connectivity error: pass through
    if (adminErr instanceof ApiError && adminErr.status === 0) {
      throw adminErr;
    }
  }

  // 3. Both failed: provide generic failed-login message so the form never reveals
  // whether an email address exists in the system.
  throw new Error("Invalid email or password. Please verify your credentials and try again.");
}

/**
 * Register a new pharmacy account and immediately activate a server-configured evaluation trial.
 */
export async function createAccount(input: {
  pharmacyName: string;
  ownerName: string;
  email: string;
  phone: string;
  password: string;
}): Promise<Session> {
  const cleanEmail = input.email.trim().toLowerCase();

  try {
    const res = await api.clientSignup({
      email: cleanEmail,
      password: input.password,
      pharmacy_name: input.pharmacyName.trim(),
      contact_person: input.ownerName.trim(),
      phone: input.phone.trim(),
    });

    const session: Session = {
      email: res.email || res.client.email || cleanEmail,
      role: "client",
      pharmacyName: res.business_name || res.client.business_name || input.pharmacyName.trim(),
      ownerName: res.owner_name || res.client.owner_name || input.ownerName.trim(),
      clientCode: res.client.client_code,
    };

    persistSession(session, res.access_token, res.refresh_token || null);
    return session;
  } catch (err) {
    if (err instanceof ApiError) {
      throw new Error(err.message || "Failed to create account. Please check your information.");
    }
    throw err;
  }
}

/**
 * Attempt to refresh an expired client access token using the stored refresh token.
 */
export async function refreshClientSession(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  const currentToken = getToken();
  if (!refreshToken && !currentToken) return false;

  try {
    const res = await api.clientRefreshToken(refreshToken || undefined, currentToken || undefined);
    const existing = getSession();
    if (existing && res.access_token) {
      persistSession(existing, res.access_token, res.refresh_token || refreshToken);
      return true;
    }
  } catch {
    // If token refresh fails, clear session to prevent stale state
    signOut();
  }
  return false;
}

export function signOut() {
  persistSession(null, null, null);
}

/** Only allow internal, same-origin paths for `next`. */
export function safeNext(next: unknown): string | null {
  if (typeof next !== "string") return null;
  if (!next.startsWith("/") || next.startsWith("//") || next.includes("\\")) return null;
  return next;
}

export function useSession() {
  const [state, setState] = useState<{
    ready: boolean;
    session: Session | null;
    token: string | null;
  }>({
    ready: false,
    session: null,
    token: null,
  });

  useEffect(() => {
    const sync = () => {
      setState({
        ready: true,
        session: getSession(),
        token: getToken(),
      });
    };
    sync();
    window.addEventListener("medihisaab-session", sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener("medihisaab-session", sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  return state;
}
