import React, { useState, useEffect } from "react";
import type { LicenseStatusInfo } from "../api/system";
import { importLicense } from "../api/system";
import {
  fetchSupportContacts,
  submitRenewalRequest,
  clientLogin,
  getStoredClientToken,
  clearStoredClientToken,
  DEFAULT_SUPPORT_CONTACTS,
  type SupportContacts,
  type RenewalRequestResult,
} from "../api/licensing";

interface ContactAdminModalProps {
  isOpen: boolean;
  onClose: () => void;
  licenseInfo: LicenseStatusInfo | null;
  onLicenseUpdated?: (newStatus: LicenseStatusInfo) => void;
}

export const ContactAdminModal: React.FC<ContactAdminModalProps> = ({
  isOpen,
  onClose,
  licenseInfo,
  onLicenseUpdated,
}) => {
  const [contacts, setContacts] = useState<SupportContacts>(DEFAULT_SUPPORT_CONTACTS);
  const [activeTab, setActiveTab] = useState<"contacts" | "request" | "import">("contacts");

  // Renewal form state
  const [selectedPlan, setSelectedPlan] = useState<string>("ANNUAL_STANDARD");
  const [paymentRef, setPaymentRef] = useState<string>("");
  const [notes, setNotes] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submitResult, setSubmitResult] = useState<RenewalRequestResult | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Client authentication state for renewal
  const [hasClientSession, setHasClientSession] = useState<boolean>(() => !!getStoredClientToken());
  const [loginEmail, setLoginEmail] = useState<string>("");
  const [loginPassword, setLoginPassword] = useState<string>("");
  const [isLoggingIn, setIsLoggingIn] = useState<boolean>(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  // File import state
  const [isImporting, setIsImporting] = useState<boolean>(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [importSuccess, setImportSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      fetchSupportContacts().then(setContacts).catch(() => {});
      setSubmitResult(null);
      setSubmitError(null);
      setImportError(null);
      setImportSuccess(null);
      setHasClientSession(!!getStoredClientToken());
      setLoginError(null);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const cleanPhoneForWa = (phone: string) => {
    return phone.replace(/[^0-9]/g, "");
  };

  const storeOrClientName = licenseInfo?.client_name || "Pharmacy";

  const handleClientLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!loginEmail.trim() || !loginPassword) {
      setLoginError("Please enter your account email and password.");
      return;
    }
    setIsLoggingIn(true);
    setLoginError(null);
    try {
      await clientLogin({
        email: loginEmail.trim(),
        password: loginPassword,
      });
      setHasClientSession(true);
      setSubmitError(null);
    } catch (err: any) {
      setLoginError(err.message || "Failed to sign in. Please verify your credentials.");
    } finally {
      setIsLoggingIn(false);
    }
  };

  const handleRenewalSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setSubmitError(null);
    setSubmitResult(null);

    try {
      const res = await submitRenewalRequest({
        requested_plan_code: selectedPlan,
        payment_reference: paymentRef.trim() || undefined,
        notes: notes.trim() || undefined,
      });
      setSubmitResult(res);
    } catch (err: any) {
      if (
        err.message?.includes("expired") ||
        err.message?.includes("401") ||
        err.message?.includes("session") ||
        err.message?.includes("credentials")
      ) {
        setHasClientSession(false);
        setSubmitError("Your client session has expired. Please sign in below to continue.");
      } else {
        setSubmitError(err.message || "Failed to submit renewal request.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsImporting(true);
    setImportError(null);
    setImportSuccess(null);

    try {
      const text = await file.text();
      const payload = JSON.parse(text);
      const updated = await importLicense(payload);
      setImportSuccess(`License verified & activated successfully! Plan: ${updated.edition}, Expiry: ${updated.expiry_date || 'Perpetual'}`);
      if (onLicenseUpdated) {
        onLicenseUpdated(updated);
      }
    } catch (err: any) {
      setImportError(err.message || "Failed to parse and verify license file.");
    } finally {
      setIsImporting(false);
      e.target.value = "";
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0, 0, 0, 0.75)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 9999,
        padding: "1rem",
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "600px",
          backgroundColor: "var(--bg-primary, #0f172a)",
          border: "1px solid var(--border-color, #334155)",
          borderRadius: "12px",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
          overflow: "hidden",
          color: "var(--text-main, #f8fafc)",
          display: "flex",
          flexDirection: "column",
          maxHeight: "90vh",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid var(--border-color, #334155)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            background: "var(--bg-secondary, #1e293b)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span style={{ fontSize: "1.25rem" }}>🛡️</span>
            <div>
              <h3 style={{ margin: 0, fontSize: "1.05rem", fontWeight: 700 }}>
                Vendor Support & License Renewal
              </h3>
              <p style={{ margin: 0, fontSize: "0.78rem", color: "var(--text-muted, #94a3b8)" }}>
                Apex Health Central Licensing Services
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="btn btn-ghost btn-sm"
            style={{ fontSize: "1.2rem", padding: "4px 8px" }}
          >
            ✕
          </button>
        </div>

        {/* License status snippet */}
        <div
          style={{
            padding: "12px 20px",
            background: "rgba(0,0,0,0.25)",
            borderBottom: "1px solid var(--border-color, #334155)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            fontSize: "0.85rem",
          }}
        >
          <div>
            <strong>{licenseInfo?.client_name || "Registered Store"}</strong>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted, #94a3b8)" }}>
              ID: {licenseInfo?.license_id || "Unlicensed"} • {licenseInfo?.edition || "COMMUNITY"}
            </div>
          </div>
          <div style={{ textAlign: "right" }}>
            <span
              style={{
                display: "inline-block",
                padding: "2px 8px",
                borderRadius: "12px",
                fontSize: "0.75rem",
                fontWeight: 600,
                background:
                  licenseInfo?.status === "ACTIVE"
                    ? "rgba(16,185,129,0.2)"
                    : licenseInfo?.status === "TRIAL"
                    ? "rgba(59,130,246,0.2)"
                    : licenseInfo?.status === "GRACE_PERIOD"
                    ? "rgba(245,158,11,0.2)"
                    : "rgba(239,68,68,0.2)",
                color:
                  licenseInfo?.status === "ACTIVE"
                    ? "#34d399"
                    : licenseInfo?.status === "TRIAL"
                    ? "#60a5fa"
                    : licenseInfo?.status === "GRACE_PERIOD"
                    ? "#fbbf24"
                    : "#f87171",
              }}
            >
              {licenseInfo?.message || licenseInfo?.status || "UNKNOWN"}
            </span>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted, #94a3b8)", marginTop: 2 }}>
              Expiry: {licenseInfo?.expiry_date || "Perpetual"}
            </div>
          </div>
        </div>

        {/* Navigation tabs */}
        <div
          style={{
            display: "flex",
            borderBottom: "1px solid var(--border-color, #334155)",
            background: "rgba(0,0,0,0.1)",
          }}
        >
          <button
            type="button"
            onClick={() => setActiveTab("contacts")}
            style={{
              flex: 1,
              padding: "10px",
              background: activeTab === "contacts" ? "var(--bg-secondary, #1e293b)" : "transparent",
              border: "none",
              borderBottom: activeTab === "contacts" ? "2px solid #38bdf8" : "2px solid transparent",
              color: activeTab === "contacts" ? "#38bdf8" : "var(--text-muted, #94a3b8)",
              fontWeight: 600,
              fontSize: "0.85rem",
              cursor: "pointer",
            }}
          >
            1. Contact Vendor Directly
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("request")}
            style={{
              flex: 1,
              padding: "10px",
              background: activeTab === "request" ? "var(--bg-secondary, #1e293b)" : "transparent",
              border: "none",
              borderBottom: activeTab === "request" ? "2px solid #38bdf8" : "2px solid transparent",
              color: activeTab === "request" ? "#38bdf8" : "var(--text-muted, #94a3b8)",
              fontWeight: 600,
              fontSize: "0.85rem",
              cursor: "pointer",
            }}
          >
            2. In-App Renewal Request
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("import")}
            style={{
              flex: 1,
              padding: "10px",
              background: activeTab === "import" ? "var(--bg-secondary, #1e293b)" : "transparent",
              border: "none",
              borderBottom: activeTab === "import" ? "2px solid #38bdf8" : "2px solid transparent",
              color: activeTab === "import" ? "#38bdf8" : "var(--text-muted, #94a3b8)",
              fontWeight: 600,
              fontSize: "0.85rem",
              cursor: "pointer",
            }}
          >
            3. Import Renewed File
          </button>
        </div>

        {/* Tab Body */}
        <div style={{ padding: "20px", overflowY: "auto", flex: 1 }}>
          {/* TAB 1: Direct Support Contacts */}
          {activeTab === "contacts" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-muted, #94a3b8)" }}>
                Reach out to our customer care and subscription desk for commercial licensing, renewal quotes, technical support, or payment verification:
              </p>

              <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "12px" }}>
                {/* Phone Call */}
                <a
                  href={`tel:${contacts.phone}`}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "12px 16px",
                    background: "rgba(30, 41, 59, 0.7)",
                    border: "1px solid var(--border-color, #334155)",
                    borderRadius: "8px",
                    textDecoration: "none",
                    color: "inherit",
                    transition: "border-color 0.2s",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                    <span style={{ fontSize: "1.3rem" }}>📞</span>
                    <div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-muted, #94a3b8)" }}>Phone Support</div>
                      <div style={{ fontWeight: 600, color: "#38bdf8" }}>{contacts.phone}</div>
                    </div>
                  </div>
                  <span style={{ fontSize: "0.8rem", color: "#38bdf8" }}>Call Now →</span>
                </a>

                {/* WhatsApp */}
                <a
                  href={`https://wa.me/${cleanPhoneForWa(contacts.whatsapp)}?text=${encodeURIComponent(`Hello Apex Health, I am contacting you regarding MediHisaab POS license renewal for ${storeOrClientName}.`)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "12px 16px",
                    background: "rgba(34, 197, 94, 0.08)",
                    border: "1px solid rgba(34, 197, 94, 0.3)",
                    borderRadius: "8px",
                    textDecoration: "none",
                    color: "inherit",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                    <span style={{ fontSize: "1.3rem" }}>💬</span>
                    <div>
                      <div style={{ fontSize: "0.75rem", color: "#4ade80" }}>WhatsApp Support Desk</div>
                      <div style={{ fontWeight: 600, color: "#22c55e" }}>{contacts.whatsapp}</div>
                    </div>
                  </div>
                  <span style={{ fontSize: "0.8rem", color: "#4ade80", fontWeight: 600 }}>Chat on WhatsApp →</span>
                </a>

                {/* Email */}
                <a
                  href={`mailto:${contacts.email}?subject=${encodeURIComponent(`MediHisaab License Renewal - ${storeOrClientName}`)}&body=${encodeURIComponent(`Dear Apex Health Team,\n\nWe would like to renew our MediHisaab subscription for ${storeOrClientName}.\n\nLicense ID: ${licenseInfo?.license_id || 'N/A'}\n\nThank you.`)}`}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "12px 16px",
                    background: "rgba(30, 41, 59, 0.7)",
                    border: "1px solid var(--border-color, #334155)",
                    borderRadius: "8px",
                    textDecoration: "none",
                    color: "inherit",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                    <span style={{ fontSize: "1.3rem" }}>✉️</span>
                    <div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-muted, #94a3b8)" }}>Email Subscription Desk</div>
                      <div style={{ fontWeight: 600, color: "#93c5fd" }}>{contacts.email}</div>
                    </div>
                  </div>
                  <span style={{ fontSize: "0.8rem", color: "#93c5fd" }}>Send Email →</span>
                </a>
              </div>

              <div style={{ fontSize: "0.8rem", color: "var(--text-muted, #94a3b8)", marginTop: "8px", background: "rgba(0,0,0,0.2)", padding: "10px", borderRadius: "6px" }}>
                💡 <strong>Renewal Workflow:</strong> Once payment is settled, the vendor generates a cryptographically signed renewal license file. You can import it in Tab 3 to restore full billing immediately.
              </div>
            </div>
          )}

          {/* TAB 2: In-App Renewal Request */}
          {activeTab === "request" && (
            <div>
              {!hasClientSession ? (
                <div style={{ background: "rgba(30, 41, 59, 0.6)", border: "1px solid var(--border-color, #334155)", borderRadius: "8px", padding: "16px" }}>
                  <h4 style={{ margin: "0 0 6px", fontSize: "0.95rem", color: "#38bdf8" }}>🔐 Sign In to Pharmacy Account</h4>
                  <p style={{ margin: "0 0 12px", fontSize: "0.8rem", color: "var(--text-muted, #94a3b8)" }}>
                    To submit an official in-app renewal request, please sign in with your MediHisaab client account credentials created during initial registration.
                  </p>

                  {submitError && (
                    <div style={{ background: "rgba(239, 68, 68, 0.15)", border: "1px solid #ef4444", borderRadius: "6px", padding: "8px 12px", fontSize: "0.8rem", color: "#f87171", marginBottom: "12px" }}>
                      ⚠️ {submitError}
                    </div>
                  )}

                  {loginError && (
                    <div style={{ background: "rgba(239, 68, 68, 0.15)", border: "1px solid #ef4444", borderRadius: "6px", padding: "8px 12px", fontSize: "0.8rem", color: "#f87171", marginBottom: "12px" }}>
                      ⚠️ {loginError}
                    </div>
                  )}

                  <form onSubmit={handleClientLogin} style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                    <div>
                      <label style={{ display: "block", fontSize: "0.78rem", marginBottom: "4px", fontWeight: 600 }}>Pharmacy Account Email</label>
                      <input
                        type="email"
                        className="form-input"
                        placeholder="e.g. rajesh@chemist.com"
                        value={loginEmail}
                        onChange={(e) => setLoginEmail(e.target.value)}
                        required
                        disabled={isLoggingIn}
                        style={{ width: "100%", padding: "8px" }}
                      />
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: "0.78rem", marginBottom: "4px", fontWeight: 600 }}>Account Password</label>
                      <input
                        type="password"
                        className="form-input"
                        placeholder="Your account password"
                        value={loginPassword}
                        onChange={(e) => setLoginPassword(e.target.value)}
                        required
                        disabled={isLoggingIn}
                        style={{ width: "100%", padding: "8px" }}
                      />
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "4px" }}>
                      <span style={{ fontSize: "0.75rem", color: "var(--text-muted, #94a3b8)" }}>
                        Forgot password? Reach support in Tab 1.
                      </span>
                      <button
                        type="submit"
                        className="btn btn-primary"
                        disabled={isLoggingIn}
                        style={{ padding: "8px 16px" }}
                      >
                        {isLoggingIn ? "Signing In..." : "Sign In & Continue →"}
                      </button>
                    </div>
                  </form>
                </div>
              ) : submitResult ? (
                <div style={{ background: "rgba(34, 197, 94, 0.1)", border: "1px solid #22c55e", borderRadius: "8px", padding: "16px", textAlign: "center" }}>
                  <div style={{ fontSize: "1.8rem", marginBottom: "8px" }}>✅</div>
                  <h4 style={{ margin: "0 0 6px", color: "#4ade80" }}>Renewal Request #{submitResult.id} Submitted</h4>
                  <p style={{ margin: "0 0 12px", fontSize: "0.85rem", color: "var(--text-muted, #94a3b8)" }}>
                    {submitResult.vendor_notification_sent
                      ? "Vendor admin has received an automated email alert and will review your renewal."
                      : "Request received on licensing server. Vendor email could not be verified; please also notify support on WhatsApp with your UTR."}
                  </p>
                  <button type="button" className="btn btn-secondary btn-sm" onClick={() => setSubmitResult(null)}>
                    Submit Another Request
                  </button>
                </div>
              ) : (
                <form onSubmit={handleRenewalSubmit} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-muted, #94a3b8)" }}>
                    Submit an official renewal request directly to the licensing server. An automated alert will be dispatched to the vendor team.
                  </p>

                  {submitError && (
                    <div style={{ background: "rgba(239, 68, 68, 0.15)", border: "1px solid #ef4444", borderRadius: "6px", padding: "10px", fontSize: "0.85rem", color: "#f87171" }}>
                      ⚠️ {submitError}
                    </div>
                  )}

                  <div>
                    <label style={{ display: "block", fontSize: "0.8rem", marginBottom: "4px", fontWeight: 600 }}>
                      Selected Plan
                    </label>
                    <select
                      className="form-input"
                      value={selectedPlan}
                      onChange={(e) => setSelectedPlan(e.target.value)}
                      style={{ width: "100%", padding: "8px" }}
                    >
                      <option value="ANNUAL_STANDARD">Annual Standard (1 Counter) — ₹5,990 / Year</option>
                      <option value="ANNUAL_PRO">Annual Multi-Counter (Up to 5 Counters) — ₹11,990 / Year</option>
                      <option value="THREE_YEAR_ENTERPRISE">3-Year Multi-Counter Enterprise — ₹29,990 / 3 Years</option>
                    </select>
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: "0.8rem", marginBottom: "4px", fontWeight: 600 }}>
                      Payment Reference / UPI UTR Number (Optional)
                    </label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="e.g. UPI-2026-X98124 or Cheque #10291"
                      value={paymentRef}
                      onChange={(e) => setPaymentRef(e.target.value)}
                      style={{ width: "100%", padding: "8px" }}
                    />
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: "0.8rem", marginBottom: "4px", fontWeight: 600 }}>
                      Notes / Remarks (Optional)
                    </label>
                    <textarea
                      className="form-input"
                      rows={2}
                      placeholder="e.g. Paid via Google Pay to vendor account."
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      style={{ width: "100%", padding: "8px" }}
                    />
                  </div>

                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "8px" }}>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      style={{ fontSize: "0.75rem", color: "var(--text-muted, #94a3b8)" }}
                      onClick={() => {
                        clearStoredClientToken();
                        setHasClientSession(false);
                      }}
                    >
                      Sign Out of Client Portal
                    </button>
                    <button
                      type="submit"
                      className="btn btn-primary"
                      disabled={isSubmitting}
                      style={{ padding: "8px 20px" }}
                    >
                      {isSubmitting ? "Submitting Request..." : "Send Renewal Request"}
                    </button>
                  </div>
                </form>
              )}
            </div>
          )}

          {/* TAB 3: Import Renewed License */}
          {activeTab === "import" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-muted, #94a3b8)" }}>
                After vendor verification, you will receive a signed license file (<code style={{ color: "#38bdf8" }}>LIC-XXXX.json</code>). Import it below to update your workstation immediately.
              </p>

              {importError && (
                <div style={{ background: "rgba(239, 68, 68, 0.15)", border: "1px solid #ef4444", borderRadius: "6px", padding: "10px", fontSize: "0.85rem", color: "#f87171" }}>
                  ⚠️ {importError}
                </div>
              )}

              {importSuccess && (
                <div style={{ background: "rgba(34, 197, 94, 0.1)", border: "1px solid #22c55e", borderRadius: "6px", padding: "10px", fontSize: "0.85rem", color: "#4ade80" }}>
                  ✓ {importSuccess}
                </div>
              )}

              <div
                style={{
                  border: "2px dashed var(--border-color, #334155)",
                  borderRadius: "8px",
                  padding: "24px",
                  textAlign: "center",
                  background: "rgba(0,0,0,0.15)",
                }}
              >
                <span style={{ fontSize: "2rem", display: "block", marginBottom: "8px" }}>📁</span>
                <p style={{ margin: "0 0 12px", fontSize: "0.85rem", color: "var(--text-muted, #94a3b8)" }}>
                  Select or drag & drop your vendor-issued signed license JSON file
                </p>
                <label
                  className="btn btn-secondary"
                  style={{ display: "inline-block", cursor: "pointer", padding: "8px 20px" }}
                >
                  {isImporting ? "Verifying Ed25519 Signature..." : "Browse License File (.json)"}
                  <input
                    type="file"
                    accept=".json"
                    onChange={handleFileSelect}
                    disabled={isImporting}
                    style={{ display: "none" }}
                  />
                </label>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: "12px 20px",
            borderTop: "1px solid var(--border-color, #334155)",
            background: "var(--bg-secondary, #1e293b)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            fontSize: "0.8rem",
            color: "var(--text-muted, #94a3b8)",
          }}
        >
          <span>🔒 100% Offline POS Verification (Ed25519)</span>
          <button type="button" className="btn btn-secondary btn-sm" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
