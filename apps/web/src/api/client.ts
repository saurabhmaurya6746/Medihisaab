/**
 * Base HTTP API client for communicating with the local Pharmacy POS Daemon.
 *
 * Adheres strictly to security rules:
 * - Session token is read exclusively from sessionStorage.
 * - Passwords, PINs, and sensitive credentials are never stored.
 */

export class ApiError extends Error {
  public readonly status: number;
  public readonly code?: string;
  public readonly details?: Record<string, unknown> | null;

  constructor(status: number, message: string, code?: string, details?: Record<string, unknown> | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

const TOKEN_STORAGE_KEY = "pharmacy_token";

export function getStoredToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setStoredToken(token: string): void {
  try {
    sessionStorage.setItem(TOKEN_STORAGE_KEY, token);
  } catch (err) {
    console.error("Failed to store token in sessionStorage", err);
  }
}

export function clearStoredToken(): void {
  try {
    sessionStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch (err) {
    console.error("Failed to clear token from sessionStorage", err);
  }
}

// In local dev with Vite proxy, base URL is empty string (relative).
// When built or customized, import.meta.env.VITE_API_BASE_URL can override.
const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || "";

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
}

export async function apiClient<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  let url = `${BASE_URL}${endpoint}`;

  if (options.params) {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(options.params)) {
      if (value !== undefined && value !== null && value !== "") {
        query.append(key, String(value));
      }
    }
    const queryString = query.toString();
    if (queryString) {
      url += (url.includes("?") ? "&" : "?") + queryString;
    }
  }

  const headers: Record<string, string> = {
    "Accept": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const token = getStoredToken();
  if (token && !headers["Authorization"]) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "Network error";
    throw new ApiError(0, `Cannot connect to local pharmacy daemon: ${msg}. Make sure the daemon is running on 127.0.0.1:38291.`, "DAEMON_UNREACHABLE");
  }

  if (response.status === 401) {
    // If we were unauthorized, clear stored token and broadcast event
    clearStoredToken();
    window.dispatchEvent(new CustomEvent("pos:unauthorized"));
  }

  let data: any = null;
  const contentType = response.headers.get("content-type");
  if (contentType && contentType.includes("application/json")) {
    try {
      data = await response.json();
    } catch {
      data = null;
    }
  } else {
    try {
      data = await response.text();
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    let errorMessage = `HTTP Error ${response.status}: ${response.statusText}`;
    let errorCode = `HTTP_${response.status}`;
    let errorDetails: Record<string, unknown> | null = null;

    if (data && typeof data === "object") {
      if (data.error && typeof data.error === "object") {
        errorMessage = data.error.message || errorMessage;
        errorCode = data.error.code || errorCode;
        errorDetails = data.error.details || null;
      } else if (data.detail) {
        if (typeof data.detail === "string") {
          errorMessage = data.detail;
        } else if (Array.isArray(data.detail)) {
          errorMessage = data.detail.map((d: any) => `${d.loc?.join(".")}: ${d.msg}`).join("; ");
          errorDetails = { errors: data.detail };
        }
      }
    }

    throw new ApiError(response.status, errorMessage, errorCode, errorDetails);
  }

  return data as T;
}
