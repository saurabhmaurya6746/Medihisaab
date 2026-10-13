import React, { useState, useEffect } from "react";
import type {
  WastageRecord,
  WastageReason,
  MedicineBatch,
  Medicine,
} from "@pharmacy/api-contracts";
import { formatRupees } from "@pharmacy/api-contracts";
import * as returnsApi from "../api/returns";
import * as mastersApi from "../api/masters";
import * as purchasesApi from "../api/purchases";
import { PaginationBar } from "./PaginationBar";

export const WastageRegisterView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"write_off" | "history">("write_off");

  // Write-off form state
  const [medicineQuery, setMedicineQuery] = useState<string>("");
  const [medicineResults, setMedicineResults] = useState<Medicine[]>([]);
  const [selectedMedicine, setSelectedMedicine] = useState<Medicine | null>(null);
  const [batches, setBatches] = useState<MedicineBatch[]>([]);
  const [selectedBatchId, setSelectedBatchId] = useState<number | null>(null);
  const [writeOffUnits, setWriteOffUnits] = useState<number>(1);
  const [reason, setReason] = useState<WastageReason>("EXPIRED");
  const [notes, setNotes] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [successRecord, setSuccessRecord] = useState<WastageRecord | null>(null);

  // History state
  const [historyItems, setHistoryItems] = useState<WastageRecord[]>([]);
  const [historyPage, setHistoryPage] = useState<number>(1);
  const [historyTotalPages, setHistoryTotalPages] = useState<number>(1);
  const [historyTotal, setHistoryTotal] = useState<number>(0);
  const [filterReason, setFilterReason] = useState<string>("");

  // Search medicines
  useEffect(() => {
    if (selectedMedicine !== null) return;
    if (medicineQuery.trim().length >= 2) {
      const timer = setTimeout(() => {
        mastersApi
          .listMedicines({ query: medicineQuery.trim(), page_size: 10, is_active: true })
          .then((res: { items: Medicine[] }) => setMedicineResults(res.items))
          .catch((err: unknown) => console.error("Medicine search failed:", err));
      }, 200);
      return () => clearTimeout(timer);
    } else {
      setMedicineResults([]);
    }
  }, [medicineQuery, selectedMedicine]);

  // Load batches when medicine is selected
  const handleSelectMedicine = async (med: Medicine) => {
    setSelectedMedicine(med);
    setMedicineQuery(med.brand_name);
    setMedicineResults([]);
    setSelectedBatchId(null);

    try {
      const bRes = await purchasesApi.listBatches({ medicine_id: med.id, in_stock_only: false });
      setBatches(bRes.items);
      if (bRes.items.length > 0) {
        setSelectedBatchId(bRes.items[0].id);
      }
    } catch (err) {
      console.error("Failed to load medicine batches:", err);
    }
  };

  const handleClearMedicine = () => {
    setSelectedMedicine(null);
    setMedicineQuery("");
    setBatches([]);
    setSelectedBatchId(null);
  };

  const activeBatch = batches.find((b) => b.id === selectedBatchId);
  const maxStock = activeBatch ? activeBatch.current_quantity : 0;

  // Cost impact estimate
  const estimatedCostImpactPaise =
    activeBatch && selectedMedicine && selectedMedicine.pack_size > 0
      ? Math.floor((activeBatch.purchase_rate_paise * writeOffUnits) / selectedMedicine.pack_size)
      : activeBatch
      ? activeBatch.purchase_rate_paise * writeOffUnits
      : 0;

  const handleSubmitWriteOff = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedBatchId) {
      setSubmitError("Please select a batch to write off.");
      return;
    }
    if (writeOffUnits <= 0) {
      setSubmitError("Quantity must be greater than zero.");
      return;
    }
    if (writeOffUnits > maxStock) {
      setSubmitError(`Cannot write off more than available stock (${maxStock} units).`);
      return;
    }
    if (!notes.trim()) {
      setSubmitError("Notes explaining the loss/breakage/scrap reason are mandatory.");
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const record = await returnsApi.recordWastage({
        batch_id: selectedBatchId,
        quantity_units: writeOffUnits,
        reason,
        notes: notes.trim(),
      });
      setSuccessRecord(record);
      handleClearMedicine();
      setNotes("");
      setWriteOffUnits(1);
    } catch (err: any) {
      setSubmitError(err?.message || "Failed to record stock write-off.");
    } finally {
      setIsSubmitting(false);
    }
  };

  // Load history
  const loadHistory = async (page = 1) => {
    try {
      const res = await returnsApi.listWastage({
        page,
        page_size: 15,
        reason: filterReason || undefined,
      });
      setHistoryItems(res.items);
      setHistoryTotal(res.total);
      setHistoryTotalPages(res.total_pages);
    } catch (err) {
      console.error("Failed to load wastage register:", err);
    }
  };

  useEffect(() => {
    if (activeTab === "history") {
      loadHistory(historyPage);
    }
  }, [activeTab, historyPage, filterReason]);

  return (
    <div className="pos-page-shell">
      {/* 1. Page Header */}
      <div className="pos-page-header">
        <div className="pos-page-header-info">
          <div className="pos-page-icon-badge">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              <line x1="10" y1="11" x2="10" y2="17" />
              <line x1="14" y1="11" x2="14" y2="17" />
            </svg>
          </div>
          <div>
            <h1 className="pos-page-title">
              <span>Wastage</span>
            </h1>
            <p className="pos-page-subtitle">
              Record expired, broken, or damaged stock.
            </p>
          </div>
        </div>

        <div className="pos-page-actions">
          <div className="pos-subnav-strip">
            <button
              type="button"
              onClick={() => setActiveTab("write_off")}
              className={`pos-subnav-btn ${activeTab === "write_off" ? "active" : ""}`}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              <span>Record Wastage</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("history")}
              className={`pos-subnav-btn ${activeTab === "history" ? "active" : ""}`}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
                <polyline points="10 9 9 9 8 9" />
              </svg>
              <span>Wastage History</span>
            </button>
          </div>
        </div>
      </div>

      {/* 2. Main Content */}
      {activeTab === "write_off" ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 14, maxWidth: 760, margin: "0 auto", width: "100%" }}>
          {successRecord && (
            <div className="pos-alert pos-alert-success" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                  <polyline points="22 4 12 14.01 9 11.01" />
                </svg>
                <div>
                  <strong style={{ display: "block" }}>Write-off Recorded: #{successRecord.reference_no}</strong>
                  <span style={{ fontSize: "0.78rem" }}>
                    {successRecord.medicine_name} &times; {successRecord.quantity_units} units (Cost Impact: ₹{formatRupees(successRecord.cost_impact_paise)})
                  </span>
                </div>
              </div>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => setSuccessRecord(null)}
              >
                ✕ Dismiss
              </button>
            </div>
          )}

          <div className="pos-card">
            <div className="pos-card-header">
              <h2 className="pos-card-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span className="pos-step-num">!</span>
                <span>Stock Write-Off Entry</span>
              </h2>
              <span className="badge badge-danger">AUDIT LOGGED</span>
            </div>

            <form onSubmit={handleSubmitWriteOff} className="pos-card-body" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {/* Step 1: Select Medicine */}
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label form-label-required">
                  Select Medicine
                </label>
                {selectedMedicine ? (
                  <div
                    style={{
                      padding: "10px 14px",
                      backgroundColor: "var(--bg-input)",
                      border: "1px solid var(--border-subtle)",
                      borderRadius: "var(--radius-sm)",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 700, color: "#ffffff", fontSize: "0.92rem" }}>
                        {selectedMedicine.brand_name}
                      </div>
                      <div style={{ fontSize: "0.76rem", color: "var(--text-muted)", marginTop: 2 }}>
                        {selectedMedicine.generic_salt} • {selectedMedicine.dosage_form} (Pack of {selectedMedicine.pack_size})
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={handleClearMedicine}
                      className="btn btn-secondary btn-sm"
                    >
                      Change Medicine
                    </button>
                  </div>
                ) : (
                  <div style={{ position: "relative" }}>
                    <div className="search-input-wrapper" style={{ maxWidth: "100%" }}>
                      <svg
                        className="search-icon-left"
                        width="15"
                        height="15"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                      >
                        <circle cx="11" cy="11" r="8" />
                        <line x1="21" y1="21" x2="16.65" y2="16.65" />
                      </svg>
                      <input
                        type="text"
                        className="form-input"
                        placeholder="Type medicine brand name to search (e.g. Paracetamol, Dolo)..."
                        value={medicineQuery}
                        onChange={(e) => setMedicineQuery(e.target.value)}
                        autoFocus
                      />
                    </div>
                    {medicineResults.length > 0 && (
                      <div className="medicine-autocomplete-dropdown">
                        {medicineResults.map((m) => (
                          <div
                            key={m.id}
                            onClick={() => handleSelectMedicine(m)}
                            className="medicine-dropdown-item"
                          >
                            <div className="medicine-dropdown-brand">{m.brand_name}</div>
                            <div className="medicine-dropdown-meta">
                              {m.generic_salt} • {m.dosage_form} (Pack of {m.pack_size})
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Step 2: Select Batch */}
              {selectedMedicine && (
                <div className="form-group" style={{ margin: 0 }}>
                  <label className="form-label form-label-required">
                    Select Batch to Deduct Stock
                  </label>
                  {batches.length === 0 ? (
                    <div className="pos-alert pos-alert-error">
                      <span>No stock batches found in inventory for this medicine.</span>
                    </div>
                  ) : (
                    <div className="batch-select-grid">
                      {batches.map((b) => (
                        <div
                          key={b.id}
                          onClick={() => setSelectedBatchId(b.id)}
                          className={`batch-select-tile ${selectedBatchId === b.id ? "selected" : ""}`}
                          role="button"
                          tabIndex={0}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") setSelectedBatchId(b.id);
                          }}
                        >
                          <div className="batch-tile-header">
                            <span style={{ fontFamily: "var(--font-mono)" }}>Batch: {b.batch_number}</span>
                            <span
                              className={`pill-badge ${b.current_quantity > 0 ? "pill-active" : "pill-inactive"}`}
                            >
                              {b.current_quantity} in stock
                            </span>
                          </div>
                          <div className="batch-tile-meta">
                            <span>Exp: {b.expiry_date}</span>
                            <span>MRP: ₹{formatRupees(b.mrp_paise)}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Step 3: Write-Off Units & Reason */}
              {activeBatch && (
                <>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                    <div className="form-group" style={{ margin: 0 }}>
                      <label className="form-label form-label-required">
                        Units to Write Off
                      </label>
                      <input
                        type="number"
                        min="1"
                        max={maxStock}
                        value={writeOffUnits}
                        onChange={(e) => setWriteOffUnits(Math.max(1, parseInt(e.target.value, 10) || 1))}
                        className="form-input"
                        style={{ fontFamily: "var(--font-mono)", fontWeight: 700, fontSize: "1rem" }}
                      />
                      <span className="form-help-text" style={{ marginTop: 4 }}>
                        Max available on-hand: <strong style={{ color: "#34d399" }}>{maxStock} units</strong>
                      </span>
                    </div>

                    <div className="form-group" style={{ margin: 0 }}>
                      <label className="form-label form-label-required">
                        Loss / Disposal Reason
                      </label>
                      <select
                        value={reason}
                        onChange={(e) => setReason(e.target.value as WastageReason)}
                        className="form-input"
                      >
                        <option value="EXPIRED">EXPIRED (Past Expiry Date)</option>
                        <option value="BREAKAGE">BREAKAGE (Bottle/Vial Broken)</option>
                        <option value="DAMAGED">DAMAGED (Crushed/Moisture Spoiled)</option>
                        <option value="WASTAGE">WASTAGE (Dispensing Scrap)</option>
                        <option value="OTHER">OTHER (Special Disposal)</option>
                      </select>
                    </div>
                  </div>

                  {/* Cost Impact Preview Callout */}
                  <div
                    style={{
                      padding: "12px 16px",
                      backgroundColor: "var(--bg-input)",
                      border: "1px solid var(--border-subtle)",
                      borderRadius: "var(--radius-sm)",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <span style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                      Estimated Purchase Cost Impact:
                    </span>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: "1.2rem", fontWeight: 800, color: "#f87171" }}>
                      ₹{formatRupees(estimatedCostImpactPaise)}
                    </span>
                  </div>

                  {/* Mandatory Notes */}
                  <div className="form-group" style={{ margin: 0 }}>
                    <label className="form-label form-label-required">
                      Disposal Notes / Incident Explanation
                    </label>
                    <textarea
                      rows={3}
                      required
                      className="form-input"
                      placeholder="Explain how the damage, breakage, or expiry occurred and details of physical disposal..."
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                    />
                  </div>

                  {/* Warning Message (Requirement 6) */}
                  <div className="warning-banner">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ flexShrink: 0 }}>
                      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                      <line x1="12" y1="9" x2="12" y2="13" />
                      <line x1="12" y1="17" x2="12.01" y2="17" />
                    </svg>
                    <span>
                      <strong>Caution:</strong> Stock write-off permanently deducts batch stock inventory from the system. This audit action is irreversible.
                    </span>
                  </div>
                </>
              )}

              {submitError && (
                <div className="pos-alert pos-alert-error">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="8" x2="12" y2="12" />
                    <line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                  <span>{submitError}</span>
                </div>
              )}

              <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 4 }}>
                <button
                  type="submit"
                  disabled={isSubmitting || !activeBatch || writeOffUnits <= 0 || maxStock <= 0}
                  className="btn btn-danger"
                  style={{ padding: "10px 24px", fontSize: "0.92rem", fontWeight: 700 }}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="3 6 5 6 21 6" />
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                  </svg>
                  <span>{isSubmitting ? "Writing Off..." : "Confirm Stock Write-Off"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : (
        /* History View */
        <div style={{ display: "flex", flexDirection: "column", gap: 12, flex: 1, minHeight: 0 }}>
          <div className="master-toolbar">
            <div className="toolbar-left">
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: "0.78rem", color: "var(--text-muted)", fontWeight: 600 }}>Filter by Reason:</span>
                <select
                  value={filterReason}
                  onChange={(e) => setFilterReason(e.target.value)}
                  className="select-filter"
                  aria-label="Filter wastage by reason"
                >
                  <option value="">All Write-Off Reasons</option>
                  <option value="EXPIRED">EXPIRED</option>
                  <option value="BREAKAGE">BREAKAGE</option>
                  <option value="DAMAGED">DAMAGED</option>
                  <option value="WASTAGE">WASTAGE</option>
                  <option value="OTHER">OTHER</option>
                </select>
              </div>
            </div>

            <div className="toolbar-right">
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => loadHistory(1)}
                title="Refresh Wastage Log"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
                </svg>
                <span>Refresh</span>
              </button>
            </div>
          </div>

          <div className="data-table-card">
            <div className="table-responsive-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th style={{ width: "160px" }}>Reference #</th>
                    <th>Medicine Brand Name</th>
                    <th style={{ width: "160px" }}>Batch & Expiry</th>
                    <th style={{ width: "120px" }}>Reason</th>
                    <th style={{ width: "90px", textAlign: "right" }}>Units</th>
                    <th style={{ width: "130px", textAlign: "right" }}>Cost Loss (₹)</th>
                    <th>Audit Disposal Notes</th>
                    <th style={{ width: "130px" }}>Recorded Date</th>
                  </tr>
                </thead>
                <tbody>
                  {historyItems.length === 0 ? (
                    <tr>
                      <td colSpan={8}>
                        <div className="table-empty-state">
                          <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                            <polyline points="3 6 5 6 21 6" />
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
                          </svg>
                          <strong style={{ color: "#ffffff", fontSize: "1rem" }}>
                            {filterReason ? `No "${filterReason}" wastage records found` : "No wastage or scrap records recorded"}
                          </strong>
                          <p style={{ fontSize: "0.82rem", marginTop: 4, maxWidth: 440 }}>
                            {filterReason
                              ? `No records found with reason "${filterReason}". Clear filter to view all write-offs.`
                              : "No medicines have been written off as expired, broken, or scrap yet. Record a write-off when expired inventory is removed."}
                          </p>
                          <div style={{ marginTop: 14 }}>
                            {filterReason ? (
                              <button
                                type="button"
                                className="btn btn-secondary btn-sm"
                                onClick={() => setFilterReason("")}
                              >
                                Clear Filter
                              </button>
                            ) : (
                              <button
                                type="button"
                                className="btn btn-primary btn-sm"
                                onClick={() => setActiveTab("write_off")}
                              >
                                + Record Stock Write-Off
                              </button>
                            )}
                          </div>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    historyItems.map((w) => (
                      <tr key={w.id}>
                        <td className="col-code" style={{ color: "#f87171" }}>
                          {w.reference_no}
                        </td>
                        <td className="col-name">
                          {w.medicine_name}
                        </td>
                        <td>
                          <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.82rem" }}>
                            {w.batch_number}
                          </div>
                          <div style={{ fontSize: "0.74rem", color: "var(--text-dim)" }}>
                            Exp: {w.expiry_date}
                          </div>
                        </td>
                        <td>
                          <span className="badge badge-danger">
                            {w.reason}
                          </span>
                        </td>
                        <td className="col-amount" style={{ color: "#ffffff", fontWeight: 700 }}>
                          {w.quantity_units}
                        </td>
                        <td className="col-amount" style={{ color: "#f87171", fontWeight: 700 }}>
                          ₹{formatRupees(w.cost_impact_paise)}
                        </td>
                        <td style={{ color: "var(--text-muted)", fontSize: "0.82rem", maxWidth: "260px" }}>
                          <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {w.notes || "—"}
                          </div>
                        </td>
                        <td style={{ color: "var(--text-dim)", fontSize: "0.8rem", whiteSpace: "nowrap" }}>
                          {new Date(w.created_at).toLocaleDateString("en-IN", {
                            day: "2-digit",
                            month: "short",
                            year: "numeric",
                          })}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {historyTotalPages > 1 && (
              <PaginationBar
                page={historyPage}
                totalPages={historyTotalPages}
                total={historyTotal}
                pageSize={15}
                onPageChange={(p) => setHistoryPage(p)}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
};
