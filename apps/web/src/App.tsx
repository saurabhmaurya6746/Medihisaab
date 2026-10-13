import React, { useState, useEffect } from "react";
import { SettingsProvider } from "./context/SettingsContext";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { FirstRunSetup } from "./components/FirstRunSetup";
import { OnboardingLicenseStep } from "./components/OnboardingLicenseStep";
import { LoginView } from "./components/LoginView";
import { AppShell } from "./components/AppShell";
import { getLicenseStatus, type LicenseStatusInfo } from "./api/system";

const MainRouter: React.FC = () => {
  const { user, isInitialized, isLoading, error, refreshSession } = useAuth();
  const [licenseInfo, setLicenseInfo] = useState<LicenseStatusInfo | null>(null);
  const [isCheckingLicense, setIsCheckingLicense] = useState<boolean>(true);
  const [prefillData, setPrefillData] = useState<{
    store_name?: string;
    store_phone?: string;
    store_dl?: string;
    store_gstin?: string;
  } | undefined>(undefined);

  useEffect(() => {
    let isMounted = true;
    getLicenseStatus()
      .then((status) => {
        if (isMounted) {
          setLicenseInfo(status);
          setIsCheckingLicense(false);
        }
      })
      .catch(() => {
        if (isMounted) {
          setIsCheckingLicense(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, [isInitialized]);

  // 1. Initial Loading / Connection Screen
  if ((isLoading && isInitialized === null) || (isCheckingLicense && isInitialized === false)) {
    return (
      <div className="auth-page-wrapper">
        <div className="auth-modal-box" style={{ textAlign: "center", padding: "40px 24px" }}>
          <div className="auth-brand-logo" style={{ animation: "pulse 1.5s infinite" }}>
            <svg
              width="28"
              height="28"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M19 10.5h-5.5V5c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v5.5H5c-.83 0-1.5.67-1.5 1.5s.67 1.5 1.5 1.5h5.5V19c0 .83.67 1.5 1.5 1.5s1.5-.67 1.5-1.5v-5.5H19c.83 0 1.5-.67 1.5-1.5s-.67-1.5-1.5-1.5z" />
            </svg>
          </div>
          <h2 style={{ fontSize: "1.15rem", fontWeight: 700, color: "#ffffff", marginBottom: 8 }}>
            Connecting to Local Daemon...
          </h2>
          <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
            Checking database initialization status on 127.0.0.1:38291
          </p>
        </div>
      </div>
    );
  }

  // 2. Offline / Fatal Connection Error before initialization
  if (isInitialized === null && error) {
    return (
      <div className="auth-page-wrapper">
        <div className="auth-modal-box" style={{ padding: "32px 24px", textAlign: "center" }}>
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: "50%",
              backgroundColor: "rgba(239, 68, 68, 0.15)",
              color: "#ef4444",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              marginBottom: 16,
            }}
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
          <h2 style={{ fontSize: "1.2rem", fontWeight: 700, color: "#ffffff", marginBottom: 8 }}>
            Pharmacy Daemon Offline
          </h2>
          <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginBottom: 20 }}>
            {error}
          </p>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => refreshSession()}
            style={{ padding: "8px 20px" }}
          >
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  // 3. First-run wizard if store is uninitialized
  if (isInitialized === false) {
    const hasActiveLicense =
      licenseInfo &&
      (licenseInfo.status === "ACTIVE" ||
        licenseInfo.status === "TRIAL" ||
        licenseInfo.status === "GRACE_PERIOD");

    if (!hasActiveLicense) {
      return (
        <OnboardingLicenseStep
          onLicenseActivated={(prefill) => {
            setPrefillData(prefill);
            getLicenseStatus().then(setLicenseInfo).catch(() => {});
            refreshSession();
          }}
        />
      );
    }

    return <FirstRunSetup initialPrefill={prefillData} />;
  }

  // 4. Operator Login if not authenticated
  if (!user) {
    return <LoginView />;
  }

  // 5. Authenticated Terminal AppShell
  return <AppShell />;
};

export const App: React.FC = () => {
  return (
    <SettingsProvider>
      <AuthProvider>
        <MainRouter />
      </AuthProvider>
    </SettingsProvider>
  );
};

export default App;
