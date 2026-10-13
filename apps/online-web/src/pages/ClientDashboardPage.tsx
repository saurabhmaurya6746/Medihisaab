import React, { useState, useEffect } from "react";
import { Link } from "../router/Link";
import { useRouter } from "../router/RouterContext";
import { useAuth } from "../context/AuthContext";
import { softwareApi } from "../api/client";
import type {
  ClientDashboardData,
  RenewalRequestItem,
  ClientPlan,
  SupportContacts,
} from "../types";

export const ClientDashboardPage: React.FC = () => {
  const { navigate } = useRouter();
  const { role, token, logout } = useAuth();

  const [dashboard, setDashboard] = useState<ClientDashboardData | null>(null);
  const [plans, setPlans] = useState<ClientPlan[]>([]);
  const [renewalRequests, setRenewalRequests] = useState<RenewalRequestItem[]>([]);
  const [supportContacts, setSupportContacts] = useState<SupportContacts>({
    phone: "+91 98765 43210",
    whatsapp: "+91 98765 43210",
    email: "support@apexhealth.com",
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Renewal form state
  const [selectedPlanCode, setSelectedPlanCode] = useState("MONTHLY_STANDARD");
  const [paymentRef, setPaymentRef] = useState("");
  const [paymentAmount, setPaymentAmount] = useState<string>("999");
  const [renewalNotes, setRenewalNotes] = useState("");
  const [submittingRenewal, setSubmittingRenewal] = useState(false);
  const [renewalSuccessMsg, setRenewalSuccessMsg] = useState<string | null>(null);
  const [renewalErrorMsg, setRenewalErrorMsg] = useState<string | null>(null);

  // Download state
  const [downloading, setDownloading] = useState(false);
  const [downloadMsg, setDownloadMsg] = useState<string | null>(null);

  // Redirect if not authenticated as client
  useEffect(() => {
    if (role !== "client" || !token) {
      navigate("/account?next=/client", { replace: true });
      return;
    }

    const loadData = async () => {
      try {
        setLoading(true);
        const [dashData, plansData, reqsData, contactsData] = await Promise.all([
          softwareApi.getClientDashboard(token),
          softwareApi.getCommercialPlans(),
          softwareApi.getMyRenewalRequests(token).catch(() => []),
          softwareApi.getSupportContacts().catch(() => ({
            phone: "+91 98765 43210",
            whatsapp: "+91 98765 43210",
            email: "support@apexhealth.com",
          })),
        ]);

        setDashboard(dashData);
        setPlans(plansData);
        setRenewalRequests(reqsData);
        setSupportContacts(contactsData);
      } catch (err: unknown) {
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("Failed to load client dashboard.");
        }
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [role, token, navigate]);

  const handleDownloadInstaller = async () => {
    if (!token) return;
    setDownloading(true);
    setDownloadMsg(null);

    try {
      // Record download request in audit log on server
      await softwareApi.recordDownloadRequest("installer-windows", token);
      setDownloadMsg("Download request recorded. Starting file download...");

      // Trigger download
      const link = document.createElement("a");
      link.href = "/MediHisaab-Setup-1.0.0.exe";
      link.download = "MediHisaab-Setup-1.0.0.exe";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch {
      setDownloadMsg("Starting installer download...");
      window.location.href = "/MediHisaab-Setup-1.0.0.exe";
    } finally {
      setDownloading(false);
    }
  };

  const handleDownloadLicenseJson = async () => {
    if (!token) return;
    try {
      const blob = await softwareApi.downloadClientLicense(token);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${dashboard?.active_license?.license_id || "license"}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to download license file.");
    }
  };

  const handleSubmitRenewal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    setSubmittingRenewal(true);
    setRenewalSuccessMsg(null);
    setRenewalErrorMsg(null);

    try {
      const res = await softwareApi.submitRenewalRequest(
        {
          requested_plan_code: selectedPlanCode,
          payment_reference: paymentRef.trim(),
          payment_amount: paymentAmount ? Math.round(parseFloat(paymentAmount) * 100) : undefined,
          notes: renewalNotes.trim(),
        },
        token
      );

      setRenewalSuccessMsg(
        `Renewal request #${res.id} submitted for review. Vendor support has been alerted and will update your subscription.`
      );
      setPaymentRef("");
      setRenewalNotes("");

      // Refresh renewal requests list
      const updatedReqs = await softwareApi.getMyRenewalRequests(token);
      setRenewalRequests(updatedReqs);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setRenewalErrorMsg(err.message);
      } else {
        setRenewalErrorMsg("Failed to submit renewal request.");
      }
    } finally {
      setSubmittingRenewal(false);
    }
  };

  if (loading) {
    return (
      <div className="page-wrapper" style={{ minHeight: "70vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ textAlign: "center", color: "#64748b" }}>
          <div className="spinner" style={{ margin: "0 auto 1rem auto" }}></div>
          <p>Loading your pharmacy licensing dashboard...</p>
        </div>
      </div>
    );
  }

  if (error || !dashboard) {
    return (
      <div className="page-wrapper" style={{ padding: "4rem 1rem", textAlign: "center" }}>
        <div className="container" style={{ maxWidth: "600px" }}>
          <div className="form-error-alert">{error || "Unable to load dashboard."}</div>
          <button onClick={() => window.location.reload()} className="btn-secondary-trial" style={{ marginTop: "1rem" }}>
            Retry Loading
          </button>
        </div>
      </div>
    );
  }

  const subStatus = dashboard.status || "INACTIVE";
  const daysRem = dashboard.days_remaining;

  return (
    <div className="page-wrapper" style={{ background: "#f8fafc", minHeight: "85vh", padding: "2.5rem 0" }}>
      <div className="container">
        {/* Pharmacy Profile Header */}
        <div className="dashboard-header-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "1rem" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.25rem" }}>
                <span className="guide-step-badge" style={{ background: "#2563eb" }}>Pharmacy Account</span>
                <span style={{ fontSize: "0.85rem", color: "#64748b", fontFamily: "var(--font-mono)" }}>
                  {dashboard.client.client_code}
                </span>
              </div>
              <h1 style={{ fontSize: "1.75rem", fontWeight: 800, color: "#0f172a" }}>
                {dashboard.client.business_name}
              </h1>
              <p style={{ color: "#64748b", fontSize: "0.9rem", marginTop: "2px" }}>
                Pharmacist / Owner: <strong>{dashboard.client.owner_name}</strong> • Email: {dashboard.client.email} • Phone: {dashboard.client.phone}
              </p>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
              <span className={`badge ${subStatus === "ACTIVE" ? "badge-active" : subStatus === "TRIAL" ? "badge-trial" : subStatus === "GRACE" ? "badge-warn" : "badge-danger"}`}>
                {subStatus === "TRIAL" ? "Evaluation Trial" : subStatus === "ACTIVE" ? "Active Subscription" : subStatus === "GRACE" ? "Grace Period Active" : subStatus}
              </span>
              <button onClick={() => { logout(); navigate("/"); }} className="btn-secondary-trial" style={{ padding: "0.4rem 0.85rem", fontSize: "0.825rem" }}>
                Sign Out
              </button>
            </div>
          </div>
        </div>

        {/* Status Metrics Row */}
        <div className="dashboard-metrics-grid">
          <div className="dashboard-metric-card">
            <span className="metric-lbl">Remaining Period</span>
            <div className="metric-val" style={{ color: daysRem !== null && daysRem <= 3 ? "#ef4444" : "#2563eb" }}>
              {daysRem !== null ? `${daysRem} Days` : "—"}
            </div>
            <span className="metric-sub">
              {subStatus === "TRIAL" ? "Evaluation Trial active" : subStatus === "GRACE" ? "Within 7-day grace window" : "Commercial term"}
            </span>
          </div>

          <div className="dashboard-metric-card">
            <span className="metric-lbl">Terminal Workstations</span>
            <div className="metric-val">
              {dashboard.maximum_terminals} {dashboard.maximum_terminals === 1 ? "Counter" : "Counters"}
            </div>
            <span className="metric-sub">Port 38291 Multi-Counter LAN</span>
          </div>

          <div className="dashboard-metric-card">
            <span className="metric-lbl">Signed Ed25519 License</span>
            <div className="metric-val" style={{ fontSize: "1.1rem", fontFamily: "var(--font-mono)" }}>
              {dashboard.active_license?.license_id ? dashboard.active_license.license_id.slice(0, 16) + "..." : "Active"}
            </div>
            <span className="metric-sub">
              Valid until: {dashboard.active_license?.valid_until || "—"}
            </span>
          </div>
        </div>

        {/* 2-Column Main Content */}
        <div className="dashboard-main-grid">
          {/* Left Column: Installer & License Actions */}
          <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
            {/* Authenticated Download Card */}
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">
                  📥 Windows Installer Binary (v1.0.0)
                </h3>
                <span className="badge badge-active">Verified Build</span>
              </div>
              <p style={{ color: "#475569", fontSize: "0.9rem", marginBottom: "1rem" }}>
                Download the official standalone Windows installer. It contains the embedded Python 3.12 daemon, local SQLite WAL engine, and receipt printing spooler.
              </p>

              <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "8px", padding: "1rem", marginBottom: "1.25rem", fontSize: "0.85rem" }}>
                <div style={{ display: "grid", gridTemplateColumns: "130px 1fr", gap: "0.4rem" }}>
                  <span style={{ color: "#64748b" }}>Filename:</span>
                  <strong style={{ fontFamily: "var(--font-mono)" }}>MediHisaab-Setup-1.0.0.exe</strong>

                  <span style={{ color: "#64748b" }}>File Size:</span>
                  <span>91.0 MB (95,442,984 bytes)</span>

                  <span style={{ color: "#64748b" }}>Platform:</span>
                  <span>Windows 10 / Windows 11 (64-bit)</span>

                  <span style={{ color: "#64748b" }}>SHA-256 Hash:</span>
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem", wordBreak: "break-all" }}>
                    2e323e4b90768f866699b24c2aad6ba36f201e092acd65ba8cf6010b0f91c02f
                  </span>
                </div>
              </div>

              {downloadMsg && (
                <div className="alert-info-box" style={{ marginBottom: "1rem", fontSize: "0.85rem", padding: "0.5rem 0.75rem" }}>
                  {downloadMsg}
                </div>
              )}

              <button
                onClick={handleDownloadInstaller}
                disabled={downloading}
                className="btn-primary-download"
                style={{ width: "100%", justifyContent: "center" }}
              >
                {downloading ? "Recording Request..." : "Download Windows Installer (91.0 MB)"}
              </button>
            </div>

            {/* License Token Download Card */}
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">
                  🛡️ Cryptographic License Token (.json)
                </h3>
              </div>
              <p style={{ color: "#475569", fontSize: "0.9rem", marginBottom: "1rem" }}>
                When you sign in from the desktop app, this license activates automatically. You can also download the signed token file for manual offline import.
              </p>

              <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
                <button
                  onClick={handleDownloadLicenseJson}
                  className="btn-secondary-trial"
                  style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}
                >
                  <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  Download License (.json)
                </button>
                <Link to="/how-it-works" className="btn-text-link" style={{ alignSelf: "center", fontSize: "0.85rem" }}>
                  View Installation Guide &rarr;
                </Link>
              </div>
            </div>

            {/* Privacy Guarantee Box */}
            <div className="alert-box" style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: "10px", padding: "1.25rem" }}>
              <strong style={{ color: "#166534", fontSize: "0.95rem", display: "flex", alignItems: "center", gap: "6px" }}>
                <span>🔒</span> Local Pharmacy Data Sovereignty Guarantee
              </strong>
              <p style={{ color: "#166534", fontSize: "0.85rem", marginTop: "0.35rem", lineHeight: 1.5 }}>
                Your medicine inventory, purchase inwarding invoices, sales bills, patient prescriptions, customer Khata credit, and staff PINs remain 100% on your local PC in SQLite. They are never uploaded or synced to this licensing server.
              </p>
            </div>
          </div>

          {/* Right Column: In-App Renewal & Support */}
          <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
            {/* In-App Renewal Request Form */}
            <div className="card" id="renew">
              <div className="card-header">
                <h3 className="card-title">
                  🔄 Submit License Renewal Request
                </h3>
              </div>
              <p style={{ color: "#475569", fontSize: "0.875rem", marginBottom: "1rem" }}>
                Extend your evaluation or commercial plan. Submit your payment reference (UPI UTR / Bank transfer receipt) for vendor review.
              </p>

              {renewalSuccessMsg && <div className="form-success-alert">{renewalSuccessMsg}</div>}
              {renewalErrorMsg && <div className="form-error-alert">{renewalErrorMsg}</div>}

              <form onSubmit={handleSubmitRenewal}>
                <div className="form-group">
                  <label>Select Renewal Plan</label>
                  <select
                    value={selectedPlanCode}
                    onChange={(e) => {
                      setSelectedPlanCode(e.target.value);
                      const target = plans.find((p) => p.plan_code === e.target.value);
                      if (target) {
                        setPaymentAmount((target.price / 100).toString());
                      }
                    }}
                  >
                    {plans.map((p) => (
                      <option key={p.id} value={p.plan_code}>
                        {p.name} — ₹{p.price / 100} ({p.duration_days} days, up to {p.maximum_terminals} counters)
                      </option>
                    ))}
                  </select>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                  <div className="form-group">
                    <label>Amount Paid (₹ INR)</label>
                    <input
                      type="number"
                      required
                      min={0}
                      value={paymentAmount}
                      onChange={(e) => setPaymentAmount(e.target.value)}
                    />
                  </div>

                  <div className="form-group">
                    <label>Payment Reference / UTR</label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. UPI/3091823901 or Cheque #123"
                      value={paymentRef}
                      onChange={(e) => setPaymentRef(e.target.value)}
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label>Notes / Counter Requirements (Optional)</label>
                  <textarea
                    rows={2}
                    placeholder="e.g. Added a second counter terminal in front billing."
                    value={renewalNotes}
                    onChange={(e) => setRenewalNotes(e.target.value)}
                  />
                </div>

                <button
                  type="submit"
                  disabled={submittingRenewal}
                  className="btn-primary-download"
                  style={{ width: "100%", justifyContent: "center" }}
                >
                  {submittingRenewal ? "Submitting Request..." : "Submit Renewal for Approval"}
                </button>
              </form>
            </div>

            {/* Submitted Renewal Requests History */}
            {renewalRequests.length > 0 && (
              <div className="card">
                <div className="card-header">
                  <h3 className="card-title">Recent Renewal Requests</h3>
                </div>
                <div style={{ overflowX: "auto" }}>
                  <table className="specs-table" style={{ fontSize: "0.825rem" }}>
                    <thead>
                      <tr>
                        <th>Req #</th>
                        <th>Plan</th>
                        <th>Reference</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {renewalRequests.map((r) => (
                        <tr key={r.id}>
                          <td>#{r.id}</td>
                          <td>{r.requested_plan_code}</td>
                          <td>{r.payment_reference || "—"}</td>
                          <td>
                            <span className={`badge ${r.status === "APPROVED" ? "badge-active" : r.status === "PENDING" ? "badge-warn" : "badge-danger"}`}>
                              {r.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Vendor Support Contacts Card */}
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">📞 Vendor Technical Support</h3>
              </div>
              <p style={{ color: "#475569", fontSize: "0.875rem", marginBottom: "0.75rem" }}>
                Need assistance with Windows installation, printer spooler setup, or multi-counter LAN configuration?
              </p>
              <ul style={{ listStyle: "none", padding: 0, margin: 0, fontSize: "0.875rem", color: "#334155" }}>
                <li style={{ marginBottom: "0.5rem" }}>
                  <strong>Helpline Telephone:</strong>{" "}
                  <a href={`tel:${supportContacts.phone.replace(/\s+/g, "")}`} style={{ color: "var(--primary)", fontWeight: 600 }}>
                    {supportContacts.phone}
                  </a>
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  <strong>WhatsApp Support:</strong>{" "}
                  <a
                    href={`https://wa.me/${supportContacts.whatsapp.replace(/[^0-9]/g, "")}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: "#059669", fontWeight: 600 }}
                  >
                    Chat on WhatsApp ({supportContacts.whatsapp})
                  </a>
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  <strong>Support Email:</strong>{" "}
                  <a href={`mailto:${supportContacts.email}`} style={{ color: "var(--primary)", fontWeight: 600 }}>
                    {supportContacts.email}
                  </a>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
