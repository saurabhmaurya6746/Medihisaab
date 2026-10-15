import React, { useState, useRef, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import { PinSwitchModal } from "./PinSwitchModal";
import { ContactAdminModal } from "./ContactAdminModal";
import { getLicenseStatus, type LicenseStatusInfo } from "../api/system";
import { MEDIHISAAB_ICON_BASE64 } from "../assets/brand";

type LoginMode = "OWNER" | "STAFF";

export const LoginView: React.FC = () => {
  const { performLogin, performOwnerLogin, storeName, error: globalError, clearError } = useAuth();
  const [mode, setMode] = useState<LoginMode>("OWNER");
  const [ownerEmail, setOwnerEmail] = useState<string>("");
  const [ownerPassword, setOwnerPassword] = useState<string>("");
  const [staffUsername, setStaffUsername] = useState<string>("");
  const [staffPassword, setStaffPassword] = useState<string>("");
  const [localError, setLocalError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [showPinModal, setShowPinModal] = useState<boolean>(false);
  const [showContactAdminModal, setShowContactAdminModal] = useState<boolean>(false);
  const [licenseInfo, setLicenseInfo] = useState<LicenseStatusInfo | null>(null);

  const emailRef = useRef<HTMLInputElement>(null);
  const usernameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (mode === "OWNER") {
      emailRef.current?.focus();
    } else {
      usernameRef.current?.focus();
    }
    getLicenseStatus().then(setLicenseInfo).catch(() => {});
  }, [mode]);

  const handleOwnerSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    setLocalError(null);

    const cleanEmail = ownerEmail.trim();
    if (!cleanEmail) {
      setLocalError("Please enter your email address.");
      emailRef.current?.focus();
      return;
    }
    if (!ownerPassword) {
      setLocalError("Please enter your portal password.");
      return;
    }

    setIsLoading(true);
    try {
      await performOwnerLogin({ email: cleanEmail, password: ownerPassword });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to sign in. Please verify your email and password.";
      setLocalError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleStaffSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    setLocalError(null);

    const cleanUser = staffUsername.trim();
    if (!cleanUser) {
      setLocalError("Please enter your operator username or email.");
      usernameRef.current?.focus();
      return;
    }
    if (!staffPassword) {
      setLocalError("Please enter your password.");
      return;
    }

    setIsLoading(true);
    try {
      await performLogin({ username: cleanUser, password: staffPassword });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Invalid username or password.";
      setLocalError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const displayError = localError || globalError;

  return (
    <div className="auth-page-wrapper">
      <div className="auth-modal-box">
        <div className="auth-header">
          <div className="auth-brand-logo" style={{ background: "transparent", width: "56px", height: "56px" }}>
            <img
              src={MEDIHISAAB_ICON_BASE64}
              alt="MediHisaab"
              style={{ width: "56px", height: "56px", objectFit: "contain" }}
            />
          </div>
          <h1 className="auth-title">{storeName || "MediHisaab"}</h1>
          <p className="auth-subtitle">MediHisaab Offline Counter Terminal — Sign In</p>
        </div>

        <div className="auth-body">
          {/* Mode Switch Tabs: Pharmacy Owner (Portal) vs Staff / Operator (Local) */}
          <div
            style={{
              display: "flex",
              borderBottom: "1px solid var(--border-subtle)",
              marginBottom: "18px",
              backgroundColor: "rgba(255, 255, 255, 0.03)",
              borderRadius: "8px 8px 0 0",
              overflow: "hidden",
            }}
          >
            <button
              type="button"
              onClick={() => {
                setMode("OWNER");
                setLocalError(null);
                clearError();
              }}
              style={{
                flex: 1,
                padding: "11px 14px",
                border: "none",
                borderBottom: mode === "OWNER" ? "2px solid #0284c7" : "2px solid transparent",
                background: mode === "OWNER" ? "var(--bg-surface)" : "transparent",
                color: mode === "OWNER" ? "var(--text-title)" : "var(--text-muted)",
                fontWeight: mode === "OWNER" ? 600 : 500,
                fontSize: "0.88rem",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "6px",
                transition: "all 0.15s ease",
              }}
            >
              <span>🏢</span>
              <span>Pharmacy Owner</span>
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("STAFF");
                setLocalError(null);
                clearError();
              }}
              style={{
                flex: 1,
                padding: "11px 14px",
                border: "none",
                borderBottom: mode === "STAFF" ? "2px solid #0284c7" : "2px solid transparent",
                background: mode === "STAFF" ? "var(--bg-surface)" : "transparent",
                color: mode === "STAFF" ? "var(--text-title)" : "var(--text-muted)",
                fontWeight: mode === "STAFF" ? 600 : 500,
                fontSize: "0.88rem",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "6px",
                transition: "all 0.15s ease",
              }}
            >
              <span>👤</span>
              <span>Staff / Operator</span>
            </button>
          </div>

          {/* Expired License Notice - Clarifies read-only data access vs credential errors */}
          {licenseInfo && (licenseInfo.status === "EXPIRED" || licenseInfo.status === "INVALID_SIGNATURE") && (
            <div
              style={{
                marginBottom: "16px",
                padding: "10px 14px",
                borderRadius: "8px",
                backgroundColor: "rgba(239, 68, 68, 0.12)",
                border: "1px solid rgba(239, 68, 68, 0.35)",
                fontSize: "0.82rem",
                color: "#fca5a5",
                lineHeight: 1.45,
              }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", gap: "8px" }}>
                <span style={{ fontSize: "1rem" }}>⚠️</span>
                <div style={{ flex: 1 }}>
                  <strong style={{ color: "#f87171" }}>
                    {licenseInfo.status === "EXPIRED" ? "Subscription / Trial Expired:" : "License Verification Required:"}
                  </strong>
                  <div style={{ marginTop: "2px", color: "var(--text-main)" }}>
                    {licenseInfo.message || `License expired on ${licenseInfo.expiry_date || "earlier date"}.`}
                  </div>
                  <div style={{ marginTop: "4px", fontSize: "0.78rem", color: "var(--text-muted)" }}>
                    You can still sign in to review, search, and export all historical invoices, ledgers, and inventory.
                  </div>
                  <div style={{ marginTop: "6px" }}>
                    <button
                      type="button"
                      onClick={() => setShowContactAdminModal(true)}
                      style={{
                        background: "none",
                        border: "none",
                        padding: 0,
                        color: "#38bdf8",
                        cursor: "pointer",
                        fontWeight: 600,
                        textDecoration: "underline",
                        fontSize: "0.82rem",
                      }}
                    >
                      Renew Subscription / Contact Admin →
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Error Banner */}
          {displayError && (
            <div className="auth-error-banner">
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                style={{ flexShrink: 0, marginTop: 2 }}
              >
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              <span>{displayError}</span>
            </div>
          )}

          {mode === "OWNER" ? (
            <form onSubmit={handleOwnerSubmit}>
              <div className="form-group">
                <label className="form-label form-label-required" htmlFor="login-email">
                  Email address
                </label>
                <input
                  ref={emailRef}
                  id="login-email"
                  className="form-input"
                  type="email"
                  value={ownerEmail}
                  onChange={(e) => setOwnerEmail(e.target.value)}
                  placeholder="Enter portal email (e.g. owner@pharmacy.com)"
                  autoComplete="email"
                  disabled={isLoading}
                />
              </div>

              <div className="form-group">
                <label className="form-label form-label-required" htmlFor="login-password">
                  Password
                </label>
                <input
                  id="login-password"
                  className="form-input"
                  type="password"
                  value={ownerPassword}
                  onChange={(e) => setOwnerPassword(e.target.value)}
                  placeholder="Enter portal account password"
                  autoComplete="current-password"
                  disabled={isLoading}
                />
              </div>

              <div style={{ marginTop: 20 }}>
                <button
                  type="submit"
                  className="btn btn-primary"
                  style={{ width: "100%", padding: "10px 16px", fontSize: "0.95rem" }}
                  disabled={isLoading}
                >
                  {isLoading ? "Signing In with Portal..." : "Sign In as Owner [Enter]"}
                </button>
              </div>

              <div
                style={{
                  marginTop: "12px",
                  fontSize: "0.78rem",
                  color: "var(--text-muted)",
                  textAlign: "center",
                  lineHeight: 1.4,
                }}
              >
                Sign in using your MediHisaab Web Portal account credentials. Connects to server to sync subscription and securely caches credentials for subsequent offline POS use.
              </div>
            </form>
          ) : (
            <form onSubmit={handleStaffSubmit}>
              <div className="form-group">
                <label className="form-label form-label-required" htmlFor="login-username">
                  Operator Username or Email
                </label>
                <input
                  ref={usernameRef}
                  id="login-username"
                  className="form-input"
                  type="text"
                  value={staffUsername}
                  onChange={(e) => setStaffUsername(e.target.value)}
                  placeholder="Enter username or email"
                  autoComplete="username"
                  disabled={isLoading}
                />
              </div>

              <div className="form-group">
                <label className="form-label form-label-required" htmlFor="login-password">
                  Password
                </label>
                <input
                  id="login-password"
                  className="form-input"
                  type="password"
                  value={staffPassword}
                  onChange={(e) => setStaffPassword(e.target.value)}
                  placeholder="Enter operator password"
                  autoComplete="current-password"
                  disabled={isLoading}
                />
              </div>

              <div style={{ marginTop: 20 }}>
                <button
                  type="submit"
                  className="btn btn-primary"
                  style={{ width: "100%", padding: "10px 16px", fontSize: "0.95rem" }}
                  disabled={isLoading}
                >
                  {isLoading ? "Signing In..." : "Sign In to Terminal [Enter]"}
                </button>
              </div>
            </form>
          )}

          <div
            style={{
              display: "flex",
              alignItems: "center",
              margin: "20px 0 16px",
              color: "var(--border-subtle)",
            }}
          >
            <div style={{ flex: 1, height: 1, backgroundColor: "var(--border-subtle)" }} />
            <span style={{ padding: "0 10px", fontSize: "0.75rem", color: "var(--text-dim)" }}>
              OR QUICK UNLOCK
            </span>
            <div style={{ flex: 1, height: 1, backgroundColor: "var(--border-subtle)" }} />
          </div>

          <button
            type="button"
            className="btn btn-secondary"
            style={{ width: "100%" }}
            onClick={() => setShowPinModal(true)}
            disabled={isLoading}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#38bdf8"
              strokeWidth="2"
            >
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
            <span>Unlock Counter with 4-Digit PIN [F4]</span>
          </button>

          {/* License Status Pill / Link */}
          {licenseInfo && (
            <div style={{ marginTop: "16px", textAlign: "center" }}>
              <button
                type="button"
                onClick={() => setShowContactAdminModal(true)}
                style={{
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  fontSize: "0.78rem",
                  color:
                    licenseInfo.status === "ACTIVE"
                      ? "var(--text-dim)"
                      : licenseInfo.status === "TRIAL"
                      ? "#60a5fa"
                      : licenseInfo.status === "GRACE_PERIOD"
                      ? "#fbbf24"
                      : "#f87171",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "4px 8px",
                  borderRadius: "6px",
                }}
              >
                <span>🛡️ {licenseInfo.message || licenseInfo.status}</span>
                <span style={{ textDecoration: "underline" }}>• Contact Admin / Renew</span>
              </button>
            </div>
          )}
        </div>
      </div>

      <PinSwitchModal
        isOpen={showPinModal}
        onClose={() => setShowPinModal(false)}
        title="Fast Cashier PIN Unlock"
      />

      <ContactAdminModal
        isOpen={showContactAdminModal}
        onClose={() => setShowContactAdminModal(false)}
        licenseInfo={licenseInfo}
        onLicenseUpdated={(newStatus) => setLicenseInfo(newStatus)}
      />
    </div>
  );
};
