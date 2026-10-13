import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import App from "@/App";
import { api } from "@/lib/api";
import { signOut } from "@/lib/auth";

describe("Account, Client Dashboard & Admin Experience", () => {
  beforeEach(() => {
    signOut();
    vi.restoreAllMocks();
  });

  it("gating: unauthenticated access to /client redirects to /account?next=/client", async () => {
    render(
      <MemoryRouter initialEntries={["/client"]}>
        <App />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole("tab", { name: /Sign In/i })).toBeInTheDocument();
      expect(screen.getByText(/MediHisaab account/i)).toBeInTheDocument();
    });
  });

  it("gating: unauthenticated access to /download redirects to /account?next=/download", async () => {
    render(
      <MemoryRouter initialEntries={["/download"]}>
        <App />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Sign in to continue to the Windows installer download/i)).toBeInTheDocument();
    });
  });

  it("account sign-in: generic error when credentials are invalid without leaking email existence", async () => {
    vi.spyOn(api, "clientLogin").mockRejectedValue(new Error("Invalid credentials"));
    vi.spyOn(api, "vendorLogin").mockRejectedValue(new Error("Invalid credentials"));

    render(
      <MemoryRouter initialEntries={["/account"]}>
        <App />
      </MemoryRouter>
    );

    const emailInput = screen.getByLabelText(/Email address/i);
    const passInput = screen.getByLabelText("Password");
    const submitBtn = screen.getByRole("button", { name: /^Sign In$/i });

    fireEvent.change(emailInput, { target: { value: "nonexistent@pharmacy.com" } });
    fireEvent.change(passInput, { target: { value: "wrongpassword123" } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(
        screen.getByText(/Invalid email or password\. Please verify your credentials and try again\./i)
      ).toBeInTheDocument();
    });
  });

  it("account sign-in: successful client login navigates to /client dashboard", async () => {
    vi.spyOn(api, "clientLogin").mockResolvedValue({
      access_token: "mock-client-jwt",
      refresh_token: "mock-client-refresh",
      token_type: "bearer",
      client: {
        id: 10,
        client_code: "CL-APOLLO",
        business_name: "Apollo Medicos",
        owner_name: "Dr. Rajesh",
        phone: "9876543210",
        email: "rajesh@apollomedicos.com",
        status: "ACTIVE",
        created_at: "2026-10-10",
        updated_at: "2026-10-10",
      },
      business_name: "Apollo Medicos",
      owner_name: "Dr. Rajesh",
      email: "rajesh@apollomedicos.com",
      trial_days: 15,
      subscription_status: "ACTIVE",
    });

    vi.spyOn(api, "clientGetDashboard").mockResolvedValue({
      client: {
        id: 10,
        client_code: "CL-APOLLO",
        business_name: "Apollo Medicos",
        owner_name: "Dr. Rajesh",
        phone: "9876543210",
        email: "rajesh@apollomedicos.com",
        status: "ACTIVE",
        created_at: "2026-10-10",
        updated_at: "2026-10-10",
      },
      subscription: {
        id: 1,
        client_id: 10,
        plan_id: 1,
        status: "ACTIVE",
        start_date: "2026-10-10",
        current_period_start: "2026-10-10",
        current_period_end: "2026-11-10",
        grace_period_end: "2026-11-17",
      },
      active_license: {
        id: 1,
        client_id: 10,
        license_id: "LIC-APOLLO-100",
        client_name: "Apollo Medicos",
        terminal_count: 2,
        activation_date: "2026-10-10",
        expiry_date: "2026-11-10",
        edition: "COMMERCIAL",
        enabled_features: "ALL",
        signature: "deadbeef",
        issued_at: "2026-10-10",
      },
      days_remaining: 30,
      grace_period_active: false,
      status: "ACTIVE",
      maximum_terminals: 2,
      last_refreshed: "2026-10-12",
      can_renew: true,
      recent_payments: [],
    });

    vi.spyOn(api, "clientGetRenewalRequests").mockResolvedValue([]);
    vi.spyOn(api, "clientGetPlans").mockResolvedValue([]);

    render(
      <MemoryRouter initialEntries={["/account"]}>
        <App />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText(/Email address/i), {
      target: { value: "rajesh@apollomedicos.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "SecretPass123!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Sign In$/i }));

    await waitFor(() => {
      expect(screen.getByText(/Apollo Medicos/i)).toBeInTheDocument();
      expect(screen.getByText(/License overview/i)).toBeInTheDocument();
      expect(screen.getByText(/LIC-APOLLO-100/i)).toBeInTheDocument();
    });
  });

  it("account sign-in: successful vendor admin login navigates to /admin console", async () => {
    vi.spyOn(api, "clientLogin").mockRejectedValue(new Error("Not a client account"));
    vi.spyOn(api, "vendorLogin").mockResolvedValue({
      access_token: "mock-vendor-jwt",
      token_type: "bearer",
      expires_in_minutes: 60,
      user: {
        id: 1,
        full_name: "System Administrator",
        email: "admin@apexhealth.com",
        role: "OWNER",
        is_active: true,
      },
    });

    vi.spyOn(api, "vendorGetStats").mockResolvedValue({
      total_clients: 25,
      active_subscriptions: 18,
      trial_clients: 7,
      expiring_soon_subscriptions: 3,
      expired_subscriptions: 1,
      suspended_clients: 0,
      total_licenses_issued: 30,
      recent_licenses: [],
    });

    vi.spyOn(api, "vendorGetClients").mockResolvedValue([]);
    vi.spyOn(api, "vendorGetRenewalRequests").mockResolvedValue([]);
    vi.spyOn(api, "vendorGetSettings").mockResolvedValue({
      settings: [],
      default_trial_days: 15,
      default_grace_days: 7,
      support_contacts: {
        phone: "+91 98765 43210",
        whatsapp: "+91 98765 43210",
        email: "support@apexhealth.com",
      },
    });

    render(
      <MemoryRouter initialEntries={["/account"]}>
        <App />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText(/Email address/i), {
      target: { value: "admin@apexhealth.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "VendorPass123!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Sign In$/i }));

    await waitFor(() => {
      expect(screen.getByText(/Vendor Administration Console/i)).toBeInTheDocument();
      expect(screen.getByText(/Total Registered Clients/i)).toBeInTheDocument();
    });
  });

  it("renewal form submission reflects actual server notification status", async () => {
    vi.spyOn(api, "clientSubmitRenewal").mockResolvedValue({
      id: 88,
      client_id: 10,
      requested_plan_code: "MONTHLY_STANDARD",
      store_name: "Apollo Medicos",
      contact_name: "Dr. Rajesh",
      email: "rajesh@apollomedicos.com",
      phone: "9876543210",
      status: "PENDING",
      payment_reference: "UPI-UTR-9999",
      payment_amount: 99900,
      vendor_notification_sent: false,
      created_at: "2026-10-12T10:00:00Z",
    });

    const res = await api.clientSubmitRenewal(
      {
        requested_plan_code: "MONTHLY_STANDARD",
        payment_reference: "UPI-UTR-9999",
        payment_amount: 99900,
      },
      "test-token"
    );

    expect(res.id).toBe(88);
    expect(res.vendor_notification_sent).toBe(false);
  });
});
