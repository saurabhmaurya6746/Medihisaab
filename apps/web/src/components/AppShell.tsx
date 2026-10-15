import React, { useState, useEffect, useRef } from "react";
import { useAuth } from "../context/AuthContext";
import { useSettings } from "../context/SettingsContext";
import { SettingsModal } from "./SettingsModal";
import { HealthIndicator } from "./HealthIndicator";
import { PinSwitchModal } from "./PinSwitchModal";
import { MedicineMasterView } from "./MedicineMasterView";
import { SupplierMasterView } from "./SupplierMasterView";
import { CustomerMasterView } from "./CustomerMasterView";
import { PurchaseInwardingView } from "./PurchaseInwardingView";
import { BillingView } from "./pos/BillingView";
import { InventoryView } from "./InventoryView";
import { StockAuditView } from "./StockAuditView";
import { CustomerKhataView } from "./CustomerKhataView";
import { SalesReturnView } from "./SalesReturnView";
import { PurchaseReturnView } from "./PurchaseReturnView";
import { WastageRegisterView } from "./WastageRegisterView";
import { AdminReportsView } from "./AdminReportsView";
import { ShortcutsHelpModal } from "./ShortcutsHelpModal";
import { ContactAdminModal } from "./ContactAdminModal";
import { getLicenseStatus, LicenseStatusInfo } from "../api/system";
import { MEDIHISAAB_ICON_BASE64 } from "../assets/brand";

type ActiveTab =
  | "billing"
  | "medicines"
  | "suppliers"
  | "purchases"
  | "customers"
  | "inventory"
  | "stock_audit"
  | "khata"
  | "returns_sales"
  | "returns_purchases"
  | "wastage"
  | "reports";

const MORE_TABS: ActiveTab[] = [
  "khata",
  "stock_audit",
  "returns_sales",
  "returns_purchases",
  "wastage",
];

function formatLicenseDate(value: string): string {
  const parsed = new Date(`${value}T00:00:00`);
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

function getLicenseBadge(license: LicenseStatusInfo): { badge: string; tooltip: string } {
  if (license.status === "UNLICENSED_COMMUNITY") {
    return {
      badge: "Community Edition",
      tooltip: "MediHisaab Community Edition · Basic offline POS",
    };
  }

  const isTrial =
    license.status === "TRIAL" ||
    ["TRIAL", "TRIALING", "EVALUATION"].includes((license.edition || "").toUpperCase());

  const daysLeft = license.remaining_days;
  const remainingStr =
    daysLeft !== null && daysLeft !== undefined
      ? `${daysLeft} day${daysLeft === 1 ? "" : "s"} left`
      : null;

  if (license.status === "EXPIRED") {
    return {
      badge: isTrial ? "Trial Expired" : "License Expired",
      tooltip: `Expired on ${license.expiry_date ? formatLicenseDate(license.expiry_date) : "N/A"}. Click to contact admin and renew.`,
    };
  }

  if (license.status === "GRACE_PERIOD" || license.grace_period_active) {
    return {
      badge: `Grace Period${remainingStr ? ` · ${remainingStr}` : ""}`,
      tooltip: `License expired on ${license.expiry_date ? formatLicenseDate(license.expiry_date) : "N/A"}. Running in grace period.`,
    };
  }

  if (isTrial) {
    return {
      badge: remainingStr ? `Free Trial · ${remainingStr}` : "Free Trial",
      tooltip: `Trial started on ${formatLicenseDate(license.activation_date)} and expires on ${license.expiry_date ? formatLicenseDate(license.expiry_date) : "N/A"}.`,
    };
  }

  if (!license.expiry_date) {
    return {
      badge: `${license.edition || "Commercial"} · Perpetual`,
      tooltip: "Commercial license with perpetual offline rights.",
    };
  }

  return {
    badge: remainingStr ? `Active · ${remainingStr}` : "Active License",
    tooltip: `Valid until ${formatLicenseDate(license.expiry_date)}.`,
  };
}

export const AppShell: React.FC = () => {
  const { user, storeName, performLogout } = useAuth();
  const { isModuleEnabled, settings } = useSettings();
  const [activeTab, setActiveTab] = useState<ActiveTab>("billing");
  const [showPinSwitchModal, setShowPinSwitchModal] = useState<boolean>(false);
  const [showSettingsModal, setShowSettingsModal] = useState<boolean>(false);
  const [showShortcutsModal, setShowShortcutsModal] = useState<boolean>(false);
  const [showContactAdminModal, setShowContactAdminModal] = useState<boolean>(false);
  const [isMoreOpen, setIsMoreOpen] = useState<boolean>(false);
  const [isProfileMenuOpen, setIsProfileMenuOpen] = useState<boolean>(false);
  const [currentTime, setCurrentTime] = useState<string>("");
  const [licenseInfo, setLicenseInfo] = useState<LicenseStatusInfo | null>(null);
  const [licenseStatusUnavailable, setLicenseStatusUnavailable] = useState(false);

  const moreDropdownRef = useRef<HTMLDivElement>(null);
  const profileDropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getLicenseStatus()
      .then((status) => {
        setLicenseInfo(status);
        setLicenseStatusUnavailable(false);
      })
      .catch(() => setLicenseStatusUnavailable(true));
  }, [showSettingsModal]);

  // Clock updates every second
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setCurrentTime(
        now.toLocaleDateString("en-IN", {
          day: "2-digit",
          month: "short",
          year: "numeric",
        }) +
          " " +
          now.toLocaleTimeString("en-IN", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
            hour12: true,
          })
      );
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  // Close "More" and Profile dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        moreDropdownRef.current &&
        !moreDropdownRef.current.contains(e.target as Node)
      ) {
        setIsMoreOpen(false);
      }
      if (
        profileDropdownRef.current &&
        !profileDropdownRef.current.contains(e.target as Node)
      ) {
        setIsProfileMenuOpen(false);
      }
    };
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isProfileMenuOpen) {
        setIsProfileMenuOpen(false);
        profileDropdownRef.current
          ?.querySelector<HTMLButtonElement>("button")
          ?.focus();
      }
    };
    if (isMoreOpen || isProfileMenuOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    if (isProfileMenuOpen) {
      document.addEventListener("keydown", handleEscape);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [isMoreOpen, isProfileMenuOpen]);

  // Automatically switch tab away if the active module gets disabled
  useEffect(() => {
    if (activeTab === "billing") return;
    const tabToModuleMap: Record<Exclude<ActiveTab, "billing">, keyof typeof settings.modules> = {
      medicines: "medicines",
      suppliers: "suppliers",
      purchases: "purchases",
      customers: "customers",
      inventory: "inventory",
      stock_audit: "stockAudit",
      khata: "khata",
      returns_sales: "salesReturns",
      returns_purchases: "purchaseReturns",
      wastage: "wastage",
      reports: "reports",
    };
    const modKey = tabToModuleMap[activeTab as Exclude<ActiveTab, "billing">];
    if (modKey && !isModuleEnabled(modKey)) {
      setActiveTab("billing");
    }
  }, [activeTab, isModuleEnabled, settings.modules]);

  // Window-level hotkey navigation (F1-F9, F11, F10, Ctrl+Shift+R/P/W)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "F1") {
        e.preventDefault();
        setActiveTab("billing");
      } else if (e.key === "F2" && activeTab !== "billing") {
        if (isModuleEnabled("medicines")) {
          e.preventDefault();
          setActiveTab("medicines");
        }
      } else if (e.key === "F3" && activeTab !== "billing") {
        if (isModuleEnabled("suppliers")) {
          e.preventDefault();
          setActiveTab("suppliers");
        }
      } else if (e.key === "F4" && activeTab !== "billing") {
        if (isModuleEnabled("khata")) {
          e.preventDefault();
          setActiveTab("khata");
        }
      } else if (e.key === "F5" && activeTab !== "billing") {
        if (isModuleEnabled("customers")) {
          e.preventDefault();
          setActiveTab("customers");
        }
      } else if (e.key === "F6" && activeTab !== "billing") {
        if (isModuleEnabled("purchases")) {
          e.preventDefault();
          setActiveTab("purchases");
        }
      } else if (e.key === "F7" && activeTab !== "billing") {
        if (isModuleEnabled("inventory")) {
          e.preventDefault();
          setActiveTab("inventory");
        }
      } else if (e.key === "F8" && activeTab !== "billing") {
        if (isModuleEnabled("stockAudit")) {
          e.preventDefault();
          setActiveTab("stock_audit");
        }
      } else if (e.key === "F9" && activeTab !== "billing") {
        if (user?.role === "ADMIN" && isModuleEnabled("reports")) {
          e.preventDefault();
          setActiveTab("reports");
        }
      } else if (e.key === "F11") {
        e.preventDefault();
        setShowPinSwitchModal(true);
      } else if (e.key === "F12") {
        e.preventDefault();
        setShowShortcutsModal((prev) => !prev);
      } else if (e.ctrlKey && e.shiftKey && (e.key === "R" || e.key === "r")) {
        if (isModuleEnabled("salesReturns")) {
          e.preventDefault();
          setActiveTab("returns_sales");
        }
      } else if (e.ctrlKey && e.shiftKey && (e.key === "P" || e.key === "p")) {
        if (isModuleEnabled("purchaseReturns")) {
          e.preventDefault();
          setActiveTab("returns_purchases");
        }
      } else if (e.ctrlKey && e.shiftKey && (e.key === "W" || e.key === "w")) {
        if (isModuleEnabled("wastage")) {
          e.preventDefault();
          setActiveTab("wastage");
        }
      } else if (e.key === "F10") {
        e.preventDefault();
        if (window.confirm("Are you sure you want to log out of this terminal session?")) {
          performLogout();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [performLogout, activeTab, isModuleEnabled, user?.role]);

  const roleClass =
    user?.role === "ADMIN"
      ? "role-pill-admin"
      : user?.role === "PHARMACIST"
      ? "role-pill-pharmacist"
      : "role-pill-cashier";

  // Check which "More" items are enabled
  const moreItems = [
    {
      tab: "khata" as ActiveTab,
      label: "Customer Khata",
      enabled: isModuleEnabled("khata"),
      shortcut: "F4",
    },
    {
      tab: "stock_audit" as ActiveTab,
      label: "Stock Audit",
      enabled: isModuleEnabled("stockAudit"),
      shortcut: "F8",
    },
    {
      tab: "returns_sales" as ActiveTab,
      label: "Sales Returns",
      enabled: isModuleEnabled("salesReturns"),
      shortcut: "Ctrl+Shift+R",
    },
    {
      tab: "returns_purchases" as ActiveTab,
      label: "Purchase Returns",
      enabled: isModuleEnabled("purchaseReturns"),
      shortcut: "Ctrl+Shift+P",
    },
    {
      tab: "wastage" as ActiveTab,
      label: "Wastage",
      enabled: isModuleEnabled("wastage"),
      shortcut: "Ctrl+Shift+W",
    },
  ].filter((item) => item.enabled);

  const isMoreTabActive = MORE_TABS.includes(activeTab);

  const sanitizedStoreName = React.useMemo(() => {
    if (!storeName) return "MediHisaab Pharmacy";
    const lower = storeName.toLowerCase().trim();
    if (lower.includes("trial") || lower === "medihisaab trial") {
      if (licenseInfo?.client_name && !licenseInfo.client_name.toLowerCase().includes("trial")) {
        return licenseInfo.client_name;
      }
      return "MediHisaab Pharmacy";
    }
    return storeName;
  }, [storeName, licenseInfo]);

  const licenseBadgeInfo = licenseInfo ? getLicenseBadge(licenseInfo) : null;

  return (
    <div className="app-container">
      {/* 1. Top Header Bar */}
      <header className="pos-header">
        <div className="pos-brand-section">
          <img
            src={MEDIHISAAB_ICON_BASE64}
            alt="MediHisaab Logo"
            className="pos-logo-img"
            style={{ width: "36px", height: "36px", borderRadius: "8px", objectFit: "contain" }}
          />
          <div style={{ display: "flex", flexDirection: "column" }}>
            <div className="pos-store-title">
              <span>{sanitizedStoreName}</span>
              <span className="pos-offline-pill">MediHisaab • Offline-First POS</span>
            </div>
          </div>
        </div>

        <div className="pos-header-actions" style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {/* Dynamic License Badge */}
          {(licenseInfo || licenseStatusUnavailable) && (
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => setShowContactAdminModal(true)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                fontSize: "0.76rem",
                fontWeight: 600,
                padding: "4px 10px",
                borderRadius: "16px",
                border: "1px solid",
                background: !licenseInfo
                  ? "rgba(148, 163, 184, 0.12)"
                  : licenseInfo.status === "ACTIVE"
                  ? "rgba(16, 185, 129, 0.15)"
                  : licenseInfo.status === "TRIAL"
                  ? "rgba(59, 130, 246, 0.15)"
                  : licenseInfo.status === "GRACE_PERIOD"
                  ? "rgba(245, 158, 11, 0.15)"
                  : "rgba(239, 68, 68, 0.15)",
                borderColor: !licenseInfo
                  ? "#64748b"
                  : licenseInfo.status === "ACTIVE"
                  ? "#10b981"
                  : licenseInfo.status === "TRIAL"
                  ? "#3b82f6"
                  : licenseInfo.status === "GRACE_PERIOD"
                  ? "#f59e0b"
                  : "#ef4444",
                color: !licenseInfo
                  ? "#cbd5e1"
                  : licenseInfo.status === "ACTIVE"
                  ? "#34d399"
                  : licenseInfo.status === "TRIAL"
                  ? "#60a5fa"
                  : licenseInfo.status === "GRACE_PERIOD"
                  ? "#fbbf24"
                  : "#f87171",
                cursor: "pointer",
              }}
              title={
                licenseBadgeInfo
                  ? `${licenseBadgeInfo.tooltip}\nClick to view license status, contact admin, or submit renewal`
                  : "License details could not be loaded. Click to contact support or import a license file."
              }
            >
              <span style={{ width: 6, height: 6, flex: "0 0 6px", borderRadius: "50%", backgroundColor: "currentColor" }} />
              <span>{licenseBadgeInfo ? licenseBadgeInfo.badge : "License"}</span>
            </button>
          )}

          {/* System Online / Health Indicator */}
          <HealthIndicator />

          {/* User Profile Menu Dropdown */}
          {user && (
            <div style={{ position: "relative" }} ref={profileDropdownRef}>
              <button
                type="button"
                className="operator-badge-container"
                onClick={() => setIsProfileMenuOpen(!isProfileMenuOpen)}
                aria-haspopup="menu"
                aria-expanded={isProfileMenuOpen}
                style={{
                  cursor: "pointer",
                  border: "1px solid var(--border-color)",
                  background: "var(--bg-secondary)",
                  padding: "4px 10px",
                  borderRadius: "var(--radius-md)",
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                }}
                title="Open Operator & System Menu"
              >
                <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", lineHeight: 1.2 }}>
                  <span className="operator-name">{user.full_name}</span>
                  <span style={{ fontSize: "0.7rem", color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
                    @{user.username}
                  </span>
                </div>
                <span className={`role-pill ${roleClass}`} style={{ fontSize: "0.72rem", padding: "2px 6px" }}>
                  {user.role}
                </span>
                <svg
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  style={{
                    opacity: 0.7,
                    transform: isProfileMenuOpen ? "rotate(180deg)" : "rotate(0deg)",
                    transition: "transform 0.15s ease",
                  }}
                >
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </button>

              {isProfileMenuOpen && (
                <div
                    role="menu"
                  style={{
                    position: "absolute",
                    top: "calc(100% + 6px)",
                    right: 0,
                    width: "min(275px, calc(100vw - 24px))",
                    maxHeight: "calc(100vh - 84px)",
                    backgroundColor: "var(--dropdown-bg, #1e293b)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "var(--radius-md)",
                    boxShadow: "var(--dropdown-shadow, 0 10px 25px rgba(0,0,0,0.6))",
                    zIndex: 2000,
                    overflowX: "hidden",
                    overflowY: "auto",
                  }}
                >
                  <div style={{ padding: "12px 14px", borderBottom: "1px solid var(--border-color)", background: "var(--bg-secondary)" }}>
                    <div style={{ fontWeight: 600, color: "var(--text-main)", fontSize: "0.92rem" }}>
                      {user.full_name}
                    </div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      @{user.username} · {user.role}
                    </div>
                    <div style={{ fontSize: "0.72rem", color: "var(--accent-primary)", marginTop: 2 }}>
                      {sanitizedStoreName}
                    </div>
                  </div>

                  <div style={{ padding: 6, display: "flex", flexDirection: "column", gap: 4 }}>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      style={{ justifyContent: "flex-start", width: "100%", padding: "7px 10px", fontSize: "0.82rem" }}
                      onClick={() => {
                        setIsProfileMenuOpen(false);
                        setShowPinSwitchModal(true);
                      }}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 8 }}>
                        <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
                        <circle cx="9" cy="7" r="4" />
                        <path d="M19 8v6M22 11h-6" />
                      </svg>
                      <span>Switch User (F11)</span>
                    </button>

                    {user.role === "ADMIN" && (
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        style={{ justifyContent: "flex-start", width: "100%", padding: "7px 10px", fontSize: "0.82rem" }}
                        onClick={() => {
                          setIsProfileMenuOpen(false);
                          setShowSettingsModal(true);
                        }}
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 8 }}>
                          <circle cx="12" cy="12" r="3" />
                          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
                        </svg>
                        <span>Settings & Backups</span>
                      </button>
                    )}

                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      style={{ justifyContent: "flex-start", width: "100%", padding: "7px 10px", fontSize: "0.82rem" }}
                      onClick={() => {
                        setIsProfileMenuOpen(false);
                        setShowShortcutsModal(true);
                      }}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 8 }}>
                        <rect x="2" y="4" width="20" height="16" rx="2" />
                        <path d="M6 8h.01M10 8h.01M14 8h.01M18 8h.01M6 12h.01M10 12h.01M14 12h.01M18 12h.01M7 16h10" />
                      </svg>
                      <span>Shortcuts Guide (F12)</span>
                    </button>

                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      style={{ justifyContent: "flex-start", width: "100%", padding: "7px 10px", fontSize: "0.82rem" }}
                      onClick={() => {
                        setIsProfileMenuOpen(false);
                        setShowContactAdminModal(true);
                      }}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 8 }}>
                        <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                        <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                      </svg>
                      <span>License Details & Renew</span>
                    </button>

                    <div style={{ height: 1, background: "var(--border-color)", margin: "4px 0" }} />

                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      style={{
                        justifyContent: "flex-start",
                        width: "100%",
                        padding: "8px 10px",
                        fontSize: "0.82rem",
                        color: "var(--accent-danger, #ef4444)",
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "flex-start",
                      }}
                      onClick={() => {
                        setIsProfileMenuOpen(false);
                        if (window.confirm("Are you sure you want to log out of this operator session?")) {
                          performLogout();
                        }
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", width: "100%" }}>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 8 }}>
                          <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                          <polyline points="16 17 21 12 16 7" />
                          <line x1="21" y1="12" x2="9" y2="12" />
                        </svg>
                        <span style={{ fontWeight: 600 }}>Logout (F10)</span>
                      </div>
                      <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: 2, paddingLeft: 22 }}>
                        Ends session. Background daemon keeps running.
                      </span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </header>
 
      {/* License Status Banner (Clock Anomaly / Grace Period / Expiry / Trial Expiring Notice) */}
      {licenseInfo && licenseInfo.status === "CLOCK_ANOMALY" && (
        <div style={{ background: "#dc2626", color: "#fff", padding: "8px 16px", fontSize: "0.85rem", fontWeight: 600, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>⚠️ {licenseInfo.message}</span>
          <button type="button" className="btn btn-secondary btn-sm" style={{ background: "#fff", color: "#dc2626", fontWeight: 700 }} onClick={() => setShowContactAdminModal(true)}>
            Contact Vendor Support
          </button>
        </div>
      )}
      {licenseInfo && licenseInfo.status === "EXPIRED" && (
        <div style={{ background: "#dc2626", color: "#fff", padding: "8px 16px", fontSize: "0.85rem", fontWeight: 600, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>⚠️ {licenseInfo.message || `License Expired (${licenseInfo.expiry_date}). Counter billing is restricted. Historical sales, ledgers, medicines, and reports remain fully accessible.`}</span>
          <button type="button" className="btn btn-secondary btn-sm" style={{ background: "#fff", color: "#dc2626", fontWeight: 700 }} onClick={() => setShowContactAdminModal(true)}>
            Contact Admin / Renew License
          </button>
        </div>
      )}
      {licenseInfo && (licenseInfo.status === "GRACE_PERIOD" || licenseInfo.grace_period_active) && (
        <div style={{ background: "#d97706", color: "#fff", padding: "8px 16px", fontSize: "0.85rem", fontWeight: 600, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>⏳ {licenseInfo.message || `License Expired. In grace period (${licenseInfo.remaining_days} days remaining). Please renew subscription to prevent disruption.`}</span>
          <button type="button" className="btn btn-secondary btn-sm" style={{ background: "#fff", color: "#d97706", fontWeight: 700 }} onClick={() => setShowContactAdminModal(true)}>
            Contact Admin / Renew
          </button>
        </div>
      )}
      {licenseInfo && licenseInfo.status === "TRIAL" && licenseInfo.remaining_days !== null && licenseInfo.remaining_days !== undefined && licenseInfo.remaining_days <= 5 && (
        <div style={{ background: "#2563eb", color: "#fff", padding: "8px 16px", fontSize: "0.85rem", fontWeight: 600, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>ℹ️ {licenseInfo.message || `Trial: ${licenseInfo.remaining_days} days remaining. Please renew to continue uninterrupted billing.`}</span>
          <button type="button" className="btn btn-secondary btn-sm" style={{ background: "#fff", color: "#2563eb", fontWeight: 700 }} onClick={() => setShowContactAdminModal(true)}>
            Contact Admin / Renew
          </button>
        </div>
      )}

      {/* 2. Main Navigation Strip */}
      <nav className="pos-nav-strip">
        <button
          className={`nav-tab-btn ${activeTab === "billing" ? "active" : ""}`}
          onClick={() => setActiveTab("billing")}
          title="Billing (F1)"
        >
          <span>Billing</span>
        </button>

        {isModuleEnabled("medicines") && (
          <button
            className={`nav-tab-btn ${activeTab === "medicines" ? "active" : ""}`}
            onClick={() => setActiveTab("medicines")}
            title="Medicines (F2)"
          >
            <span>Medicines</span>
          </button>
        )}

        {isModuleEnabled("inventory") && (
          <button
            className={`nav-tab-btn ${activeTab === "inventory" ? "active" : ""}`}
            onClick={() => setActiveTab("inventory")}
            title="Inventory (F7)"
          >
            <span>Inventory</span>
          </button>
        )}

        {isModuleEnabled("customers") && (
          <button
            className={`nav-tab-btn ${activeTab === "customers" ? "active" : ""}`}
            onClick={() => setActiveTab("customers")}
            title="Customers (F5)"
          >
            <span>Customers</span>
          </button>
        )}

        {isModuleEnabled("suppliers") && (
          <button
            className={`nav-tab-btn ${activeTab === "suppliers" ? "active" : ""}`}
            onClick={() => setActiveTab("suppliers")}
            title="Suppliers (F3)"
          >
            <span>Suppliers</span>
          </button>
        )}

        {isModuleEnabled("purchases") && (
          <button
            className={`nav-tab-btn ${activeTab === "purchases" ? "active" : ""}`}
            onClick={() => setActiveTab("purchases")}
            title="Purchases (F6)"
          >
            <span>Purchases</span>
          </button>
        )}

        {user?.role === "ADMIN" && isModuleEnabled("reports") && (
          <button
            className={`nav-tab-btn ${activeTab === "reports" ? "active" : ""}`}
            onClick={() => setActiveTab("reports")}
            title="Reports (F9)"
          >
            <span>Reports</span>
          </button>
        )}

        {/* Secondary Modules in "More" Menu */}
        {moreItems.length > 0 && (
          <div className="nav-more-container" ref={moreDropdownRef}>
            <button
              type="button"
              className={`nav-tab-btn nav-more-btn ${isMoreTabActive ? "active" : ""}`}
              onClick={() => setIsMoreOpen((prev) => !prev)}
              aria-expanded={isMoreOpen}
              title="More modules"
            >
              <span>
                {isMoreTabActive
                  ? moreItems.find((i) => i.tab === activeTab)?.label || "More"
                  : "More"}
              </span>
              <svg
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                style={{
                  transform: isMoreOpen ? "rotate(180deg)" : "rotate(0deg)",
                  transition: "transform 0.15s ease",
                }}
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>

            {isMoreOpen && (
              <div className="nav-more-menu" role="menu">
                {moreItems.map((item) => (
                  <button
                    key={item.tab}
                    type="button"
                    role="menuitem"
                    className={`nav-more-item ${activeTab === item.tab ? "active" : ""}`}
                    onClick={() => {
                      setActiveTab(item.tab);
                      setIsMoreOpen(false);
                    }}
                    title={`${item.label} (${item.shortcut})`}
                  >
                    <span>{item.label}</span>
                    <span className="nav-more-shortcut">{item.shortcut}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </nav>

      {/* 3. Main Workspace Area */}
      <main className="pos-main-workspace">
        {activeTab === "billing" && <BillingView />}

        {activeTab === "medicines" && isModuleEnabled("medicines") && <MedicineMasterView />}

        {activeTab === "inventory" && isModuleEnabled("inventory") && <InventoryView />}

        {activeTab === "customers" && isModuleEnabled("customers") && <CustomerMasterView />}

        {activeTab === "suppliers" && isModuleEnabled("suppliers") && <SupplierMasterView />}

        {activeTab === "purchases" && isModuleEnabled("purchases") && <PurchaseInwardingView />}

        {activeTab === "khata" && isModuleEnabled("khata") && <CustomerKhataView />}

        {activeTab === "stock_audit" && isModuleEnabled("stockAudit") && <StockAuditView />}

        {activeTab === "returns_sales" && isModuleEnabled("salesReturns") && <SalesReturnView />}

        {activeTab === "returns_purchases" && isModuleEnabled("purchaseReturns") && <PurchaseReturnView />}

        {activeTab === "wastage" && isModuleEnabled("wastage") && <WastageRegisterView />}

        {activeTab === "reports" && isModuleEnabled("reports") && <AdminReportsView />}
      </main>

      {/* 4. Bottom Clean Status & Telemetry Bar */}
      <footer className="pos-status-bar">
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <span style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
            Station: <strong style={{ color: "var(--text-main)" }}>Counter 1</strong>
          </span>
          <span style={{ color: "var(--border-subtle)" }}>•</span>
          <span style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
            Mode: <span style={{ color: "var(--accent-success)", fontWeight: 600 }}>Offline POS</span>
          </span>
          <span style={{ color: "var(--border-subtle)" }}>•</span>
          <span style={{ fontSize: "0.82rem", color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
            v1.0.0
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <button
            type="button"
            className="btn btn-ghost btn-xs"
            onClick={() => setShowShortcutsModal(true)}
            style={{ fontSize: "0.8rem", color: "var(--accent-primary)", padding: "2px 8px" }}
            title="View all keyboard shortcuts [F12]"
            aria-label="View keyboard shortcuts guide"
          >
            <span>Shortcuts [F12]</span>
          </button>
          <span style={{ color: "var(--border-subtle)" }}>•</span>
          <span style={{ fontSize: "0.82rem", color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
            {currentTime}
          </span>
        </div>
      </footer>

      {/* Fast Cashier PIN Switch Modal */}
      <PinSwitchModal
        isOpen={showPinSwitchModal}
        onClose={() => setShowPinSwitchModal(false)}
        title="Switch Operator"
      />

      {/* Admin Settings Modal */}
      <SettingsModal
        isOpen={showSettingsModal}
        onClose={() => setShowSettingsModal(false)}
      />

      {/* Keyboard Shortcuts Help Modal */}
      <ShortcutsHelpModal
        isOpen={showShortcutsModal}
        onClose={() => setShowShortcutsModal(false)}
      />

      {/* Vendor Support & License Renewal Modal */}
      <ContactAdminModal
        isOpen={showContactAdminModal}
        onClose={() => setShowContactAdminModal(false)}
        licenseInfo={licenseInfo}
        onLicenseUpdated={(newStatus) => setLicenseInfo(newStatus)}
      />
    </div>
  );
};
