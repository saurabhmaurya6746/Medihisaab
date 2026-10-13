/**
 * Common API error envelopes, pagination interfaces, and system health status contracts.
 */

export interface ApiErrorDetail {
  code: string;
  message: string;
  details?: Record<string, unknown> | null;
  timestamp: string;
}

export interface ApiErrorEnvelope {
  success: false;
  error: ApiErrorDetail;
}

export interface ApiSuccessEnvelope<T> {
  success: true;
  data: T;
  message?: string;
}

export type ApiResponse<T> = ApiSuccessEnvelope<T> | ApiErrorEnvelope;

/**
 * Standard pagination query parameters for list endpoints.
 */
export interface PaginationParams {
  page?: number;
  page_size?: number;
  search?: string;
  sort_by?: string;
  sort_order?: "asc" | "desc";
}

/**
 * Standard paginated response envelope.
 */
export interface PaginatedResult<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

/**
 * System and daemon health diagnostics.
 */
export type ServiceHealthStatus = "HEALTHY" | "DEGRADED" | "UNHEALTHY";

export interface DatabaseHealthInfo {
  status: string;
  journal_mode?: string;
  synchronous?: string;
  foreign_keys?: boolean;
  integrity?: string;
  schema_version?: number;
  path: string;
  size_kb?: number;
  wal_size_kb?: number;
}

export interface SystemHealthResponse {
  status: ServiceHealthStatus;
  version: string;
  uptime_seconds: number;
  database: DatabaseHealthInfo;
  port: number;
  platform: string;
  timestamp: string;
}

/**
 * Statutory Indian Pharmaceutical Regex Patterns
 */
// 15-character GSTIN: 2-digit state code + 10-char PAN + 1 entity num + 'Z' + 1 checksum char
export const GSTIN_REGEX = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/;

// 4 to 8-digit HSN code for pharmaceuticals (e.g. 3004)
export const HSN_REGEX = /^\d{4,8}$/;

// 4-digit numeric cashier unlock PIN
export const PIN_REGEX = /^\d{4}$/;

/**
 * Exact parser converting rupee string representations to integer paise without floating-point conversion.
 * Avoids IEEE-754 precision issues (e.g. 1.14 * 100 = 113.99999999999999).
 *
 * Supports:
 *   - "10.50" -> 1050
 *   - "10.5"  -> 1050
 *   - "10.05" -> 1005
 *   - "10"    -> 1000
 *   - "0.01"  -> 1
 *   - ".50"   -> 50
 *   - "-10.50" -> -1050
 *   - "  10.50 " -> 1050
 */
export function parseRupeesToPaise(value: string | number | null | undefined): number {
  if (value === null || value === undefined) return 0;
  let str: string;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return 0;
    str = value.toString();
  } else {
    str = value.trim();
  }

  if (!str) return 0;

  const isNegative = str.startsWith("-");
  if (isNegative) {
    str = str.slice(1).trim();
  }

  const dotIndex = str.indexOf(".");
  let rupeesStr = "0";
  let paiseStr = "00";

  if (dotIndex === -1) {
    rupeesStr = str;
  } else {
    rupeesStr = str.slice(0, dotIndex) || "0";
    const rawDec = str.slice(dotIndex + 1);
    if (rawDec.length === 0) {
      paiseStr = "00";
    } else if (rawDec.length === 1) {
      paiseStr = rawDec + "0";
    } else if (rawDec.length === 2) {
      paiseStr = rawDec;
    } else {
      // 3 or more decimal places: half-up round based on 3rd digit
      const twoDigits = parseInt(rawDec.slice(0, 2), 10) || 0;
      const thirdDigit = parseInt(rawDec[2], 10) || 0;
      paiseStr = String(thirdDigit >= 5 ? twoDigits + 1 : twoDigits).padStart(2, "0");
    }
  }

  const rupeesInt = parseInt(rupeesStr.replace(/\D/g, "") || "0", 10) || 0;
  const paiseInt = parseInt(paiseStr.replace(/\D/g, "") || "0", 10) || 0;
  const total = rupeesInt * 100 + paiseInt;

  return isNegative ? -total : total;
}

export function paiseToRupees(paise: number): number {
  return paise / 100;
}

export function rupeesToPaise(rupees: string | number | null | undefined): number {
  return parseRupeesToPaise(rupees);
}

export function formatRupees(paise: number): string {
  if (!Number.isFinite(paise)) return "0.00";
  const isNeg = paise < 0;
  const absPaise = Math.abs(Math.trunc(paise));
  const r = Math.floor(absPaise / 100);
  const p = absPaise % 100;
  const formatted = `${r}.${p.toString().padStart(2, "0")}`;
  return isNeg ? `-${formatted}` : formatted;
}
