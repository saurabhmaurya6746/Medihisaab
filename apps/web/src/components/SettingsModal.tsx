import React, { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import {
  useSettings,
  AppSettings,
  AppTheme,
  ModuleSettings,
  POSPreferences,
  DEFAULT_SETTINGS,
} from "../context/SettingsContext";
import { getLicenseStatus, importLicense, LicenseStatusInfo } from "../api/system";
import { ConfirmModal } from "./ConfirmModal";
import { ContactAdminModal } from "./ContactAdminModal";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type SettingsSection = "appearance" | "modules" | "preferences" | "license";

interface ModuleMeta {
  key: keyof ModuleSettings;
  label: string;
  shortcut?: string;
  description: string;
}

const OPTIONAL_MODULES: ModuleMeta[] = [
  {
    key: "medicines",
    label: "Medicines",
    shortcut: "F2",
    description: "Drug database, salts, packaging units, and Schedule H1 drugs.",
  },
  {
    key: "suppliers",
    label: "Suppliers",
    shortcut: "F3",
    description: "Supplier accounts, contact ledgers, payment tracking, and purchase bills.",
  },
  {
    key: "purchases",
    label: "Purchases",
    shortcut: "F6",
    description: "Purchase bills, batch entry, cost rates, and GST breakdown.",
  },
  {
    key: "customers",
    label: "Customers",
    shortcut: "F5",
    description: "Customer profiles, contact numbers, doctor details, and purchase records.",
  },
  {
    key: "inventory",
    label: "Inventory",
    shortcut: "F7",
    description: "Batch stock management, expiry tracking, near-expiry alerts, and return dump.",
  },
  {
    key: "stockAudit",
    label: "Stock Audit",
    shortcut: "F8",
    description: "Physical stock reconciliation, discrepancy logging, and batch counting.",
  },
  {
    key: "khata",
    label: "Customer Khata",
    shortcut: "F4",
    description: "Customer credit accounts, outstanding balances, and payment collection.",
  },
  {
    key: "salesReturns",
    label: "Sales Returns",
    shortcut: "Ctrl+Shift+R",
    description: "Customer credit notes, sales return processing, and inventory replenishment.",
  },
  {
    key: "purchaseReturns",
    label: "Purchase Returns",
    shortcut: "Ctrl+Shift+P",
    description: "Supplier debit notes, returned stock management, and balance adjustments.",
  },
  {
    key: "wastage",
    label: "Wastage",
    shortcut: "Ctrl+Shift+W",
    description: "Damaged, broken, expired, or spoiled medicine write-offs and scrap records.",
  },
  {
    key: "reports",
    label: "Reports",
    shortcut: "F9",
    description: "Daily sales audit, GST tax returns, Schedule H1 drug register, and profit analysis.",
  },
];

interface PreferenceMeta {
  key: keyof POSPreferences;
  label: string;
  description: string;
}

const POS_PREFERENCES: PreferenceMeta[] = [
  {
    key: "autoPrintReceipt",
    label: "Automatically print receipt after billing",
    description: "Automatically send sales receipts to the receipt printer queue upon completing a sale.",
  },
  {
    key: "barcodeScanner",
    label: "Enable barcode scanner",
    description: "Allow hardware barcode scanners to rapidly search and populate items by barcode.",
  },
  {
    key: "lowStockAlerts",
    label: "Show low-stock alerts",
    description: "Notify the operator when medicine stock falls below the minimum level.",
  },
  {
    key: "expiryAlerts",
    label: "Show expiry alerts",
    description: "Highlight batches near or past expiration date in billing and inventory lists.",
  },
  {
    key: "allowDiscounts",
    label: "Allow discounts during billing",
    description: "Allow authorized operators to apply discounts to a sale.",
  },
  {
    key: "allowCreditSales",
    label: "Allow credit/Khata sales",
    description: "Allow operators to book sales to customer credit ledgers (Khata).",
  },
];

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose }) => {
  const { user } = useAuth();
  const { settings, updateSettings, resetSettings } = useSettings();

  const [activeSection, setActiveSection] = useState<SettingsSection>("appearance");
  const [draft, setDraft] = useState<AppSettings>(settings);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  // License state
  const [licenseData, setLicenseData] = useState<LicenseStatusInfo | null>(null);
  const [isLicenseLoading, setIsLicenseLoading] = useState<boolean>(false);
  const [licenseImportError, setLicenseImportError] = useState<string | null>(null);
  const [licenseImportSuccess, setLicenseImportSuccess] = useState<string | null>(null);
  const [showContactAdminModal, setShowContactAdminModal] = useState<boolean>(false);

  // Confirmation dialogs
  const [moduleToDisable, setModuleToDisable] = useState<ModuleMeta | null>(null);
  const [showResetConfirm, setShowResetConfirm] = useState<boolean>(false);

  const fetchLicense = async () => {
    setIsLicenseLoading(true);
    setLicenseImportError(null);
    try {
      const data = await getLicenseStatus();
      setLicenseData(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load license status";
      setLicenseImportError(msg);
    } finally {
      setIsLicenseLoading(false);
    }
  };

  const handleLicenseFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLicenseImportError(null);
    setLicenseImportSuccess(null);
    try {
      const text = await file.text();
      let parsed: Record<string, unknown>;
      try {
        parsed = JSON.parse(text);
      } catch {
        setLicenseImportError("Selected file is not valid JSON.");
        return;
      }
      if (!parsed.client_name || !parsed.license_id || !parsed.signature) {
        setLicenseImportError("Invalid license file: Missing required client_name, license_id, or signature attributes.");
        return;
      }
      const updated = await importLicense(parsed);
      setLicenseData(updated);
      setLicenseImportSuccess(`License activated successfully for "${updated.client_name}" (${updated.terminal_count} terminals).`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "License signature is invalid, tampered, or expired.";
      setLicenseImportError(msg);
    } finally {
      e.target.value = "";
    }
  };

  // Sync draft whenever modal is opened
  useEffect(() => {
    if (isOpen) {
      setDraft(settings);
      setSaveSuccessMsg(null);
      setValidationError(null);
      setLicenseImportError(null);
      setLicenseImportSuccess(null);
      setActiveSection("appearance");
    }
  }, [isOpen, settings]);

  // Load license when license tab is opened
  useEffect(() => {
    if (isOpen && activeSection === "license") {
      fetchLicense();
    }
  }, [isOpen, activeSection]);

  // Handle Escape key
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (moduleToDisable !== null) {
          setModuleToDisable(null);
        } else if (showResetConfirm) {
          setShowResetConfirm(false);
        } else {
          onClose();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, moduleToDisable, showResetConfirm, onClose]);

  // Non-admin check
  if (!isOpen || !user || user.role !== "ADMIN") {
    return null;
  }

  // Count currently enabled modules in draft
  const enabledModuleCount = Object.values(draft.modules).filter(Boolean).length;

  const handleThemeChange = (newTheme: AppTheme) => {
    setDraft((prev) => ({ ...prev, theme: newTheme }));
    setSaveSuccessMsg(null);
  };

  const handleModuleToggle = (mod: ModuleMeta) => {
    const isCurrentlyActive = draft.modules[mod.key];
    setValidationError(null);

    if (isCurrentlyActive) {
      // Disabling module: check if it's the last operational module
      if (enabledModuleCount <= 1) {
        setValidationError("Cannot disable module: At least one operational module must remain enabled.");
        return;
      }
      // Request confirmation before disabling
      setModuleToDisable(mod);
    } else {
      // Enabling module immediately in draft
      setDraft((prev) => ({
        ...prev,
        modules: {
          ...prev.modules,
          [mod.key]: true,
        },
      }));
      setSaveSuccessMsg(null);
    }
  };

  const confirmDisableModule = () => {
    if (moduleToDisable) {
      setDraft((prev) => ({
        ...prev,
        modules: {
          ...prev.modules,
          [moduleToDisable.key]: false,
        },
      }));
      setModuleToDisable(null);
      setSaveSuccessMsg(null);
    }
  };

  const handlePreferenceToggle = (prefKey: keyof POSPreferences) => {
    setDraft((prev) => ({
      ...prev,
      preferences: {
        ...prev.preferences,
        [prefKey]: !prev.preferences[prefKey],
      },
    }));
    setSaveSuccessMsg(null);
  };

  const handleApplyChanges = () => {
    // Safety check: ensure at least one module is enabled
    const enabledCount = Object.values(draft.modules).filter(Boolean).length;
    if (enabledCount === 0) {
      setValidationError("Cannot save: At least one operational module must remain enabled.");
      return;
    }

    updateSettings(draft);
    setSaveSuccessMsg("Settings saved successfully.");
    setTimeout(() => {
      onClose();
    }, 800);
  };

  const handleConfirmReset = () => {
    resetSettings();
    setDraft(DEFAULT_SETTINGS);
    setShowResetConfirm(false);
    setSaveSuccessMsg("Settings reset to defaults successfully.");
    setTimeout(() => {
      onClose();
    }, 800);
  };

  return (
    <>
      <div className="modal-backdrop" onClick={onClose}>
        <div
          className="modal-dialog settings-modal-dialog"
          onClick={(e) => e.stopPropagation()}
          role="dialog"
          aria-modal="true"
          aria-labelledby="settings-dialog-title"
        >
          {/* Header */}
          <div className="modal-header">
            <div className="modal-title" id="settings-dialog-title">
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                style={{ color: "var(--accent-primary)" }}
              >
                <circle cx="12" cy="12" r="3" />
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
              </svg>
              <span>Admin Terminal Settings</span>
              <span className="role-pill role-pill-admin" style={{ marginLeft: 8 }}>
                ADMIN
              </span>
            </div>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={onClose}
              title="Close [Esc]"
              aria-label="Close settings"
            >
              ✕
            </button>
          </div>

          {/* Body: Sidebar + Main Content */}
          <div className="settings-modal-body">
            {/* Sidebar Navigation */}
            <aside className="settings-sidebar">
              <button
                type="button"
                className={`settings-nav-item ${activeSection === "appearance" ? "active" : ""}`}
                onClick={() => setActiveSection("appearance")}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="5" />
                  <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
                </svg>
                <span>Appearance</span>
              </button>

              <button
                type="button"
                className={`settings-nav-item ${activeSection === "modules" ? "active" : ""}`}
                onClick={() => setActiveSection("modules")}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="3" width="7" height="7" />
                  <rect x="14" y="3" width="7" height="7" />
                  <rect x="14" y="14" width="7" height="7" />
                  <rect x="3" y="14" width="7" height="7" />
                </svg>
                <span>Modules</span>
              </button>

              <button
                type="button"
                className={`settings-nav-item ${activeSection === "preferences" ? "active" : ""}`}
                onClick={() => setActiveSection("preferences")}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
                </svg>
                <span>Preferences</span>
              </button>

              <button
                type="button"
                className={`settings-nav-item ${activeSection === "license" ? "active" : ""}`}
                onClick={() => {
                  setActiveSection("license");
                  setValidationError(null);
                  setLicenseImportError(null);
                  setLicenseImportSuccess(null);
                }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                  <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                </svg>
                <span>License</span>
              </button>
            </aside>

            {/* Content Panel */}
            <main className="settings-content-panel">
              {validationError && (
                <div className="auth-error-banner" style={{ margin: 0 }}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="8" x2="12" y2="12" />
                    <line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                  <span>{validationError}</span>
                </div>
              )}

              {/* 1. Appearance Section */}
              {activeSection === "appearance" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                  <div className="settings-section-header">
                    <h3 className="settings-section-title">Application Theme</h3>
                    <p className="settings-section-desc">
                      Select how the pharmacy workstation appears. Changes apply across the entire interface including headers, tables, dialogs, and forms.
                    </p>
                  </div>

                  <div className="theme-options-grid">
                    {/* Light Theme Card */}
                    <div
                      tabIndex={0}
                      role="radio"
                      aria-checked={draft.theme === "light"}
                      className={`theme-card ${draft.theme === "light" ? "selected" : ""}`}
                      onClick={() => handleThemeChange("light")}
                      onKeyDown={(e) => {
                        if (e.key === " " || e.key === "Enter") {
                          e.preventDefault();
                          handleThemeChange("light");
                        }
                      }}
                    >
                      <div className="theme-card-icon">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <circle cx="12" cy="12" r="5" />
                          <line x1="12" y1="1" x2="12" y2="3" />
                          <line x1="12" y1="21" x2="12" y2="23" />
                          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
                          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
                          <line x1="1" y1="12" x2="3" y2="12" />
                          <line x1="21" y1="12" x2="23" y2="12" />
                          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
                          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
                        </svg>
                      </div>
                      <div className="theme-card-title">Light</div>
                      <div className="theme-card-desc">
                        Crisp light backgrounds with high contrast for bright daylight environments.
                      </div>
                      {draft.theme === "light" && (
                        <span className="badge badge-info" style={{ marginTop: 4 }}>
                          Active
                        </span>
                      )}
                    </div>

                    {/* Dark Theme Card */}
                    <div
                      tabIndex={0}
                      role="radio"
                      aria-checked={draft.theme === "dark"}
                      className={`theme-card ${draft.theme === "dark" ? "selected" : ""}`}
                      onClick={() => handleThemeChange("dark")}
                      onKeyDown={(e) => {
                        if (e.key === " " || e.key === "Enter") {
                          e.preventDefault();
                          handleThemeChange("dark");
                        }
                      }}
                    >
                      <div className="theme-card-icon">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                        </svg>
                      </div>
                      <div className="theme-card-title">Dark</div>
                      <div className="theme-card-desc">
                        Standard high-density dark workspace design to reduce eye strain.
                      </div>
                      {draft.theme === "dark" && (
                        <span className="badge badge-info" style={{ marginTop: 4 }}>
                          Active
                        </span>
                      )}
                    </div>

                    {/* System Default Card */}
                    <div
                      tabIndex={0}
                      role="radio"
                      aria-checked={draft.theme === "system"}
                      className={`theme-card ${draft.theme === "system" ? "selected" : ""}`}
                      onClick={() => handleThemeChange("system")}
                      onKeyDown={(e) => {
                        if (e.key === " " || e.key === "Enter") {
                          e.preventDefault();
                          handleThemeChange("system");
                        }
                      }}
                    >
                      <div className="theme-card-icon">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
                          <line x1="8" y1="21" x2="16" y2="21" />
                          <line x1="12" y1="17" x2="12" y2="21" />
                        </svg>
                      </div>
                      <div className="theme-card-title">System Default</div>
                      <div className="theme-card-desc">
                        Automatically matches your operating system light or dark color preference.
                      </div>
                      {draft.theme === "system" && (
                        <span className="badge badge-info" style={{ marginTop: 4 }}>
                          Active
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* 2. Modules Section */}
              {activeSection === "modules" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  <div className="settings-section-header">
                    <h3 className="settings-section-title">Operational Modules</h3>
                    <p className="settings-section-desc">
                      Enable or disable optional system modules. Disabled modules are removed from the navigation bar and keyboard shortcuts without deleting any data.
                    </p>
                  </div>

                  {/* Core Always-Enabled Banner */}
                  <div className="settings-item-row locked" style={{ borderLeft: "4px solid var(--accent-success)" }}>
                    <div className="settings-item-info">
                      <div className="settings-item-title-wrap">
                        <span className="settings-item-title" title="Shortcut: F1">Counter Sales & Billing</span>
                        <span className="badge badge-success" style={{ fontSize: "0.72rem" }}>Always active</span>
                      </div>
                      <p className="settings-item-desc">
                        Main counter billing terminal and invoice register. Core operational functions cannot be disabled.
                      </p>
                    </div>
                  </div>

                  {/* Optional Modules List */}
                  {OPTIONAL_MODULES.map((mod) => {
                    const isChecked = draft.modules[mod.key];
                    const inputId = `module-toggle-${mod.key}`;

                    return (
                      <div key={mod.key} className="settings-item-row">
                        <div className="settings-item-info">
                          <div className="settings-item-title-wrap">
                            <label
                              htmlFor={inputId}
                              className="settings-item-title"
                              style={{ cursor: "pointer" }}
                              title={mod.shortcut ? `Shortcut: ${mod.shortcut}` : undefined}
                            >
                              {mod.label}
                            </label>
                          </div>
                          <p className="settings-item-desc">{mod.description}</p>
                        </div>

                        <label className="toggle-switch-container" htmlFor={inputId}>
                          <input
                            id={inputId}
                            type="checkbox"
                            className="toggle-switch-input"
                            checked={isChecked}
                            onChange={() => handleModuleToggle(mod)}
                            aria-label={`Toggle ${mod.label} module`}
                          />
                          <span className="toggle-switch-track">
                            <span className="toggle-switch-thumb" />
                          </span>
                        </label>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* 3. Preferences Section */}
              {activeSection === "preferences" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  <div className="settings-section-header">
                    <h3 className="settings-section-title">Terminal Preferences</h3>
                    <p className="settings-section-desc">
                      Configure operational behavior for billing, hardware scanner support, alerts, and discount authorizations.
                    </p>
                  </div>

                  {POS_PREFERENCES.map((pref) => {
                    const isChecked = draft.preferences[pref.key];
                    const inputId = `pref-toggle-${pref.key}`;

                    return (
                      <div key={pref.key} className="settings-item-row">
                        <div className="settings-item-info">
                          <label htmlFor={inputId} className="settings-item-title" style={{ cursor: "pointer" }}>
                            {pref.label}
                          </label>
                          <p className="settings-item-desc">{pref.description}</p>
                        </div>

                        <label className="toggle-switch-container" htmlFor={inputId}>
                          <input
                            id={inputId}
                            type="checkbox"
                            className="toggle-switch-input"
                            checked={isChecked}
                            onChange={() => handlePreferenceToggle(pref.key)}
                            aria-label={`Toggle preference: ${pref.label}`}
                          />
                          <span className="toggle-switch-track">
                            <span className="toggle-switch-thumb" />
                          </span>
                        </label>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* 4. License Section */}
              {activeSection === "license" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                  <div className="settings-section-header">
                    <h3 className="settings-section-title">Client Software License</h3>
                    <p className="settings-section-desc">
                      Manage offline client license and terminal entitlements. Digital signatures are verified against the embedded Ed25519 public key.
                    </p>
                  </div>

                  {licenseImportError && (
                    <div className="auth-error-banner" style={{ margin: 0 }}>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="12" cy="12" r="10" />
                        <line x1="12" y1="8" x2="12" y2="12" />
                        <line x1="12" y1="16" x2="12.01" y2="16" />
                      </svg>
                      <span>{licenseImportError}</span>
                    </div>
                  )}

                  {licenseImportSuccess && (
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        padding: "10px 14px",
                        background: "rgba(22, 163, 74, 0.12)",
                        border: "1px solid rgba(22, 163, 74, 0.3)",
                        borderRadius: "var(--radius-sm)",
                        color: "#16a34a",
                        fontSize: "0.88rem",
                      }}
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                      <span>{licenseImportSuccess}</span>
                    </div>
                  )}

                  {/* License Status Card */}
                  {isLicenseLoading ? (
                    <div style={{ padding: 24, textAlign: "center", color: "var(--text-muted)" }}>
                      Loading license information...
                    </div>
                  ) : licenseData ? (
                    <div
                      style={{
                        background: "var(--bg-secondary)",
                        border: "1px solid var(--border-color)",
                        borderRadius: "var(--radius-md)",
                        padding: "16px 20px",
                        display: "flex",
                        flexDirection: "column",
                        gap: 16,
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          borderBottom: "1px solid var(--border-color)",
                          paddingBottom: 12,
                        }}
                      >
                        <div>
                          <div style={{ fontSize: "1.1rem", fontWeight: 600, color: "var(--text-main)" }}>
                            {licenseData.client_name}
                          </div>
                          <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                            License ID: {licenseData.license_id}
                          </div>
                        </div>

                        <div>
                          <span
                            className={`role-pill ${
                              licenseData.status === "ACTIVE"
                                ? "role-pill-admin"
                                : licenseData.status === "TRIAL"
                                ? "role-pill-pharmacist"
                                : licenseData.status === "GRACE_PERIOD"
                                ? "role-pill-cashier"
                                : licenseData.status === "UNLICENSED_COMMUNITY"
                                ? "role-pill-pharmacist"
                                : "role-pill-cashier"
                            }`}
                            style={{
                              fontSize: "0.8rem",
                              padding: "4px 10px",
                              backgroundColor:
                                licenseData.status === "TRIAL"
                                  ? "#e0f2fe"
                                  : licenseData.status === "GRACE_PERIOD"
                                  ? "#fef3c7"
                                  : undefined,
                              color:
                                licenseData.status === "TRIAL"
                                  ? "#0369a1"
                                  : licenseData.status === "GRACE_PERIOD"
                                  ? "#b45309"
                                  : undefined,
                              border:
                                licenseData.status === "TRIAL"
                                  ? "1px solid #bae6fd"
                                  : licenseData.status === "GRACE_PERIOD"
                                  ? "1px solid #fde68a"
                                  : undefined,
                            }}
                          >
                            {licenseData.status === "TRIAL"
                              ? "EVALUATION TRIAL"
                              : licenseData.status === "GRACE_PERIOD"
                              ? "GRACE PERIOD"
                              : licenseData.status.replace(/_/g, " ")}
                          </span>
                        </div>
                      </div>

                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                          gap: 14,
                        }}
                      >
                        <div>
                          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase" }}>
                            Allowed Terminals
                          </div>
                          <div style={{ fontSize: "1.05rem", fontWeight: 600, color: "var(--accent-primary)" }}>
                            {licenseData.terminal_count} Counter Terminals
                          </div>
                        </div>

                        <div>
                          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase" }}>
                            Edition
                          </div>
                          <div style={{ fontSize: "0.95rem", fontWeight: 500, color: "var(--text-main)" }}>
                            {licenseData.edition}
                          </div>
                        </div>

                        <div>
                          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase" }}>
                            Activation Date
                          </div>
                          <div style={{ fontSize: "0.95rem", color: "var(--text-main)" }}>
                            {licenseData.activation_date}
                          </div>
                        </div>

                        <div>
                          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase" }}>
                            Expiry Date
                          </div>
                          <div
                            style={{
                              fontSize: "0.95rem",
                              color: licenseData.expiry_date ? "var(--text-main)" : "var(--accent-primary)",
                            }}
                          >
                            {licenseData.expiry_date || "Perpetual (No Expiry)"}
                          </div>
                        </div>

                        {licenseData.remaining_days !== undefined && licenseData.remaining_days !== null && (
                          <div>
                            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase" }}>
                              {licenseData.status === "TRIAL" ? "Trial Days Left" : "Remaining Days"}
                            </div>
                            <div
                              style={{
                                fontSize: "1.05rem",
                                fontWeight: 700,
                                color:
                                  licenseData.remaining_days <= 3
                                    ? "var(--accent-danger, #dc2626)"
                                    : licenseData.remaining_days <= 7
                                    ? "#d97706"
                                    : "var(--accent-success, #16a34a)",
                              }}
                            >
                              {licenseData.remaining_days} {licenseData.remaining_days === 1 ? "Day" : "Days"}
                              {licenseData.grace_period_active ? " (Grace Period)" : ""}
                            </div>
                          </div>
                        )}
                      </div>

                      <div
                        style={{
                          fontSize: "0.82rem",
                          color: "var(--text-muted)",
                          background: "rgba(0,0,0,0.06)",
                          padding: "8px 12px",
                          borderRadius: "var(--radius-sm)",
                        }}
                      >
                        <strong>Cryptographic Note:</strong> {licenseData.message}
                      </div>
                    </div>
                  ) : (
                    <div style={{ padding: 20, textAlign: "center", color: "var(--text-muted)" }}>
                      No active license loaded. Click below to import a license file.
                    </div>
                  )}

                  {/* Import New License Card */}
                  <div
                    style={{
                      border: "1px dashed var(--border-color)",
                      borderRadius: "var(--radius-md)",
                      padding: "18px 20px",
                      display: "flex",
                      flexDirection: "column",
                      gap: 12,
                    }}
                  >
                    <div>
                      <h4 style={{ fontSize: "0.95rem", fontWeight: 600, color: "var(--text-main)", marginBottom: 4 }}>
                        Import Client License File (.json)
                      </h4>
                      <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                        Select the signed license file (<code style={{ fontFamily: "var(--font-mono)" }}>LIC-CLIENT-XXX.json</code>) supplied by the publisher.
                      </p>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                      <label
                        className="btn btn-primary btn-sm"
                        style={{ cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 6 }}
                      >
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                          <polyline points="17 8 12 3 7 8" />
                          <line x1="12" y1="3" x2="12" y2="15" />
                        </svg>
                        <span>Select License File (.json)</span>
                        <input
                          type="file"
                          accept=".json,application/json"
                          onChange={handleLicenseFileUpload}
                          style={{ display: "none" }}
                        />
                      </label>

                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={fetchLicense}
                        title="Reload license status from daemon"
                      >
                        Refresh Status
                      </button>

                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => setShowContactAdminModal(true)}
                        title="Open support channels and renewal request form"
                        style={{ background: "rgba(56, 189, 248, 0.1)", borderColor: "#38bdf8", color: "#38bdf8" }}
                      >
                        Contact Vendor & Renew
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </main>
          </div>

          {/* Footer Controls */}
          <div className="modal-footer" style={{ justifyContent: "space-between" }}>
            <div>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setShowResetConfirm(true)}
                title="Reset all settings to default values"
              >
                Reset to Defaults
              </button>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              {saveSuccessMsg && (
                <div className="settings-toast">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  <span>{saveSuccessMsg}</span>
                </div>
              )}

              <button type="button" className="btn btn-secondary btn-sm" onClick={onClose}>
                Cancel [Esc]
              </button>

              <button type="button" className="btn btn-primary btn-sm" onClick={handleApplyChanges}>
                Apply Changes
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Confirmation Modal: Disabling a module */}
      {moduleToDisable && (
        <ConfirmModal
          isOpen={true}
          title="Disable Module"
          message={`Are you sure you want to disable "${moduleToDisable.label}"? It will be hidden from the navigation bar and keyboard shortcuts. No existing records will be deleted.`}
          confirmLabel="Disable Module"
          confirmVariant="warning"
          onConfirm={confirmDisableModule}
          onCancel={() => setModuleToDisable(null)}
        />
      )}

      {/* Confirmation Modal: Reset to defaults */}
      {showResetConfirm && (
        <ConfirmModal
          isOpen={true}
          title="Reset to Defaults"
          message="Are you sure you want to reset all settings to system defaults? This will restore the default dark theme, re-enable all optional modules, and restore standard POS preferences."
          confirmLabel="Reset All Settings"
          confirmVariant="danger"
          onConfirm={handleConfirmReset}
          onCancel={() => setShowResetConfirm(false)}
        />
      )}

      {/* Vendor Support & License Renewal Modal */}
      <ContactAdminModal
        isOpen={showContactAdminModal}
        onClose={() => setShowContactAdminModal(false)}
        licenseInfo={licenseData}
        onLicenseUpdated={(updated) => {
          setLicenseData(updated);
          setLicenseImportSuccess(`License updated to ${updated.edition} (Expires: ${updated.expiry_date || 'Perpetual'}).`);
        }}
      />
    </>
  );
};
