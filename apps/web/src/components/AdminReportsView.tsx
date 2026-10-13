import React, { useState, useEffect, useCallback } from "react";
import { formatRupees } from "@pharmacy/api-contracts";
import type {
  ScheduleH1ReportResponse,
  Gstr1ReportResponse,
  Gstr2ReportResponse,
  SalesRegisterItem,
  PurchaseRegisterItem,
  DayBookCurrentResponse,
  DayBookSession,
  BackupManifest,
  BackupVerifyResult,
  RestorePreviewResponse,
  SystemDiscoveryResponse,
} from "@pharmacy/api-contracts";
import * as reportsApi from "../api/reports";
import * as systemApi from "../api/system";

type MainSection = "compliance" | "daybook" | "backups" | "system";
type ComplianceSubSection = "h1" | "gstr1" | "gstr2" | "sales" | "purchases";

export const AdminReportsView: React.FC = () => {
  const [activeSection, setActiveSection] = useState<MainSection>("compliance");
  const [complianceSub, setComplianceSub] = useState<ComplianceSubSection>("h1");

  // Date filters for compliance reports
  const [fromDate, setFromDate] = useState<string>("");
  const [toDate, setToDate] = useState<string>("");
  const [fiscalYear, setFiscalYear] = useState<string>("");

  // Loading & notification states
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // 1. Compliance reports data
  const [h1Report, setH1Report] = useState<ScheduleH1ReportResponse | null>(null);
  const [gstr1Report, setGstr1Report] = useState<Gstr1ReportResponse | null>(null);
  const [gstr2Report, setGstr2Report] = useState<Gstr2ReportResponse | null>(null);
  const [salesRegister, setSalesRegister] = useState<SalesRegisterItem[]>([]);
  const [purchaseRegister, setPurchaseRegister] = useState<PurchaseRegisterItem[]>([]);

  // 2. Day-Book data
  const [dayBookCurrent, setDayBookCurrent] = useState<DayBookCurrentResponse | null>(null);
  const [dayBookHistory, setDayBookHistory] = useState<DayBookSession[]>([]);
  const [floatInputRupees, setFloatInputRupees] = useState<string>("");
  const [actualCashRupees, setActualCashRupees] = useState<string>("");
  const [closeNotes, setCloseNotes] = useState<string>("");

  // 3. Backups data
  const [backupsList, setBackupsList] = useState<BackupManifest[]>([]);
  const [backupNotes, setBackupNotes] = useState<string>("");
  const [verifyResult, setVerifyResult] = useState<BackupVerifyResult | null>(null);
  const [restorePreview, setRestorePreview] = useState<RestorePreviewResponse | null>(null);
  const [isRestoreModalOpen, setIsRestoreModalOpen] = useState<boolean>(false);

  // 4. System & LAN configuration
  const [systemConfig, setSystemConfig] = useState<Record<string, string>>({});
  const [discoveryInfo, setDiscoveryInfo] = useState<SystemDiscoveryResponse | null>(null);
  const [serverMode, setServerMode] = useState<string>("STANDALONE");
  const [storeName, setStoreName] = useState<string>("");
  const [storeGstin, setStoreGstin] = useState<string>("");
  const [storeDl, setStoreDl] = useState<string>("");
  const [backupDir, setBackupDir] = useState<string>("");

  const clearAlerts = () => {
    setErrorMessage(null);
    setSuccessMessage(null);
  };

  // =========================================================================
  // SECTION 1: COMPLIANCE REPORTS
  // =========================================================================

  const loadComplianceReport = useCallback(async () => {
    setIsLoading(true);
    clearAlerts();
    try {
      const filters = {
        from_date: fromDate || undefined,
        to_date: toDate || undefined,
        fiscal_year: fiscalYear || undefined,
      };

      if (complianceSub === "h1") {
        const data = await reportsApi.getScheduleH1Report(filters);
        setH1Report(data);
      } else if (complianceSub === "gstr1") {
        const data = await reportsApi.getGstr1Report(filters);
        setGstr1Report(data);
      } else if (complianceSub === "gstr2") {
        const data = await reportsApi.getGstr2Report(filters);
        setGstr2Report(data);
      } else if (complianceSub === "sales") {
        const data = await reportsApi.getSalesRegister(filters);
        setSalesRegister(data);
      } else if (complianceSub === "purchases") {
        const data = await reportsApi.getPurchaseRegister(filters);
        setPurchaseRegister(data);
      }
    } catch (err: any) {
      setErrorMessage(err?.message || "Failed to load statutory report.");
    } finally {
      setIsLoading(false);
    }
  }, [complianceSub, fromDate, toDate, fiscalYear]);

  // =========================================================================
  // SECTION 2: DAY-BOOK CASH RECONCILIATION
  // =========================================================================

  const loadDayBook = useCallback(async () => {
    setIsLoading(true);
    clearAlerts();
    try {
      const [current, history] = await Promise.all([
        reportsApi.getCurrentDayBook(),
        reportsApi.getDayBookHistory(30),
      ]);
      setDayBookCurrent(current);
      setDayBookHistory(history);
      setFloatInputRupees(current?.session ? (current.session.opening_float_paise / 100).toFixed(2) : "0.00");
    } catch (err: any) {
      setErrorMessage(err?.message || "Failed to load cash day-book.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleSetOpeningFloat = async () => {
    clearAlerts();
    const rupees = parseFloat(floatInputRupees || "0");
    if (isNaN(rupees) || rupees < 0) {
      setErrorMessage("Opening float must be a valid non-negative amount.");
      return;
    }
    const paise = Math.round(rupees * 100);
    try {
      setIsLoading(true);
      await reportsApi.setDayBookOpeningFloat(paise);
      setSuccessMessage(`Opening float set to ₹${rupees.toFixed(2)}.`);
      await loadDayBook();
    } catch (err: any) {
      setErrorMessage(err?.message || "Failed to update opening float.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleCloseDayBook = async () => {
    clearAlerts();
    const rupees = parseFloat(actualCashRupees || "0");
    if (isNaN(rupees) || rupees < 0) {
      setErrorMessage("Please enter the physical drawer cash count.");
      return;
    }
    const paise = Math.round(rupees * 100);

    const expectedPaise = dayBookCurrent?.summary.expected_cash_paise ?? 0;
    const variancePaise = paise - expectedPaise;
    const varianceRupees = (variancePaise / 100).toFixed(2);

    const confirmMsg =
      `Confirm Cash Drawer Closure?\n\n` +
      `Expected Cash: ₹${(expectedPaise / 100).toFixed(2)}\n` +
      `Physical Count: ₹${rupees.toFixed(2)}\n` +
      `Variance: ₹${varianceRupees} ${variancePaise < 0 ? "(Shortage)" : variancePaise > 0 ? "(Excess)" : "(Balanced)"}\n\n` +
      `Once closed, today's cash book is sealed and immutable. Proceed?`;

    if (!window.confirm(confirmMsg)) return;

    try {
      setIsLoading(true);
      const res = await reportsApi.closeDayBook(paise, closeNotes);
      setSuccessMessage(`Day-book closed successfully! Status: ${res.status}.`);
      setActualCashRupees("");
      setCloseNotes("");
      await loadDayBook();
    } catch (err: any) {
      setErrorMessage(err?.message || "Failed to close day-book.");
    } finally {
      setIsLoading(false);
    }
  };

  // =========================================================================
  // SECTION 3: HOT BACKUPS & DISASTER RECOVERY
  // =========================================================================

  const loadBackups = useCallback(async () => {
    setIsLoading(true);
    clearAlerts();
    try {
      const data = await systemApi.listBackups();
      setBackupsList(data);
    } catch (err: any) {
      setErrorMessage(err?.message || "Failed to load backups ledger.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleCreateBackup = async () => {
    clearAlerts();
    try {
      setIsLoading(true);
      const res = await systemApi.createBackup({
        notes: backupNotes.trim() || undefined,
        backup_type: "MANUAL",
      });
      setSuccessMessage(`Hot backup archive created: ${res.filename} (${(res.file_size_bytes / 1024).toFixed(1)} KB)`);
      setBackupNotes("");
      await loadBackups();
    } catch (err: any) {
      setErrorMessage(err?.message || "Failed to create backup snapshot.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifyBackup = async (id: number) => {
    clearAlerts();
    try {
      setIsLoading(true);
      const res = await systemApi.verifyBackup(id);
      setVerifyResult(res);
      if (res.is_valid) {
        setSuccessMessage(`Backup #${id} verified: SHA-256 hash valid and SQLite integrity healthy.`);
      } else {
        setErrorMessage(`Backup #${id} verification failed: ${res.message}`);
      }
      await loadBackups();
    } catch (err: any) {
      setErrorMessage(err?.message || "Failed to verify backup archive.");
    } finally {
      setIsLoading(false);
    }
  };

  const handlePreviewRestoreFromId = async (backupId: number) => {
    clearAlerts();
    try {
      setIsLoading(true);
      const preview = await systemApi.previewRestore({ backupId });
      setRestorePreview(preview);
      setIsRestoreModalOpen(true);
    } catch (err: any) {
      setErrorMessage(err?.message || "Failed to preview backup archive for restoration.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileUploadForRestore = async (e: React.ChangeEvent<HTMLInputElement>) => {
    clearAlerts();
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setIsLoading(true);
      const preview = await systemApi.previewRestore({ file });
      setRestorePreview(preview);
      setIsRestoreModalOpen(true);
    } catch (err: any) {
      setErrorMessage(err?.message || "Failed to inspect uploaded backup file.");
    } finally {
      setIsLoading(false);
      e.target.value = "";
    }
  };

  const handleExecuteRestore = async () => {
    if (!restorePreview) return;
    clearAlerts();

    const warnMsg =
      `CRITICAL WARNING: DATABASE RESTORATION\n\n` +
      `You are about to restore database from archive: '${restorePreview.filename}'.\n` +
      `Current database data will be replaced with this backup state.\n` +
      `An automated safety backup will be created immediately before swapping.\n\n` +
      `Are you completely sure you want to restore?`;

    if (!window.confirm(warnMsg)) return;

    try {
      setIsLoading(true);
      const res = await systemApi.executeRestore(restorePreview.staging_token, true);
      setSuccessMessage(`Database restored successfully! Pre-restore safety backup: ${res.safety_backup_filename}`);
      setIsRestoreModalOpen(false);
      setRestorePreview(null);
      await loadBackups();
    } catch (err: any) {
      setErrorMessage(err?.message || "Database restoration failed.");
    } finally {
      setIsLoading(false);
    }
  };

  // =========================================================================
  // SECTION 4: SYSTEM & LAN CONFIGURATION
  // =========================================================================

  const loadSystemConfig = useCallback(async () => {
    setIsLoading(true);
    clearAlerts();
    try {
      const [configs, discovery] = await Promise.all([
        systemApi.getSystemConfig(),
        systemApi.getSystemDiscovery(),
      ]);
      setSystemConfig(configs);
      setDiscoveryInfo(discovery);
      setServerMode(configs["server_mode"] || "STANDALONE");
      setStoreName(configs["store_name"] || "Apex Health Pharmacy");
      setStoreGstin(configs["store_gstin"] || "");
      setStoreDl(configs["store_dl_number"] || "");
      setBackupDir(configs["backup_directory"] || "");
    } catch (err: any) {
      setErrorMessage(err?.message || "Failed to load system configuration.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleSaveSystemConfig = async () => {
    clearAlerts();
    try {
      setIsLoading(true);
      const updated = await systemApi.updateSystemConfig({
        server_mode: serverMode,
        store_name: storeName.trim(),
        store_gstin: storeGstin.trim().toUpperCase(),
        store_dl_number: storeDl.trim(),
        backup_directory: backupDir.trim(),
      });
      setSystemConfig(updated);
      setSuccessMessage("System configuration and store settings saved successfully.");
      const discovery = await systemApi.getSystemDiscovery();
      setDiscoveryInfo(discovery);
    } catch (err: any) {
      setErrorMessage(err?.message || "Failed to save system settings.");
    } finally {
      setIsLoading(false);
    }
  };

  // Load appropriate section data on tab switch
  useEffect(() => {
    if (activeSection === "compliance") {
      loadComplianceReport();
    } else if (activeSection === "daybook") {
      loadDayBook();
    } else if (activeSection === "backups") {
      loadBackups();
    } else if (activeSection === "system") {
      loadSystemConfig();
    }
  }, [activeSection, loadComplianceReport, loadDayBook, loadBackups, loadSystemConfig]);

  return (
    <div className="admin-reports-view" style={{ padding: "1.5rem", height: "100%", overflowY: "auto" }}>
      {/* Top Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
        <div>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 700, margin: 0 }}>Reports & Admin</h1>
          <p style={{ color: "var(--text-muted)", margin: "0.25rem 0 0", fontSize: "0.85rem" }}>
            Tax registers, drug compliance, cash reconciliation, and database backups
          </p>
        </div>
      </div>

      {/* Main Navigation Tabs */}
      <div style={{ display: "flex", gap: "0.5rem", borderBottom: "2px solid #334155", marginBottom: "1.5rem" }}>
        <button
          onClick={() => setActiveSection("compliance")}
          style={{
            padding: "0.75rem 1.25rem",
            background: activeSection === "compliance" ? "#1e293b" : "transparent",
            color: activeSection === "compliance" ? "#38bdf8" : "#94a3b8",
            border: "none",
            borderBottom: activeSection === "compliance" ? "3px solid #38bdf8" : "3px solid transparent",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Tax & Drug Reports
        </button>
        <button
          onClick={() => setActiveSection("daybook")}
          style={{
            padding: "0.75rem 1.25rem",
            background: activeSection === "daybook" ? "#1e293b" : "transparent",
            color: activeSection === "daybook" ? "#38bdf8" : "#94a3b8",
            border: "none",
            borderBottom: activeSection === "daybook" ? "3px solid #38bdf8" : "3px solid transparent",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Day-Book
        </button>
        <button
          onClick={() => setActiveSection("backups")}
          style={{
            padding: "0.75rem 1.25rem",
            background: activeSection === "backups" ? "#1e293b" : "transparent",
            color: activeSection === "backups" ? "#38bdf8" : "#94a3b8",
            border: "none",
            borderBottom: activeSection === "backups" ? "3px solid #38bdf8" : "3px solid transparent",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Backups & Restore
        </button>
        <button
          onClick={() => setActiveSection("system")}
          style={{
            padding: "0.75rem 1.25rem",
            background: activeSection === "system" ? "#1e293b" : "transparent",
            color: activeSection === "system" ? "#38bdf8" : "#94a3b8",
            border: "none",
            borderBottom: activeSection === "system" ? "3px solid #38bdf8" : "3px solid transparent",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Store & System
        </button>
      </div>

      {/* Alert Banners */}
      {errorMessage && (
        <div style={{ padding: "0.75rem 1rem", background: "#ef444422", border: "1px solid #ef4444", borderRadius: "6px", color: "#fca5a5", marginBottom: "1rem" }}>
          <strong>Error:</strong> {errorMessage}
        </div>
      )}
      {successMessage && (
        <div style={{ padding: "0.75rem 1rem", background: "#10b98122", border: "1px solid #10b981", borderRadius: "6px", color: "#6ee7b7", marginBottom: "1rem" }}>
          <strong>Success:</strong> {successMessage}
        </div>
      )}

      {/* =================================================================== */}
      {/* SECTION 1: COMPLIANCE & STATUTORY REPORTS */}
      {/* =================================================================== */}
      {activeSection === "compliance" && (
        <div>
          {/* Sub-selectors and Filters */}
          <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", gap: "1rem", background: "#1e293b", padding: "1rem", borderRadius: "8px", marginBottom: "1.5rem" }}>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button
                onClick={() => setComplianceSub("h1")}
                style={{ padding: "0.5rem 1rem", borderRadius: "4px", border: "none", background: complianceSub === "h1" ? "#0284c7" : "#334155", color: "#fff", cursor: "pointer", fontWeight: 600 }}
              >
                Schedule H1 Register
              </button>
              <button
                onClick={() => setComplianceSub("gstr1")}
                style={{ padding: "0.5rem 1rem", borderRadius: "4px", border: "none", background: complianceSub === "gstr1" ? "#0284c7" : "#334155", color: "#fff", cursor: "pointer", fontWeight: 600 }}
              >
                GSTR-1 Outward Supply
              </button>
              <button
                onClick={() => setComplianceSub("gstr2")}
                style={{ padding: "0.5rem 1rem", borderRadius: "4px", border: "none", background: complianceSub === "gstr2" ? "#0284c7" : "#334155", color: "#fff", cursor: "pointer", fontWeight: 600 }}
              >
                GSTR-2 Inward Register
              </button>
              <button
                onClick={() => setComplianceSub("sales")}
                style={{ padding: "0.5rem 1rem", borderRadius: "4px", border: "none", background: complianceSub === "sales" ? "#0284c7" : "#334155", color: "#fff", cursor: "pointer", fontWeight: 600 }}
              >
                Sales Register
              </button>
              <button
                onClick={() => setComplianceSub("purchases")}
                style={{ padding: "0.5rem 1rem", borderRadius: "4px", border: "none", background: complianceSub === "purchases" ? "#0284c7" : "#334155", color: "#fff", cursor: "pointer", fontWeight: 600 }}
              >
                Purchase Register
              </button>
            </div>

            {/* Date Filters & Refresh */}
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              <input
                type="date"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
                style={{ padding: "0.4rem 0.6rem", background: "#0f172a", border: "1px solid #475569", color: "#fff", borderRadius: "4px" }}
              />
              <span style={{ color: "#94a3b8" }}>to</span>
              <input
                type="date"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
                style={{ padding: "0.4rem 0.6rem", background: "#0f172a", border: "1px solid #475569", color: "#fff", borderRadius: "4px" }}
              />
              <select
                value={fiscalYear}
                onChange={(e) => setFiscalYear(e.target.value)}
                style={{ padding: "0.4rem 0.6rem", background: "#0f172a", border: "1px solid #475569", color: "#fff", borderRadius: "4px" }}
              >
                <option value="">All FY</option>
                <option value="2026-27">FY 2026-27</option>
                <option value="2025-26">FY 2025-26</option>
                <option value="2024-25">FY 2024-25</option>
              </select>
              <button
                onClick={loadComplianceReport}
                disabled={isLoading}
                style={{ padding: "0.4rem 1rem", background: "#10b981", color: "#fff", border: "none", borderRadius: "4px", cursor: "pointer", fontWeight: 600 }}
              >
                {isLoading ? "Loading..." : "Filter"}
              </button>
            </div>
          </div>

          {/* Sub-view: Schedule H1 Register */}
          {complianceSub === "h1" && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <h3 style={{ margin: 0, fontSize: "1.2rem" }}>Schedule H1 Drug Dispensing Register (Records: {h1Report?.total_records ?? 0})</h3>
                <button
                  onClick={() => reportsApi.downloadScheduleH1Csv({ from_date: fromDate, to_date: toDate })}
                  style={{ padding: "0.5rem 1rem", background: "#0284c7", color: "#fff", border: "none", borderRadius: "4px", cursor: "pointer", fontWeight: 600 }}
                >
                  Export Statutory CSV
                </button>
              </div>

              <div style={{ background: "#1e293b", borderRadius: "8px", overflow: "hidden" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "0.9rem" }}>
                  <thead>
                    <tr style={{ background: "#0f172a", color: "#94a3b8", borderBottom: "1px solid #334155" }}>
                      <th style={{ padding: "0.75rem 1rem" }}>Dispensed Date</th>
                      <th style={{ padding: "0.75rem 1rem" }}>Invoice No</th>
                      <th style={{ padding: "0.75rem 1rem" }}>Medicine Name</th>
                      <th style={{ padding: "0.75rem 1rem" }}>Batch</th>
                      <th style={{ padding: "0.75rem 1rem" }}>Units</th>
                      <th style={{ padding: "0.75rem 1rem" }}>Patient Name</th>
                      <th style={{ padding: "0.75rem 1rem" }}>Patient Address</th>
                      <th style={{ padding: "0.75rem 1rem" }}>Prescribing Doctor</th>
                    </tr>
                  </thead>
                  <tbody>
                    {h1Report?.records && h1Report.records.length > 0 ? (
                      h1Report.records.map((r) => (
                        <tr key={r.id} style={{ borderBottom: "1px solid #334155" }}>
                          <td style={{ padding: "0.75rem 1rem" }}>{r.dispensed_date}</td>
                          <td style={{ padding: "0.75rem 1rem", color: "#38bdf8", fontWeight: 600 }}>{r.invoice_no}</td>
                          <td style={{ padding: "0.75rem 1rem", fontWeight: 600 }}>{r.medicine_name}</td>
                          <td style={{ padding: "0.75rem 1rem" }}>{r.batch_number}</td>
                          <td style={{ padding: "0.75rem 1rem" }}>{r.quantity_units}</td>
                          <td style={{ padding: "0.75rem 1rem" }}>{r.patient_name}</td>
                          <td style={{ padding: "0.75rem 1rem", color: "#94a3b8" }}>{r.patient_address}</td>
                          <td style={{ padding: "0.75rem 1rem" }}>{r.doctor_name}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={8} style={{ padding: "2rem", textAlign: "center", color: "#94a3b8" }}>
                          No Schedule H1 prescriptions recorded in this date range.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Sub-view: GSTR-1 Outward Supplies */}
          {complianceSub === "gstr1" && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: "1.2rem" }}>GSTR-1 Outward Tax Invoices ({gstr1Report?.fiscal_year ?? "FY 2026-27"})</h3>
                  <p style={{ margin: "0.25rem 0 0", color: "#94a3b8", fontSize: "0.85rem" }}>
                    Total Taxable: {formatRupees(gstr1Report?.totals.total_taxable_paise ?? 0)} | CGST: {formatRupees(gstr1Report?.totals.total_cgst_paise ?? 0)} | SGST: {formatRupees(gstr1Report?.totals.total_sgst_paise ?? 0)} | Grand Total: {formatRupees(gstr1Report?.totals.grand_total_paise ?? 0)}
                  </p>
                </div>
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <button
                    onClick={() => reportsApi.downloadGstr1Csv("b2b", { from_date: fromDate, to_date: toDate, fiscal_year: fiscalYear })}
                    style={{ padding: "0.4rem 0.8rem", background: "#0284c7", color: "#fff", border: "none", borderRadius: "4px", cursor: "pointer", fontSize: "0.85rem" }}
                  >
                    CSV (B2B)
                  </button>
                  <button
                    onClick={() => reportsApi.downloadGstr1Csv("b2c", { from_date: fromDate, to_date: toDate, fiscal_year: fiscalYear })}
                    style={{ padding: "0.4rem 0.8rem", background: "#0284c7", color: "#fff", border: "none", borderRadius: "4px", cursor: "pointer", fontSize: "0.85rem" }}
                  >
                    CSV (B2C)
                  </button>
                  <button
                    onClick={() => reportsApi.downloadGstr1Csv("hsn", { from_date: fromDate, to_date: toDate, fiscal_year: fiscalYear })}
                    style={{ padding: "0.4rem 0.8rem", background: "#0284c7", color: "#fff", border: "none", borderRadius: "4px", cursor: "pointer", fontSize: "0.85rem" }}
                  >
                    CSV (HSN)
                  </button>
                </div>
              </div>

              {/* B2B Table */}
              <h4 style={{ color: "#38bdf8", margin: "1rem 0 0.5rem" }}>Table 4A - B2B Invoices (Registered Buyers with GSTIN)</h4>
              <div style={{ background: "#1e293b", borderRadius: "8px", overflow: "hidden", marginBottom: "1.5rem" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "0.9rem" }}>
                  <thead>
                    <tr style={{ background: "#0f172a", color: "#94a3b8", borderBottom: "1px solid #334155" }}>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Buyer GSTIN</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Buyer Name</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Invoice No</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Date</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Taxable</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Rate</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>CGST</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>SGST</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Invoice Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {gstr1Report?.b2b_invoices && gstr1Report.b2b_invoices.length > 0 ? (
                      gstr1Report.b2b_invoices.map((b, idx) => (
                        <tr key={idx} style={{ borderBottom: "1px solid #334155" }}>
                          <td style={{ padding: "0.6rem 0.8rem", color: "#facc15", fontWeight: 600 }}>{b.customer_gstin}</td>
                          <td style={{ padding: "0.6rem 0.8rem" }}>{b.customer_name}</td>
                          <td style={{ padding: "0.6rem 0.8rem", color: "#38bdf8" }}>{b.invoice_no}</td>
                          <td style={{ padding: "0.6rem 0.8rem" }}>{b.invoice_date}</td>
                          <td style={{ padding: "0.6rem 0.8rem" }}>{formatRupees(b.taxable_value_paise)}</td>
                          <td style={{ padding: "0.6rem 0.8rem" }}>{b.gst_rate}%</td>
                          <td style={{ padding: "0.6rem 0.8rem" }}>{formatRupees(b.cgst_paise)}</td>
                          <td style={{ padding: "0.6rem 0.8rem" }}>{formatRupees(b.sgst_paise)}</td>
                          <td style={{ padding: "0.6rem 0.8rem", fontWeight: 600 }}>{formatRupees(b.invoice_value_paise)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={9} style={{ padding: "1.5rem", textAlign: "center", color: "#94a3b8" }}>
                          No B2B invoices recorded in this period.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {/* HSN Summary */}
              <h4 style={{ color: "#38bdf8", margin: "1rem 0 0.5rem" }}>Table 12 - HSN Summary of Outward Supplies</h4>
              <div style={{ background: "#1e293b", borderRadius: "8px", overflow: "hidden" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "0.9rem" }}>
                  <thead>
                    <tr style={{ background: "#0f172a", color: "#94a3b8", borderBottom: "1px solid #334155" }}>
                      <th style={{ padding: "0.6rem 0.8rem" }}>HSN Code</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Description</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>UQC</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Qty</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Total Value</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Taxable</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Central Tax</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>State Tax</th>
                    </tr>
                  </thead>
                  <tbody>
                    {gstr1Report?.hsn_summary && gstr1Report.hsn_summary.length > 0 ? (
                      gstr1Report.hsn_summary.map((h, idx) => (
                        <tr key={idx} style={{ borderBottom: "1px solid #334155" }}>
                          <td style={{ padding: "0.6rem 0.8rem", color: "#a78bfa", fontWeight: 600 }}>{h.hsn_code}</td>
                          <td style={{ padding: "0.6rem 0.8rem" }}>{h.description}</td>
                          <td style={{ padding: "0.6rem 0.8rem" }}>{h.uqc}</td>
                          <td style={{ padding: "0.6rem 0.8rem" }}>{h.total_quantity}</td>
                          <td style={{ padding: "0.6rem 0.8rem" }}>{formatRupees(h.total_value_paise)}</td>
                          <td style={{ padding: "0.6rem 0.8rem" }}>{formatRupees(h.taxable_value_paise)}</td>
                          <td style={{ padding: "0.6rem 0.8rem" }}>{formatRupees(h.cgst_paise)}</td>
                          <td style={{ padding: "0.6rem 0.8rem" }}>{formatRupees(h.sgst_paise)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={8} style={{ padding: "1.5rem", textAlign: "center", color: "#94a3b8" }}>
                          No HSN records found.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Sub-view: GSTR-2 Inward Supplies */}
          {complianceSub === "gstr2" && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: "1.2rem" }}>GSTR-2 Inward Purchases (Grouped by Supplier GSTIN)</h3>
                  <p style={{ margin: "0.25rem 0 0", color: "#94a3b8", fontSize: "0.85rem" }}>
                    Total Invoices: {gstr2Report?.totals.total_invoices ?? 0} | Total Taxable: {formatRupees(gstr2Report?.totals.total_taxable_paise ?? 0)} | Total Inward: {formatRupees(gstr2Report?.totals.grand_total_paise ?? 0)}
                  </p>
                </div>
                <button
                  onClick={() => reportsApi.downloadGstr2Csv({ from_date: fromDate, to_date: toDate })}
                  style={{ padding: "0.5rem 1rem", background: "#0284c7", color: "#fff", border: "none", borderRadius: "4px", cursor: "pointer", fontWeight: 600 }}
                >
                  Export GSTR-2 CSV
                </button>
              </div>

              <div style={{ background: "#1e293b", borderRadius: "8px", overflow: "hidden" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "0.9rem" }}>
                  <thead>
                    <tr style={{ background: "#0f172a", color: "#94a3b8", borderBottom: "1px solid #334155" }}>
                      <th style={{ padding: "0.75rem 1rem" }}>Supplier GSTIN</th>
                      <th style={{ padding: "0.75rem 1rem" }}>Supplier Name</th>
                      <th style={{ padding: "0.75rem 1rem" }}>Invoices</th>
                      <th style={{ padding: "0.75rem 1rem" }}>Taxable Value</th>
                      <th style={{ padding: "0.75rem 1rem" }}>Input Tax (GST)</th>
                      <th style={{ padding: "0.75rem 1rem" }}>Grand Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {gstr2Report?.suppliers && gstr2Report.suppliers.length > 0 ? (
                      gstr2Report.suppliers.map((s) => (
                        <tr key={s.supplier_id} style={{ borderBottom: "1px solid #334155" }}>
                          <td style={{ padding: "0.75rem 1rem", color: "#facc15", fontWeight: 600 }}>{s.supplier_gstin}</td>
                          <td style={{ padding: "0.75rem 1rem", fontWeight: 600 }}>{s.supplier_name}</td>
                          <td style={{ padding: "0.75rem 1rem" }}>{s.invoice_count}</td>
                          <td style={{ padding: "0.75rem 1rem" }}>{formatRupees(s.subtotal_taxable_paise)}</td>
                          <td style={{ padding: "0.75rem 1rem", color: "#38bdf8" }}>{formatRupees(s.total_tax_paise)}</td>
                          <td style={{ padding: "0.75rem 1rem", fontWeight: 700 }}>{formatRupees(s.grand_total_paise)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={6} style={{ padding: "2rem", textAlign: "center", color: "#94a3b8" }}>
                          No inward purchase invoices found.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Sub-view: Sales Register */}
          {complianceSub === "sales" && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <h3 style={{ margin: 0, fontSize: "1.2rem" }}>Sales Register ({salesRegister.length} bills)</h3>
                <button
                  onClick={() => reportsApi.downloadSalesRegisterCsv({ from_date: fromDate, to_date: toDate })}
                  style={{ padding: "0.5rem 1rem", background: "#0284c7", color: "#fff", border: "none", borderRadius: "4px", cursor: "pointer", fontWeight: 600 }}
                >
                  Export Sales Register CSV
                </button>
              </div>

              <div style={{ background: "#1e293b", borderRadius: "8px", overflow: "hidden" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "0.9rem" }}>
                  <thead>
                    <tr style={{ background: "#0f172a", color: "#94a3b8", borderBottom: "1px solid #334155" }}>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Invoice No</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Date</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Customer</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Mode</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Items</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Taxable</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>CGST</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>SGST</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Grand Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {salesRegister.length > 0 ? (
                      salesRegister.map((s) => (
                        <tr key={s.invoice_id} style={{ borderBottom: "1px solid #334155" }}>
                          <td style={{ padding: "0.6rem 0.8rem", color: "#38bdf8", fontWeight: 600 }}>{s.invoice_no}</td>
                          <td style={{ padding: "0.6rem 0.8rem" }}>{s.invoice_date.slice(0, 10)}</td>
                          <td style={{ padding: "0.6rem 0.8rem" }}>{s.customer_name || "Walk-in"}</td>
                          <td style={{ padding: "0.6rem 0.8rem" }}>{s.payment_mode}</td>
                          <td style={{ padding: "0.6rem 0.8rem" }}>{s.item_count}</td>
                          <td style={{ padding: "0.6rem 0.8rem" }}>{formatRupees(s.subtotal_taxable_paise)}</td>
                          <td style={{ padding: "0.6rem 0.8rem" }}>{formatRupees(s.total_cgst_paise)}</td>
                          <td style={{ padding: "0.6rem 0.8rem" }}>{formatRupees(s.total_sgst_paise)}</td>
                          <td style={{ padding: "0.6rem 0.8rem", fontWeight: 700 }}>{formatRupees(s.grand_total_paise)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={9} style={{ padding: "2rem", textAlign: "center", color: "#94a3b8" }}>
                          No sales bills recorded in this period.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Sub-view: Purchase Register */}
          {complianceSub === "purchases" && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <h3 style={{ margin: 0, fontSize: "1.2rem" }}>Purchase Register ({purchaseRegister.length} inward bills)</h3>
                <button
                  onClick={() => reportsApi.downloadPurchaseRegisterCsv({ from_date: fromDate, to_date: toDate })}
                  style={{ padding: "0.5rem 1rem", background: "#0284c7", color: "#fff", border: "none", borderRadius: "4px", cursor: "pointer", fontWeight: 600 }}
                >
                  Export Purchase Register CSV
                </button>
              </div>

              <div style={{ background: "#1e293b", borderRadius: "8px", overflow: "hidden" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "0.9rem" }}>
                  <thead>
                    <tr style={{ background: "#0f172a", color: "#94a3b8", borderBottom: "1px solid #334155" }}>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Supplier Invoice</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Date</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Supplier</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>GSTIN</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Taxable Value</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Tax Amount</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Grand Total</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {purchaseRegister.length > 0 ? (
                      purchaseRegister.map((p) => (
                        <tr key={p.invoice_id} style={{ borderBottom: "1px solid #334155" }}>
                          <td style={{ padding: "0.6rem 0.8rem", color: "#38bdf8", fontWeight: 600 }}>{p.supplier_invoice_number}</td>
                          <td style={{ padding: "0.6rem 0.8rem" }}>{p.invoice_date}</td>
                          <td style={{ padding: "0.6rem 0.8rem", fontWeight: 600 }}>{p.supplier_name}</td>
                          <td style={{ padding: "0.6rem 0.8rem", color: "#facc15" }}>{p.supplier_gstin || "—"}</td>
                          <td style={{ padding: "0.6rem 0.8rem" }}>{formatRupees(p.subtotal_paise)}</td>
                          <td style={{ padding: "0.6rem 0.8rem" }}>{formatRupees(p.tax_amount_paise)}</td>
                          <td style={{ padding: "0.6rem 0.8rem", fontWeight: 700 }}>{formatRupees(p.grand_total_paise)}</td>
                          <td style={{ padding: "0.6rem 0.8rem" }}>
                            <span style={{ padding: "0.2rem 0.5rem", borderRadius: "4px", background: p.status === "POSTED" ? "#065f46" : "#78350f", color: "#fff", fontSize: "0.8rem" }}>
                              {p.status}
                            </span>
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={8} style={{ padding: "2rem", textAlign: "center", color: "#94a3b8" }}>
                          No purchases found.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* =================================================================== */}
      {/* SECTION 2: DAY-BOOK & CASH DRAWER RECONCILIATION */}
      {/* =================================================================== */}
      {activeSection === "daybook" && (
        <div>
          {/* Live Session Overview */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "1rem", marginBottom: "1.5rem" }}>
            <div style={{ background: "#1e293b", padding: "1.25rem", borderRadius: "8px", borderLeft: "4px solid #38bdf8" }}>
              <div style={{ color: "#94a3b8", fontSize: "0.85rem" }}>Session Date</div>
              <div style={{ fontSize: "1.25rem", fontWeight: 700, margin: "0.25rem 0" }}>{dayBookCurrent?.session.session_date ?? "Today"}</div>
              <span style={{ padding: "0.2rem 0.5rem", borderRadius: "4px", background: dayBookCurrent?.session.status === "OPEN" ? "#065f46" : "#475569", color: "#fff", fontSize: "0.8rem" }}>
                {dayBookCurrent?.session.status ?? "OPEN"}
              </span>
            </div>

            <div style={{ background: "#1e293b", padding: "1.25rem", borderRadius: "8px", borderLeft: "4px solid #0284c7" }}>
              <div style={{ color: "#94a3b8", fontSize: "0.85rem" }}>Opening Float</div>
              <div style={{ fontSize: "1.5rem", fontWeight: 700, margin: "0.25rem 0" }}>
                {formatRupees(dayBookCurrent?.summary.opening_float_paise ?? 0)}
              </div>
              <div style={{ color: "#64748b", fontSize: "0.8rem" }}>Drawer starting cash</div>
            </div>

            <div style={{ background: "#1e293b", padding: "1.25rem", borderRadius: "8px", borderLeft: "4px solid #10b981" }}>
              <div style={{ color: "#94a3b8", fontSize: "0.85rem" }}>Cash Sales (+)</div>
              <div style={{ fontSize: "1.5rem", fontWeight: 700, margin: "0.25rem 0", color: "#34d399" }}>
                {formatRupees(dayBookCurrent?.summary.cash_sales_paise ?? 0)}
              </div>
              <div style={{ color: "#64748b", fontSize: "0.8rem" }}>Direct counter sales</div>
            </div>

            <div style={{ background: "#1e293b", padding: "1.25rem", borderRadius: "8px", borderLeft: "4px solid #a855f7" }}>
              <div style={{ color: "#94a3b8", fontSize: "0.85rem" }}>Khata Deposits (+)</div>
              <div style={{ fontSize: "1.5rem", fontWeight: 700, margin: "0.25rem 0", color: "#c084fc" }}>
                {formatRupees(dayBookCurrent?.summary.cash_deposits_paise ?? 0)}
              </div>
              <div style={{ color: "#64748b", fontSize: "0.8rem" }}>Customer payments</div>
            </div>

            <div style={{ background: "#1e293b", padding: "1.25rem", borderRadius: "8px", borderLeft: "4px solid #f43f5e" }}>
              <div style={{ color: "#94a3b8", fontSize: "0.85rem" }}>Cash Refunds (-)</div>
              <div style={{ fontSize: "1.5rem", fontWeight: 700, margin: "0.25rem 0", color: "#fb7185" }}>
                {formatRupees(dayBookCurrent?.summary.cash_refunds_paise ?? 0)}
              </div>
              <div style={{ color: "#64748b", fontSize: "0.8rem" }}>Returns cash payout</div>
            </div>

            <div style={{ background: "#1e293b", padding: "1.25rem", borderRadius: "8px", borderLeft: "4px solid #facc15" }}>
              <div style={{ color: "#94a3b8", fontSize: "0.85rem" }}>Expected Cash in Drawer</div>
              <div style={{ fontSize: "1.6rem", fontWeight: 800, margin: "0.25rem 0", color: "#facc15" }}>
                {formatRupees(dayBookCurrent?.summary.expected_cash_paise ?? 0)}
              </div>
              <div style={{ color: "#64748b", fontSize: "0.8rem" }}>Float + Sales + Deposits - Refunds</div>
            </div>
          </div>

          {/* Action Boxes: Float & Drawer Closure */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem", marginBottom: "2rem" }}>
            {/* Box A: Opening Float Setup */}
            <div style={{ background: "#1e293b", padding: "1.25rem", borderRadius: "8px" }}>
              <h3 style={{ margin: "0 0 1rem", fontSize: "1.1rem" }}>Opening Float Setup</h3>
              <p style={{ color: "#94a3b8", fontSize: "0.85rem", margin: "0 0 1rem" }}>
                Set the starting float placed into the counter drawer at the start of the morning shift.
              </p>
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={floatInputRupees}
                  onChange={(e) => setFloatInputRupees(e.target.value)}
                  placeholder="₹ 500.00"
                  disabled={dayBookCurrent?.session.status === "CLOSED"}
                  style={{ flex: 1, padding: "0.6rem 0.8rem", background: "#0f172a", border: "1px solid #475569", color: "#fff", borderRadius: "4px", fontSize: "1rem" }}
                />
                <button
                  onClick={handleSetOpeningFloat}
                  disabled={dayBookCurrent?.session.status === "CLOSED" || isLoading}
                  style={{ padding: "0.6rem 1.25rem", background: "#0284c7", color: "#fff", border: "none", borderRadius: "4px", cursor: "pointer", fontWeight: 600 }}
                >
                  Save Float
                </button>
              </div>
            </div>

            {/* Box B: Drawer Closure & Variance */}
            <div style={{ background: "#1e293b", padding: "1.25rem", borderRadius: "8px" }}>
              <h3 style={{ margin: "0 0 1rem", fontSize: "1.1rem" }}>Physical Cash Count & Close Day</h3>
              <p style={{ color: "#94a3b8", fontSize: "0.85rem", margin: "0 0 1rem" }}>
                Count all currency notes and coins physically present in the drawer at the end of the shift.
              </p>

              {dayBookCurrent?.session.status === "CLOSED" ? (
                <div style={{ padding: "1rem", background: "#0f172a", borderRadius: "6px", color: "#94a3b8" }}>
                  <p style={{ margin: 0, fontWeight: 600, color: "#34d399" }}>Today's Cash Drawer is Sealed and Closed.</p>
                  <p style={{ margin: "0.25rem 0 0", fontSize: "0.85rem" }}>
                    Actual Counted: {formatRupees(dayBookCurrent.session.actual_cash_paise ?? 0)} |
                    Variance: {formatRupees(dayBookCurrent.session.variance_paise ?? 0)}
                  </p>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  <div>
                    <label style={{ display: "block", color: "#94a3b8", fontSize: "0.85rem", marginBottom: "0.25rem" }}>Physical Drawer Cash Count (₹)</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={actualCashRupees}
                      onChange={(e) => setActualCashRupees(e.target.value)}
                      placeholder="Enter counted drawer cash"
                      style={{ width: "100%", padding: "0.6rem 0.8rem", background: "#0f172a", border: "1px solid #475569", color: "#fff", borderRadius: "4px", fontSize: "1rem" }}
                    />
                  </div>

                  <div>
                    <label style={{ display: "block", color: "#94a3b8", fontSize: "0.85rem", marginBottom: "0.25rem" }}>Closure Notes (optional)</label>
                    <input
                      type="text"
                      value={closeNotes}
                      onChange={(e) => setCloseNotes(e.target.value)}
                      placeholder="e.g. ₹5 shortage verified, no counterfeit notes"
                      style={{ width: "100%", padding: "0.5rem 0.8rem", background: "#0f172a", border: "1px solid #475569", color: "#fff", borderRadius: "4px" }}
                    />
                  </div>

                  <button
                    onClick={handleCloseDayBook}
                    disabled={isLoading}
                    style={{ padding: "0.75rem", background: "#dc2626", color: "#fff", border: "none", borderRadius: "4px", cursor: "pointer", fontWeight: 700 }}
                  >
                    Lock Drawer & Close Day
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Historical Cash Sessions Table */}
          <h3 style={{ margin: "0 0 1rem", fontSize: "1.1rem" }}>Previous Closed Day-Book Sessions</h3>
          <div style={{ background: "#1e293b", borderRadius: "8px", overflow: "hidden" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "0.9rem" }}>
              <thead>
                <tr style={{ background: "#0f172a", color: "#94a3b8", borderBottom: "1px solid #334155" }}>
                  <th style={{ padding: "0.6rem 0.8rem" }}>Date</th>
                  <th style={{ padding: "0.6rem 0.8rem" }}>Opening Float</th>
                  <th style={{ padding: "0.6rem 0.8rem" }}>Cash Sales</th>
                  <th style={{ padding: "0.6rem 0.8rem" }}>Deposits</th>
                  <th style={{ padding: "0.6rem 0.8rem" }}>Refunds</th>
                  <th style={{ padding: "0.6rem 0.8rem" }}>Expected</th>
                  <th style={{ padding: "0.6rem 0.8rem" }}>Actual Count</th>
                  <th style={{ padding: "0.6rem 0.8rem" }}>Variance</th>
                  <th style={{ padding: "0.6rem 0.8rem" }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {dayBookHistory.length > 0 ? (
                  dayBookHistory.map((s) => (
                    <tr key={s.id} style={{ borderBottom: "1px solid #334155" }}>
                      <td style={{ padding: "0.6rem 0.8rem", fontWeight: 600 }}>{s.session_date}</td>
                      <td style={{ padding: "0.6rem 0.8rem" }}>{formatRupees(s.opening_float_paise)}</td>
                      <td style={{ padding: "0.6rem 0.8rem", color: "#34d399" }}>{formatRupees(s.cash_sales_paise)}</td>
                      <td style={{ padding: "0.6rem 0.8rem", color: "#c084fc" }}>{formatRupees(s.cash_deposits_paise)}</td>
                      <td style={{ padding: "0.6rem 0.8rem", color: "#fb7185" }}>{formatRupees(s.cash_refunds_paise)}</td>
                      <td style={{ padding: "0.6rem 0.8rem" }}>{formatRupees(s.expected_cash_paise)}</td>
                      <td style={{ padding: "0.6rem 0.8rem", fontWeight: 600 }}>{s.actual_cash_paise !== null && s.actual_cash_paise !== undefined ? formatRupees(s.actual_cash_paise) : "—"}</td>
                      <td style={{ padding: "0.6rem 0.8rem", color: (s.variance_paise ?? 0) < 0 ? "#f87171" : (s.variance_paise ?? 0) > 0 ? "#facc15" : "#34d399", fontWeight: 600 }}>
                        {s.variance_paise !== null && s.variance_paise !== undefined ? formatRupees(s.variance_paise) : "—"}
                      </td>
                      <td style={{ padding: "0.6rem 0.8rem" }}>
                        <span style={{ padding: "0.2rem 0.5rem", borderRadius: "4px", background: s.status === "CLOSED" ? "#334155" : "#065f46", color: "#fff", fontSize: "0.8rem" }}>
                          {s.status}
                        </span>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={9} style={{ padding: "1.5rem", textAlign: "center", color: "#94a3b8" }}>
                      No historic sessions recorded yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* =================================================================== */}
      {/* SECTION 3: HOT BACKUPS & DISASTER RECOVERY */}
      {/* =================================================================== */}
      {activeSection === "backups" && (
        <div>
          {/* Action Row */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: "#1e293b", padding: "1.25rem", borderRadius: "8px", marginBottom: "1.5rem" }}>
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flex: 1, maxWidth: "600px" }}>
              <input
                type="text"
                value={backupNotes}
                onChange={(e) => setBackupNotes(e.target.value)}
                placeholder="Optional backup note (e.g. Before month-end audit)"
                style={{ flex: 1, padding: "0.6rem 0.8rem", background: "#0f172a", border: "1px solid #475569", color: "#fff", borderRadius: "4px" }}
              />
              <button
                onClick={handleCreateBackup}
                disabled={isLoading}
                style={{ padding: "0.6rem 1.25rem", background: "#10b981", color: "#fff", border: "none", borderRadius: "4px", cursor: "pointer", fontWeight: 700 }}
              >
                Create Hot Backup (.pbk)
              </button>
            </div>

            <div>
              <label style={{ padding: "0.6rem 1.25rem", background: "#475569", color: "#fff", borderRadius: "4px", cursor: "pointer", fontWeight: 600 }}>
                Upload & Restore (.pbk)
                <input
                  type="file"
                  accept=".pbk,.zip"
                  onChange={handleFileUploadForRestore}
                  style={{ display: "none" }}
                />
              </label>
            </div>
          </div>

          {/* Verification Result Banner */}
          {verifyResult && (
            <div style={{ padding: "1rem", borderRadius: "6px", marginBottom: "1rem", background: verifyResult.is_valid ? "#065f4633" : "#7f1d1d33", border: `1px solid ${verifyResult.is_valid ? "#10b981" : "#ef4444"}` }}>
              <strong>Verification Result for {verifyResult.filename}:</strong>
              <div>Status: {verifyResult.integrity_status} | SHA-256: <code>{verifyResult.sha256_hash.slice(0, 16)}...</code></div>
              <div style={{ fontSize: "0.85rem", color: "#94a3b8" }}>{verifyResult.message}</div>
            </div>
          )}

          {/* Backup Manifests Table */}
          <h3 style={{ margin: "0 0 1rem", fontSize: "1.1rem" }}>Available Backup Archives ({backupsList.length})</h3>
          <div style={{ background: "#1e293b", borderRadius: "8px", overflow: "hidden" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "0.9rem" }}>
              <thead>
                <tr style={{ background: "#0f172a", color: "#94a3b8", borderBottom: "1px solid #334155" }}>
                  <th style={{ padding: "0.6rem 0.8rem" }}>Archive Filename</th>
                  <th style={{ padding: "0.6rem 0.8rem" }}>Type</th>
                  <th style={{ padding: "0.6rem 0.8rem" }}>Created Date</th>
                  <th style={{ padding: "0.6rem 0.8rem" }}>Size</th>
                  <th style={{ padding: "0.6rem 0.8rem" }}>Invoices</th>
                  <th style={{ padding: "0.6rem 0.8rem" }}>Revenue</th>
                  <th style={{ padding: "0.6rem 0.8rem" }}>Status</th>
                  <th style={{ padding: "0.6rem 0.8rem" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {backupsList.length > 0 ? (
                  backupsList.map((b) => (
                    <tr key={b.id} style={{ borderBottom: "1px solid #334155" }}>
                      <td style={{ padding: "0.6rem 0.8rem", color: "#38bdf8", fontWeight: 600 }}>{b.filename}</td>
                      <td style={{ padding: "0.6rem 0.8rem" }}>
                        <span style={{ padding: "0.2rem 0.5rem", borderRadius: "4px", background: b.backup_type === "PRE_RESTORE_SAFETY" ? "#7c2d12" : "#1e293b", color: "#fff", fontSize: "0.75rem", border: "1px solid #475569" }}>
                          {b.backup_type}
                        </span>
                      </td>
                      <td style={{ padding: "0.6rem 0.8rem" }}>{b.created_at.slice(0, 19).replace("T", " ")}</td>
                      <td style={{ padding: "0.6rem 0.8rem" }}>{(b.file_size_bytes / 1024).toFixed(1)} KB</td>
                      <td style={{ padding: "0.6rem 0.8rem" }}>{b.invoice_count}</td>
                      <td style={{ padding: "0.6rem 0.8rem" }}>{formatRupees(b.revenue_total_paise)}</td>
                      <td style={{ padding: "0.6rem 0.8rem" }}>
                        <span style={{ padding: "0.2rem 0.5rem", borderRadius: "4px", background: b.status === "VALID" ? "#065f46" : "#991b1b", color: "#fff", fontSize: "0.75rem" }}>
                          {b.status}
                        </span>
                      </td>
                      <td style={{ padding: "0.6rem 0.8rem" }}>
                        <div style={{ display: "flex", gap: "0.35rem" }}>
                          <button
                            onClick={() => handleVerifyBackup(b.id)}
                            style={{ padding: "0.3rem 0.6rem", background: "#334155", color: "#fff", border: "none", borderRadius: "4px", cursor: "pointer", fontSize: "0.8rem" }}
                          >
                            Verify
                          </button>
                          <button
                            onClick={() => systemApi.downloadBackupArchive(b.id, b.filename)}
                            style={{ padding: "0.3rem 0.6rem", background: "#0284c7", color: "#fff", border: "none", borderRadius: "4px", cursor: "pointer", fontSize: "0.8rem" }}
                          >
                            Download
                          </button>
                          <button
                            onClick={() => handlePreviewRestoreFromId(b.id)}
                            style={{ padding: "0.3rem 0.6rem", background: "#b91c1c", color: "#fff", border: "none", borderRadius: "4px", cursor: "pointer", fontSize: "0.8rem" }}
                          >
                            Restore
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={8} style={{ padding: "2rem", textAlign: "center", color: "#94a3b8" }}>
                      No backup archives found. Click 'Create Hot Backup' to take a snapshot.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Restore Confirmation Modal */}
          {isRestoreModalOpen && restorePreview && (
            <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
              <div style={{ background: "#1e293b", padding: "1.75rem", borderRadius: "8px", maxWidth: "560px", width: "90%", border: "1px solid #ef4444" }}>
                <h3 style={{ margin: "0 0 1rem", color: "#f87171" }}>Inspect & Confirm Database Restore</h3>

                <div style={{ background: "#0f172a", padding: "1rem", borderRadius: "6px", fontSize: "0.9rem", marginBottom: "1rem" }}>
                  <div><strong>Package:</strong> {restorePreview.filename}</div>
                  <div><strong>Snapshot Created:</strong> {restorePreview.created_at.slice(0, 19).replace("T", " ")}</div>
                  <div><strong>Schema Version:</strong> v{restorePreview.schema_version}</div>
                  <div><strong>Invoices Recorded:</strong> {restorePreview.invoice_count}</div>
                  <div><strong>Total Medicines:</strong> {restorePreview.medicine_count}</div>
                  <div><strong>Total Sales Revenue:</strong> {formatRupees(restorePreview.revenue_total_paise)}</div>
                  <div><strong>Compatibility:</strong> <span style={{ color: restorePreview.is_compatible ? "#34d399" : "#f87171", fontWeight: 600 }}>{restorePreview.is_compatible ? "COMPATIBLE" : "INCOMPATIBLE"}</span></div>
                  <div><strong>Status:</strong> {restorePreview.message}</div>
                </div>

                <div style={{ padding: "0.75rem", background: "#f59e0b22", border: "1px solid #f59e0b", borderRadius: "4px", color: "#fcd34d", fontSize: "0.85rem", marginBottom: "1.25rem" }}>
                  Notice: An automatic safety backup (PRE_RESTORE_SAFETY) will be taken immediately before restoring.
                </div>

                <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
                  <button
                    onClick={() => setIsRestoreModalOpen(false)}
                    style={{ padding: "0.6rem 1.25rem", background: "#475569", color: "#fff", border: "none", borderRadius: "4px", cursor: "pointer" }}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleExecuteRestore}
                    disabled={!restorePreview.is_compatible || isLoading}
                    style={{ padding: "0.6rem 1.25rem", background: "#dc2626", color: "#fff", border: "none", borderRadius: "4px", cursor: "pointer", fontWeight: 700 }}
                  >
                    {isLoading ? "Restoring..." : "Yes, Restore Database"}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* =================================================================== */}
      {/* SECTION 4: LAN SETUP & STORE SETTINGS */}
      {/* =================================================================== */}
      {activeSection === "system" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
          {/* Card A: LAN Server & Network Status */}
          <div style={{ background: "#1e293b", padding: "1.5rem", borderRadius: "8px" }}>
            <h3 style={{ margin: "0 0 1rem", fontSize: "1.2rem" }}>LAN Server & Network Status</h3>

            <div style={{ marginBottom: "1.25rem" }}>
              <label style={{ display: "block", color: "#94a3b8", fontSize: "0.85rem", marginBottom: "0.5rem" }}>Operational Mode</label>
              <select
                value={serverMode}
                onChange={(e) => setServerMode(e.target.value)}
                style={{ width: "100%", padding: "0.6rem 0.8rem", background: "#0f172a", border: "1px solid #475569", color: "#fff", borderRadius: "4px" }}
              >
                <option value="STANDALONE">STANDALONE (Single PC localhost - 127.0.0.1)</option>
                <option value="LAN_SERVER">LAN_SERVER (Multi-PC Counter LAN - 0.0.0.0)</option>
              </select>
              <p style={{ color: "#64748b", fontSize: "0.8rem", margin: "0.25rem 0 0" }}>
                LAN_SERVER mode allows other billing counters on the local network to connect to this computer.
              </p>
            </div>

            {discoveryInfo && (
              <div style={{ background: "#0f172a", padding: "1rem", borderRadius: "6px", fontSize: "0.9rem" }}>
                <h4 style={{ margin: "0 0 0.5rem", color: "#38bdf8" }}>Active Connection Endpoints:</h4>
                <div style={{ color: "#94a3b8", fontSize: "0.85rem", marginBottom: "0.5rem" }}>
                  Counter terminals can access the POS at any of these URLs:
                </div>
                {discoveryInfo.lan_ips.map((ip, idx) => (
                  <div key={idx} style={{ padding: "0.25rem 0", color: "#34d399", fontFamily: "monospace" }}>
                    • http://{ip}:{discoveryInfo.port}
                  </div>
                ))}
                <div style={{ marginTop: "0.75rem", color: "#64748b", fontSize: "0.8rem" }}>
                  Database Size: {discoveryInfo.database_size_kb} KB | Platform: {discoveryInfo.platform}
                </div>
              </div>
            )}
          </div>

          {/* Card B: Store Credentials & Metadata */}
          <div style={{ background: "#1e293b", padding: "1.5rem", borderRadius: "8px" }}>
            <h3 style={{ margin: "0 0 1rem", fontSize: "1.2rem" }}>
              Store Profile & Tax Credentials{" "}
              {Object.keys(systemConfig).length > 0 && (
                <span style={{ fontSize: "0.8rem", color: "#64748b", fontWeight: "normal" }}>
                  ({Object.keys(systemConfig).length} parameters active)
                </span>
              )}
            </h3>

            <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div>
                <label style={{ display: "block", color: "#94a3b8", fontSize: "0.85rem", marginBottom: "0.25rem" }}>Store Trading Name</label>
                <input
                  type="text"
                  value={storeName}
                  onChange={(e) => setStoreName(e.target.value)}
                  placeholder="Apex Health Pharmacy"
                  style={{ width: "100%", padding: "0.6rem 0.8rem", background: "#0f172a", border: "1px solid #475569", color: "#fff", borderRadius: "4px" }}
                />
              </div>

              <div>
                <label style={{ display: "block", color: "#94a3b8", fontSize: "0.85rem", marginBottom: "0.25rem" }}>Pharmacy GSTIN</label>
                <input
                  type="text"
                  value={storeGstin}
                  onChange={(e) => setStoreGstin(e.target.value)}
                  placeholder="27AABCA1234F1Z5"
                  style={{ width: "100%", padding: "0.6rem 0.8rem", background: "#0f172a", border: "1px solid #475569", color: "#fff", borderRadius: "4px" }}
                />
              </div>

              <div>
                <label style={{ display: "block", color: "#94a3b8", fontSize: "0.85rem", marginBottom: "0.25rem" }}>Drug License Numbers (20B / 21B)</label>
                <input
                  type="text"
                  value={storeDl}
                  onChange={(e) => setStoreDl(e.target.value)}
                  placeholder="DL-20B-12345/21B-67890"
                  style={{ width: "100%", padding: "0.6rem 0.8rem", background: "#0f172a", border: "1px solid #475569", color: "#fff", borderRadius: "4px" }}
                />
              </div>

              <div>
                <label style={{ display: "block", color: "#94a3b8", fontSize: "0.85rem", marginBottom: "0.25rem" }}>Custom Backup Directory (optional)</label>
                <input
                  type="text"
                  value={backupDir}
                  onChange={(e) => setBackupDir(e.target.value)}
                  placeholder="Leave blank for default AppData/Local/PharmacyApp/backups"
                  style={{ width: "100%", padding: "0.6rem 0.8rem", background: "#0f172a", border: "1px solid #475569", color: "#fff", borderRadius: "4px" }}
                />
              </div>

              <button
                onClick={handleSaveSystemConfig}
                disabled={isLoading}
                style={{ padding: "0.75rem", background: "#10b981", color: "#fff", border: "none", borderRadius: "4px", cursor: "pointer", fontWeight: 700, marginTop: "0.5rem" }}
              >
                {isLoading ? "Saving..." : "Save Settings"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
