import React, { useState, useRef, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import { PinSwitchModal } from "./PinSwitchModal";
import { ContactAdminModal } from "./ContactAdminModal";
import { getLicenseStatus, type LicenseStatusInfo } from "../api/system";
import { MEDIHISAAB_ICON_BASE64 } from "../assets/brand";

export const LoginView: React.FC = () => {
  const { performLogin, storeName, error: globalError, clearError } = useAuth();
  const [username, setUsername] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [localError, setLocalError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [showPinModal, setShowPinModal] = useState<boolean>(false);
  const [showContactAdminModal, setShowContactAdminModal] = useState<boolean>(false);
  const [licenseInfo, setLicenseInfo] = useState<LicenseStatusInfo | null>(null);

  const usernameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    // Autofocus username on mount
    usernameRef.current?.focus();
    getLicenseStatus().then(setLicenseInfo).catch(() => {});
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    setLocalError(null);

    const cleanUser = username.trim();
    if (!cleanUser) {
      setLocalError("Please enter your operator username.");
      usernameRef.current?.focus();
      return;
    }
    if (!password) {
      setLocalError("Please enter your password.");
      return;
    }

    setIsLoading(true);
    try {
      await performLogin({ username: cleanUser, password });
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

          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label form-label-required" htmlFor="login-username">
                Operator Username
              </label>
              <input
                ref={usernameRef}
                id="login-username"
                className="form-input"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter username"
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
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
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
