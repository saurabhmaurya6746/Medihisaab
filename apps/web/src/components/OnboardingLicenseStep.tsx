import React, { useState, useEffect } from "react";
import { MEDIHISAAB_ICON_BASE64 } from "../assets/brand";
import {
  clientLogin,
  fetchSupportContacts,
  getPortalUrl,
  DEFAULT_SUPPORT_CONTACTS,
  type SupportContacts,
} from "../api/licensing";
import { importLicense } from "../api/system";
import { getSetupStatus, login as localLogin } from "../api/auth";
import { ApiError, setStoredToken } from "../api/client";

interface OnboardingLicenseStepProps {
  onLicenseActivated: (prefill?: {
    store_name?: string;
    store_phone?: string;
    store_dl?: string;
    store_gstin?: string;
  }) => void;
}

type TabChoice = "signin" | "import";

export const OnboardingLicenseStep: React.FC<OnboardingLicenseStepProps> = ({
  onLicenseActivated,
}) => {
  const [activeTab, setActiveTab] = useState<TabChoice>("signin");
  const [supportContacts, setSupportContacts] = useState<SupportContacts>(DEFAULT_SUPPORT_CONTACTS);

  // Signin form state
  const [loginForm, setLoginForm] = useState({
    email: "",
    password: "",
  });

  // Import state
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [pendingLicense, setPendingLicense] = useState<Record<string, unknown> | null>(null);
  const [localAdminForm, setLocalAdminForm] = useState({ username: "", password: "" });
  const [needsLocalAdmin, setNeedsLocalAdmin] = useState(false);

  useEffect(() => {
    fetchSupportContacts().then(setSupportContacts).catch(() => {});
  }, []);

  const portalSignupUrl = `${getPortalUrl()}/account?mode=signup`;

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setSuccessMsg(null);

    if (!loginForm.email.trim() || !loginForm.password) {
      setErrorMsg("Please enter your account email and password.");
      return;
    }

    setIsLoading(true);
    try {
      const res = await clientLogin({
        email: loginForm.email.trim(),
        password: loginForm.password,
      });

      if (!res.license_token) {
        throw new Error(
          "No active license found for this client account. Please log in to the online portal to check your subscription status or contact support."
        );
      }

      await importLicense(res.license_token);
      setSuccessMsg(`Welcome, ${res.owner_name || res.business_name || "Pharmacist"}! License cryptographically verified and installed.`);

      setTimeout(() => {
        onLicenseActivated({
          store_name: res.business_name,
          store_phone: res.phone,
        });
      }, 1000);
    } catch (err: any) {
      setErrorMsg(err.message || "Invalid email or password. Please verify your portal credentials.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setErrorMsg(null);
    setSuccessMsg(null);
    setIsLoading(true);

    try {
      const text = await file.text();
      const payload = JSON.parse(text);
      const res = await importLicense(payload);

      setSuccessMsg(`Offline license verified! Edition: ${res.edition}, Expiry: ${res.expiry_date || 'Perpetual'}`);
      setTimeout(() => {
        onLicenseActivated({
          store_name: res.client_name,
        });
      }, 1000);
    } catch (err: any) {
      if (err instanceof ApiError && err.status === 401) {
        try {
          const setup = await getSetupStatus();
          if (setup.is_initialized) {
            setPendingLicense(JSON.parse(await file.text()));
            setNeedsLocalAdmin(true);
            setErrorMsg("This installation already has a local administrator. Sign in below to authorize the license import.");
          } else {
            setErrorMsg("The local setup state changed while importing. Close and reopen MediHisaab, then try again.");
          }
        } catch (statusError: any) {
          setErrorMsg(statusError.message || err.message || "Could not check local administrator status.");
        }
      } else {
        setErrorMsg(err.message || "Failed to import or verify cryptographic signature of license file.");
      }
    } finally {
      setIsLoading(false);
      e.target.value = "";
    }
  };

  const handleLocalAdminImport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pendingLicense) return;
    setErrorMsg(null);
    setSuccessMsg(null);
    setIsLoading(true);
    try {
      const session = await localLogin(localAdminForm);
      if (session.user.role !== "ADMIN") {
        throw new Error("Only a local administrator can import a license file.");
      }
      setStoredToken(session.access_token);
      const res = await importLicense(pendingLicense);
      setSuccessMsg(`Offline license verified! Edition: ${res.edition}, Expiry: ${res.expiry_date || "Perpetual"}`);
      setNeedsLocalAdmin(false);
      setPendingLicense(null);
      setTimeout(() => onLicenseActivated({ store_name: res.client_name }), 500);
    } catch (err: any) {
      setErrorMsg(err.message || "Could not authorize the license import.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-page-wrapper">
      <div className="auth-modal-box" style={{ maxWidth: "560px", width: "100%" }}>
        {/* Header */}
        <div className="auth-header">
          <div className="auth-brand-logo" style={{ background: "transparent", width: "56px", height: "56px" }}>
            <img
              src={MEDIHISAAB_ICON_BASE64}
              alt="MediHisaab Logo"
              style={{ width: "56px", height: "56px", objectFit: "contain" }}
            />
          </div>
          <h1 className="auth-title">Welcome to MediHisaab</h1>
          <p className="auth-subtitle">
            Step 1 of 2: Activate Software License / Evaluation Trial
          </p>
        </div>

        {/* Online Portal Callout */}
        <div
          style={{
            background: "rgba(59, 130, 246, 0.08)",
            border: "1px solid rgba(59, 130, 246, 0.25)",
            borderRadius: "8px",
            padding: "12px 14px",
            marginBottom: "16px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "12px",
          }}
        >
          <div>
            <div style={{ fontSize: "0.82rem", fontWeight: 600, color: "#93c5fd" }}>
              New Pharmacy? Start 15-Day Free Trial
            </div>
            <div style={{ fontSize: "0.76rem", color: "var(--text-muted, #94a3b8)", marginTop: "2px" }}>
              Accounts and free trials are created on the online portal.
            </div>
          </div>
          <a
            href={portalSignupUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-primary"
            style={{
              padding: "6px 12px",
              fontSize: "0.78rem",
              textDecoration: "none",
              whiteSpace: "nowrap",
            }}
          >
            Create Account ↗
          </a>
        </div>

        {/* 2 Choices Navigation */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "4px",
            background: "rgba(0,0,0,0.3)",
            padding: "4px",
            borderRadius: "8px",
            marginBottom: "16px",
          }}
        >
          <button
            type="button"
            onClick={() => { setActiveTab("signin"); setErrorMsg(null); setSuccessMsg(null); }}
            style={{
              padding: "8px 6px",
              fontSize: "0.82rem",
              fontWeight: 600,
              borderRadius: "6px",
              border: "none",
              cursor: "pointer",
              background: activeTab === "signin" ? "#3b82f6" : "transparent",
              color: activeTab === "signin" ? "#ffffff" : "var(--text-muted, #94a3b8)",
              textAlign: "center",
            }}
          >
            Sign In Account
          </button>
          <button
            type="button"
            onClick={() => { setActiveTab("import"); setErrorMsg(null); setSuccessMsg(null); }}
            style={{
              padding: "8px 6px",
              fontSize: "0.82rem",
              fontWeight: 600,
              borderRadius: "6px",
              border: "none",
              cursor: "pointer",
              background: activeTab === "import" ? "#3b82f6" : "transparent",
              color: activeTab === "import" ? "#ffffff" : "var(--text-muted, #94a3b8)",
              textAlign: "center",
            }}
          >
            Import License File
          </button>
        </div>

        {/* Notifications */}
        {errorMsg && (
          <div className="auth-error-banner" style={{ marginBottom: "16px" }}>
            <span>⚠️ {errorMsg}</span>
          </div>
        )}
        {successMsg && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "10px 14px",
              background: "rgba(34, 197, 94, 0.15)",
              border: "1px solid #22c55e",
              borderRadius: "6px",
              color: "#4ade80",
              fontSize: "0.85rem",
              marginBottom: "16px",
            }}
          >
            <span>✓ {successMsg}</span>
          </div>
        )}

        {/* Choice 1: Sign in with existing portal credentials */}
        {activeTab === "signin" && (
          <form onSubmit={handleLoginSubmit} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            <p style={{ margin: 0, fontSize: "0.82rem", color: "var(--text-muted, #94a3b8)" }}>
              Sign in with your registered MediHisaab online account. Your workstation will automatically retrieve and install your signed trial or commercial license.
            </p>

            <div>
              <label className="form-label form-label-required">Online Account Email</label>
              <input
                type="email"
                className="form-input"
                placeholder="Enter your registered portal email"
                value={loginForm.email}
                onChange={(e) => setLoginForm({ ...loginForm, email: e.target.value })}
                required
                disabled={isLoading}
              />
            </div>

            <div>
              <label className="form-label form-label-required">Password</label>
              <input
                type="password"
                className="form-input"
                placeholder="Enter your account password"
                value={loginForm.password}
                onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })}
                required
                disabled={isLoading}
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              disabled={isLoading}
              style={{ padding: "10px", marginTop: "4px", justifyContent: "center" }}
            >
              {isLoading ? "Verifying Account & License..." : "Sign In & Retrieve Signed License"}
            </button>

            <div style={{ textAlign: "center", marginTop: "4px" }}>
              <span style={{ fontSize: "0.78rem", color: "var(--text-muted, #94a3b8)" }}>
                Need a new license or trial?{" "}
                <a
                  href={portalSignupUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: "#38bdf8", textDecoration: "underline" }}
                >
                  Create Account on Online Portal &rarr;
                </a>
              </span>
            </div>
          </form>
        )}

        {/* Choice 2: Import a license file */}
        {activeTab === "import" && (
          <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            <p style={{ margin: 0, fontSize: "0.82rem", color: "var(--text-muted, #94a3b8)" }}>
              For 100% offline air-gapped activation: If the vendor provided you with an Ed25519 digitally signed <code style={{ color: "#38bdf8" }}>.json</code> license file on a USB drive or via email, import it below.
            </p>

            <div
              style={{
                border: "2px dashed var(--border-color, #334155)",
                borderRadius: "8px",
                padding: "24px 16px",
                textAlign: "center",
                background: "rgba(0,0,0,0.15)",
              }}
            >
              <span style={{ fontSize: "2.2rem", display: "block", marginBottom: "8px" }}>📄</span>
              <p style={{ margin: "0 0 12px", fontSize: "0.85rem", color: "var(--text-muted, #94a3b8)" }}>
                Click to browse or drag and drop your license file
              </p>
              <label
                className="btn btn-secondary"
                style={{ display: "inline-block", cursor: "pointer", padding: "8px 20px" }}
              >
                {isLoading ? "Verifying Cryptographic Signature..." : "Select License File (.json)"}
                <input
                  type="file"
                  accept=".json"
                  onChange={handleFileImport}
                  disabled={isLoading}
                  style={{ display: "none" }}
                />
              </label>
            </div>

            {needsLocalAdmin && (
              <form onSubmit={handleLocalAdminImport} style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                <p style={{ margin: 0, fontSize: "0.82rem", color: "var(--text-muted, #94a3b8)" }}>
                  Enter the local MediHisaab administrator credentials to finish importing this file.
                </p>
                <div>
                  <label className="form-label form-label-required">Admin Username</label>
                  <input
                    className="form-input"
                    autoComplete="username"
                    value={localAdminForm.username}
                    onChange={(e) => setLocalAdminForm({ ...localAdminForm, username: e.target.value })}
                    required
                    disabled={isLoading}
                  />
                </div>
                <div>
                  <label className="form-label form-label-required">Admin Password</label>
                  <input
                    className="form-input"
                    type="password"
                    autoComplete="current-password"
                    value={localAdminForm.password}
                    onChange={(e) => setLocalAdminForm({ ...localAdminForm, password: e.target.value })}
                    required
                    disabled={isLoading}
                  />
                </div>
                <button type="submit" className="btn btn-primary" disabled={isLoading}>
                  {isLoading ? "Signing in and importing..." : "Sign In & Import License"}
                </button>
              </form>
            )}
          </div>
        )}

        {/* Support Help Footer */}
        <div
          style={{
            marginTop: "20px",
            paddingTop: "12px",
            borderTop: "1px solid var(--border-color, #334155)",
            fontSize: "0.75rem",
            color: "var(--text-muted, #94a3b8)",
            textAlign: "center",
          }}
        >
          Need assistance? Vendor Support: Phone: <strong>{supportContacts.phone}</strong> | WhatsApp: <strong>{supportContacts.whatsapp}</strong>
        </div>
      </div>
    </div>
  );
};
