/**
 * Client API services for licensing, installer downloads, and customer portal.
 * Correctly unwraps ApiEnvelope responses and handles production connectivity.
 */

import type {
  ClientPlan,
  DownloadItem,
  EvaluationSignupPayload,
  EvaluationSignupResponse,
  SupportContacts,
  ClientDashboardData,
  RenewalRequestItem,
  VendorUser,
} from "../types";

const getApiBase = (): string => {
  const envUrl = import.meta.env.VITE_LICENSING_API_URL;
  if (envUrl) {
    const clean = envUrl.endsWith("/") ? envUrl.slice(0, -1) : envUrl;
    return `${clean}/api/v1`;
  }
  return "/api/v1";
};

class SoftwareApiClient {
  private apiBase = getApiBase();

  private async handleResponse<T>(res: Response, fallbackError = "Request failed"): Promise<T> {
    const contentType = res.headers.get("content-type") || "";
    let json: any = null;

    if (contentType.includes("application/json")) {
      try {
        json = await res.json();
      } catch {
        json = null;
      }
    }

    if (!res.ok) {
      const errorMsg =
        (json && (json.detail || json.message)) ||
        `${fallbackError} (HTTP ${res.status})`;
      const err = new Error(errorMsg);
      (err as any).status = res.status;
      throw err;
    }

    if (json && typeof json === "object" && "data" in json) {
      return json.data as T;
    }

    return (json ?? ({} as unknown)) as T;
  }

  async getInstallerInfo(): Promise<DownloadItem> {
    try {
      const res = await fetch("/MediHisaab-Setup-1.0.0.exe", { method: "HEAD" });
      const isAvailable = res.ok;
      return {
        id: "installer-windows",
        title: "MediHisaab Windows Installer (v1.0.0)",
        filename: "MediHisaab-Setup-1.0.0.exe",
        size: "91.0 MB (95,442,984 bytes)",
        version: "v1.0.0 (Production Release)",
        targetPlatform: "Windows 10 / Windows 11 (64-bit)",
        url: "/MediHisaab-Setup-1.0.0.exe",
        isAvailable,
        sha256: "2e323e4b90768f866699b24c2aad6ba36f201e092acd65ba8cf6010b0f91c02f",
        isInstaller: true,
      };
    } catch {
      return {
        id: "installer-windows",
        title: "MediHisaab Windows Installer (v1.0.0)",
        filename: "MediHisaab-Setup-1.0.0.exe",
        size: "91.0 MB (95,442,984 bytes)",
        version: "v1.0.0 (Production Release)",
        targetPlatform: "Windows 10 / Windows 11 (64-bit)",
        url: "/MediHisaab-Setup-1.0.0.exe",
        isAvailable: true,
        sha256: "2e323e4b90768f866699b24c2aad6ba36f201e092acd65ba8cf6010b0f91c02f",
        isInstaller: true,
      };
    }
  }

  async getCommercialPlans(): Promise<ClientPlan[]> {
    try {
      const res = await fetch(`${this.apiBase}/client/plans`);
      if (res.ok) {
        return await this.handleResponse<ClientPlan[]>(res);
      }
    } catch {
      // Fallback below
    }
    return [
      {
        id: 1,
        plan_code: "MONTHLY_STANDARD",
        name: "Standard Counter (Monthly)",
        price: 99900,
        duration_days: 30,
        maximum_terminals: 2,
        description: "Full offline POS, automated hot backups, FEFO dispensing, Schedule H1 registers, up to 2 counters.",
      },
      {
        id: 2,
        plan_code: "ANNUAL_STANDARD",
        name: "Enterprise Multi-Counter (Annual)",
        price: 999900,
        duration_days: 365,
        maximum_terminals: 5,
        description: "High-volume retail pharmacy LAN mode, unlimited bills, priority hotline support, up to 5 counters.",
      },
    ];
  }

  async getSupportContacts(): Promise<SupportContacts> {
    try {
      const res = await fetch(`${this.apiBase}/client/support-contacts`);
      if (res.ok) {
        return await this.handleResponse<SupportContacts>(res);
      }
    } catch {
      // Fallback below
    }
    return {
      phone: "+91 98765 43210",
      whatsapp: "+91 98765 43210",
      email: "support@apexhealth.com",
    };
  }

  async registerTrial(payload: EvaluationSignupPayload): Promise<EvaluationSignupResponse> {
    const res = await fetch(`${this.apiBase}/client/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return await this.handleResponse<EvaluationSignupResponse>(res, "Failed to register evaluation account.");
  }

  async clientLogin(credentials: { email: string; password: string }): Promise<EvaluationSignupResponse> {
    const res = await fetch(`${this.apiBase}/client/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(credentials),
    });
    return await this.handleResponse<EvaluationSignupResponse>(res, "Invalid pharmacy email or password.");
  }

  async vendorLogin(credentials: { email: string; password: string }): Promise<{ access_token: string; user: VendorUser }> {
    const res = await fetch(`${this.apiBase}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(credentials),
    });
    return await this.handleResponse<{ access_token: string; user: VendorUser }>(res, "Invalid administrator credentials.");
  }

  async getClientDashboard(token: string): Promise<ClientDashboardData> {
    const res = await fetch(`${this.apiBase}/client/dashboard`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return await this.handleResponse<ClientDashboardData>(res, "Failed to load client dashboard.");
  }

  async downloadClientLicense(token: string): Promise<Blob> {
    const res = await fetch(`${this.apiBase}/client/license/download`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      throw new Error(`Failed to download license file (HTTP ${res.status})`);
    }
    return await res.blob();
  }

  async submitRenewalRequest(
    payload: { requested_plan_code: string; payment_reference?: string; payment_amount?: number; notes?: string },
    token: string
  ): Promise<RenewalRequestItem> {
    const res = await fetch(`${this.apiBase}/client/renewal-requests`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    });
    return await this.handleResponse<RenewalRequestItem>(res, "Failed to submit renewal request.");
  }

  async getMyRenewalRequests(token: string): Promise<RenewalRequestItem[]> {
    const res = await fetch(`${this.apiBase}/client/renewal-requests`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return await this.handleResponse<RenewalRequestItem[]>(res, "Failed to load renewal requests.");
  }

  async recordDownloadRequest(
    itemId: string,
    token?: string
  ): Promise<{ download_url: string; filename?: string; sha256?: string }> {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    try {
      const res = await fetch(`${this.apiBase}/client/downloads/${itemId}/request`, {
        method: "POST",
        headers,
      });
      if (res.ok) {
        return await this.handleResponse<{ download_url: string; filename?: string; sha256?: string }>(res);
      }
    } catch {
      // Ignore if offline
    }
    return {
      download_url: "/MediHisaab-Setup-1.0.0.exe",
      filename: "MediHisaab-Setup-1.0.0.exe",
      sha256: "2e323e4b90768f866699b24c2aad6ba36f201e092acd65ba8cf6010b0f91c02f",
    };
  }
}

export const softwareApi = new SoftwareApiClient();
