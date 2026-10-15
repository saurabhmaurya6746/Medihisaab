import { describe, expect, it, vi, beforeEach } from "vitest";
import { api, ApiError } from "@/lib/api";

describe("ApiClient - Envelope & Error Handling", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("correctly unwraps success ApiEnvelope data", async () => {
    const mockEnvelope = {
      success: true,
      data: {
        id: 1,
        client_code: "CL-100",
        business_name: "Apollo Pharmacy",
      },
      message: "Client fetched successfully",
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      text: async () => JSON.stringify(mockEnvelope),
    } as unknown as Response);

    const client = await api.clientGetMe("mock-jwt-token");
    expect(client.id).toBe(1);
    expect(client.client_code).toBe("CL-100");
    expect(client.business_name).toBe("Apollo Pharmacy");
  });

  it("throws ApiError with detail on 401 unauthorized", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      headers: new Headers({ "content-type": "application/json" }),
      text: async () => JSON.stringify({ detail: "Invalid email or password." }),
    } as unknown as Response);

    await expect(api.clientLogin({ email: "wrong@test.com", password: "bad" })).rejects.toThrow(
      "Invalid email or password."
    );
  });

  it("throws ApiError with detail on 403 forbidden account deactivation", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      headers: new Headers({ "content-type": "application/json" }),
      text: async () =>
        JSON.stringify({ detail: "Account is suspended. Contact system owner." }),
    } as unknown as Response);

    try {
      await api.clientLogin({ email: "suspended@test.com", password: "pass" });
      expect.fail("Should have thrown ApiError");
    } catch (err: any) {
      expect(err).toBeInstanceOf(ApiError);
      expect(err.status).toBe(403);
      expect(err.message).toBe("Account is suspended. Contact system owner.");
    }
  });

  it("handles network failures with friendly error message", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("Failed to fetch"));

    try {
      await api.clientGetPlans();
      expect.fail("Should have thrown ApiError");
    } catch (err: any) {
      expect(err).toBeInstanceOf(ApiError);
      expect(err.status).toBe(0);
      expect(err.message).toContain("Unable to connect to the MediHisaab licensing server");
    }
  });

  it("records download request with token before delivery", async () => {
    const mockAuditResponse = {
      success: true,
      data: {
        download_url: "/api/v1/client/downloads/installer-windows/file",
        filename: "MediHisaab-Setup-1.0.7.exe",
        sha256: "f9729901c59d88a0ff39333b1541771f9098da84d0db11198409926ed1b0b0c7",
        version: "1.0.7",
      },
      message: "Installer download request recorded.",
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      text: async () => JSON.stringify(mockAuditResponse),
    } as unknown as Response);

    const res = await api.clientRecordDownloadRequest("installer-windows", "test-token");
    expect(res.download_url).toBe("/api/v1/client/downloads/installer-windows/file");
    expect(res.sha256).toBe("f9729901c59d88a0ff39333b1541771f9098da84d0db11198409926ed1b0b0c7");
    expect(res.version).toBe("1.0.7");
  });

  it("handles network/CORS failures with explicit connection error and isNetworkError flag", async () => {
    global.fetch = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));

    try {
      await api.clientSignup({
        email: "test@example.com",
        password: "Password123!",
        pharmacy_name: "Test Pharmacy",
        contact_person: "Test Owner",
        phone: "+91 98765 43210",
      });
      expect.fail("Should have thrown ApiError");
    } catch (err: any) {
      expect(err).toBeInstanceOf(ApiError);
      expect(err.status).toBe(0);
      expect(err.isNetworkError).toBe(true);
      expect(err.message).toContain("Unable to connect to the MediHisaab licensing server");
      expect(err.message).toContain("network/CORS");
    }
  });

  it("formats FastAPI 422 array validation errors into readable message", async () => {
    const fastApiValidation = {
      detail: [
        {
          type: "string_too_short",
          loc: ["body", "password"],
          msg: "String should have at least 8 characters",
        },
        {
          type: "missing",
          loc: ["body", "phone"],
          msg: "Field required",
        },
      ],
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      headers: new Headers({ "content-type": "application/json" }),
      text: async () => JSON.stringify(fastApiValidation),
    } as unknown as Response);

    try {
      await api.clientSignup({
        email: "test@example.com",
        password: "short",
        pharmacy_name: "Test Pharmacy",
        contact_person: "Test Owner",
        phone: "",
      });
      expect.fail("Should have thrown ApiError");
    } catch (err: any) {
      expect(err).toBeInstanceOf(ApiError);
      expect(err.status).toBe(422);
      expect(err.isValidationError).toBe(true);
      expect(err.message).toContain("password: String should have at least 8 characters");
      expect(err.message).toContain("phone: Field required");
    }
  });

  it("preserves 400 bad request duplicate email error message", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      headers: new Headers({ "content-type": "application/json" }),
      text: async () =>
        JSON.stringify({
          detail: "An account with this email address already exists. Please sign in.",
        }),
    } as unknown as Response);

    try {
      await api.clientSignup({
        email: "duplicate@example.com",
        password: "Password123!",
        pharmacy_name: "Test Pharmacy",
        contact_person: "Test Owner",
        phone: "9876543210",
      });
      expect.fail("Should have thrown ApiError");
    } catch (err: any) {
      expect(err).toBeInstanceOf(ApiError);
      expect(err.status).toBe(400);
      expect(err.isValidationError).toBe(true);
      expect(err.message).toBe("An account with this email address already exists. Please sign in.");
    }
  });
});

import { normalizeApiBaseUrl } from "@/lib/api";

describe("normalizeApiBaseUrl helper", () => {
  it("defaults to /api/v1 when unset, empty, or whitespace", () => {
    expect(normalizeApiBaseUrl(undefined)).toBe("/api/v1");
    expect(normalizeApiBaseUrl(null)).toBe("/api/v1");
    expect(normalizeApiBaseUrl("")).toBe("/api/v1");
    expect(normalizeApiBaseUrl("   ")).toBe("/api/v1");
  });

  it("normalizes hostname without trailing slash", () => {
    expect(normalizeApiBaseUrl("https://medihisaab-portal.onrender.com")).toBe(
      "https://medihisaab-portal.onrender.com/api/v1"
    );
  });

  it("normalizes hostname with trailing slash", () => {
    expect(normalizeApiBaseUrl("https://medihisaab-portal.onrender.com/")).toBe(
      "https://medihisaab-portal.onrender.com/api/v1"
    );
  });

  it("normalizes URL already ending with /api/v1 or /api/v1/", () => {
    expect(normalizeApiBaseUrl("https://medihisaab-portal.onrender.com/api/v1")).toBe(
      "https://medihisaab-portal.onrender.com/api/v1"
    );
    expect(normalizeApiBaseUrl("https://medihisaab-portal.onrender.com/api/v1/")).toBe(
      "https://medihisaab-portal.onrender.com/api/v1"
    );
  });
});
