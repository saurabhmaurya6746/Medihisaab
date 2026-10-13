import { apiClient, getStoredToken } from "./client";
import type {
  ApiSuccessEnvelope,
  ScheduleH1ReportResponse,
  Gstr1ReportResponse,
  Gstr2ReportResponse,
  SalesRegisterItem,
  PurchaseRegisterItem,
  DayBookCurrentResponse,
  DayBookSession,
} from "@pharmacy/api-contracts";

export interface ReportDateFilter {
  from_date?: string;
  to_date?: string;
  fiscal_year?: string;
}

// Helper to trigger browser CSV file download with Auth token
export async function downloadCsvReport(endpoint: string, params: Record<string, string | undefined> = {}, defaultFilename: string): Promise<void> {
  const query = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v) query.append(k, v);
  }
  const queryString = query.toString();
  const url = `${endpoint}${queryString ? `?${queryString}` : ""}`;

  const token = getStoredToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(url, { headers });
  if (!response.ok) {
    throw new Error(`Failed to download report (${response.status} ${response.statusText})`);
  }

  const blob = await response.blob();
  const downloadUrl = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = downloadUrl;

  const contentDisposition = response.headers.get("content-disposition");
  let filename = defaultFilename;
  if (contentDisposition) {
    const match = contentDisposition.match(/filename=["']?([^"';]+)["']?/i);
    if (match && match[1]) {
      filename = match[1];
    }
  }

  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(downloadUrl);
}

// 1. Schedule H1 Register
export async function getScheduleH1Report(filters?: ReportDateFilter): Promise<ScheduleH1ReportResponse> {
  const res = await apiClient<ApiSuccessEnvelope<ScheduleH1ReportResponse>>("/api/v1/reports/schedule-h1", {
    params: {
      from_date: filters?.from_date,
      to_date: filters?.to_date,
    },
  });
  return res.data;
}

export async function downloadScheduleH1Csv(filters?: ReportDateFilter): Promise<void> {
  return downloadCsvReport(
    "/api/v1/reports/schedule-h1/export",
    { from_date: filters?.from_date, to_date: filters?.to_date },
    "Schedule_H1_Register.csv"
  );
}

// 2. GSTR-1 Tax Filing
export async function getGstr1Report(filters?: ReportDateFilter): Promise<Gstr1ReportResponse> {
  const res = await apiClient<ApiSuccessEnvelope<Gstr1ReportResponse>>("/api/v1/reports/gstr-1", {
    params: {
      from_date: filters?.from_date,
      to_date: filters?.to_date,
      fiscal_year: filters?.fiscal_year,
    },
  });
  return res.data;
}

export async function downloadGstr1Csv(section: "b2b" | "b2c" | "hsn" | "docs", filters?: ReportDateFilter): Promise<void> {
  return downloadCsvReport(
    "/api/v1/reports/gstr-1/export",
    {
      section,
      from_date: filters?.from_date,
      to_date: filters?.to_date,
      fiscal_year: filters?.fiscal_year,
    },
    `GSTR1_${section.toUpperCase()}.csv`
  );
}

// 3. GSTR-2 Purchase Register
export async function getGstr2Report(filters?: ReportDateFilter): Promise<Gstr2ReportResponse> {
  const res = await apiClient<ApiSuccessEnvelope<Gstr2ReportResponse>>("/api/v1/reports/gstr-2", {
    params: {
      from_date: filters?.from_date,
      to_date: filters?.to_date,
    },
  });
  return res.data;
}

export async function downloadGstr2Csv(filters?: ReportDateFilter): Promise<void> {
  return downloadCsvReport(
    "/api/v1/reports/gstr-2/export",
    { from_date: filters?.from_date, to_date: filters?.to_date },
    "GSTR2_Inward_Purchases.csv"
  );
}

// 4. Sales & Purchase Registers
export async function getSalesRegister(filters?: ReportDateFilter): Promise<SalesRegisterItem[]> {
  const res = await apiClient<ApiSuccessEnvelope<SalesRegisterItem[]>>("/api/v1/reports/sales-register", {
    params: {
      from_date: filters?.from_date,
      to_date: filters?.to_date,
    },
  });
  return res.data;
}

export async function downloadSalesRegisterCsv(filters?: ReportDateFilter): Promise<void> {
  return downloadCsvReport(
    "/api/v1/reports/sales-register/export",
    { from_date: filters?.from_date, to_date: filters?.to_date },
    "Sales_Register.csv"
  );
}

export async function getPurchaseRegister(filters?: ReportDateFilter): Promise<PurchaseRegisterItem[]> {
  const res = await apiClient<ApiSuccessEnvelope<PurchaseRegisterItem[]>>("/api/v1/reports/purchase-register", {
    params: {
      from_date: filters?.from_date,
      to_date: filters?.to_date,
    },
  });
  return res.data;
}

export async function downloadPurchaseRegisterCsv(filters?: ReportDateFilter): Promise<void> {
  return downloadCsvReport(
    "/api/v1/reports/purchase-register/export",
    { from_date: filters?.from_date, to_date: filters?.to_date },
    "Purchase_Register.csv"
  );
}

// 5. Day-Book & Cash Reconciliation
export async function getCurrentDayBook(sessionDate?: string): Promise<DayBookCurrentResponse> {
  const res = await apiClient<ApiSuccessEnvelope<DayBookCurrentResponse>>("/api/v1/reports/day-book/current", {
    params: { session_date: sessionDate },
  });
  return res.data;
}

export async function setDayBookOpeningFloat(openingFloatPaise: number, sessionDate?: string): Promise<DayBookSession> {
  const res = await apiClient<ApiSuccessEnvelope<DayBookSession>>("/api/v1/reports/day-book/opening-float", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      opening_float_paise: openingFloatPaise,
      session_date: sessionDate,
    }),
  });
  return res.data;
}

export async function closeDayBook(actualCashPaise: number, notes?: string, sessionDate?: string): Promise<DayBookSession> {
  const res = await apiClient<ApiSuccessEnvelope<DayBookSession>>("/api/v1/reports/day-book/close", {
    method: "POST",
    params: { session_date: sessionDate },
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      actual_cash_paise: actualCashPaise,
      notes,
    }),
  });
  return res.data;
}

export async function getDayBookHistory(limit: number = 30): Promise<DayBookSession[]> {
  const res = await apiClient<ApiSuccessEnvelope<DayBookSession[]>>("/api/v1/reports/day-book/history", {
    params: { limit },
  });
  return res.data;
}
