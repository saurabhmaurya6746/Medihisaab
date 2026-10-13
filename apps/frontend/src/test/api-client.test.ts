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
      expect(err.message).toContain("Unable to connect to MediHisaab server");
    }
  });

  it("records download request with token before delivery", async () => {
    const mockAuditResponse = {
      success: true,
      data: {
        download_url: "/MediHisaab-Setup-1.0.0.exe",
        filename: "MediHisaab-Setup-1.0.0.exe",
        sha256: "2e323e4b90768f866699b24c2aad6ba36f201e092acd65ba8cf6010b0f91c02f",
        version: "1.0.0",
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
    expect(res.download_url).toBe("/MediHisaab-Setup-1.0.0.exe");
    expect(res.sha256).toBe("2e323e4b90768f866699b24c2aad6ba36f201e092acd65ba8cf6010b0f91c02f");
  });
});
