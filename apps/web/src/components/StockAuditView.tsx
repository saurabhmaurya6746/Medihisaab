import React, { useState, useEffect, useCallback, useRef } from "react";
import type {
  StockAdjustmentRecord,
  StockAdjustmentReason,
  BatchAuditDetails,
  MedicineBatch,
} from "@pharmacy/api-contracts";
import { formatRupees } from "@pharmacy/api-contracts";
import { useAuth } from "../context/AuthContext";
import * as inventoryApi from "../api/inventory";
import * as purchasesApi from "../api/purchases";
import { PaginationBar } from "./PaginationBar";

export const StockAuditView: React.FC = () => {
  const { user } = useAuth();
  const canAudit = user?.role === "ADMIN" || user?.role === "PHARMACIST";

  // Active Batch for Audit Form
  const [selectedBatchId, setSelectedBatchId] = useState<number | null>(null);
  const [batchDetails, setBatchDetails] = useState<BatchAuditDetails | null>(null);
  const [batchSearchQuery, setBatchSearchQuery] = useState<string>("");
  const [batchSearchResults, setBatchSearchResults] = useState<MedicineBatch[]>([]);
  const [isSearchingBatches, setIsSearchingBatches] = useState<boolean>(false);

  // Form Inputs
  const [physicalQuantity, setPhysicalQuantity] = useState<string>("");
  const [reason, setReason] = useState<StockAdjustmentReason>("AUDIT_CORRECTION");
  const [notes, setNotes] = useState<string>("");
  const [isSubmittingAudit, setIsSubmittingAudit] = useState<boolean>(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);

  // Audit History Table State
  const [audits, setAudits] = useState<StockAdjustmentRecord[]>([]);
  const [totalAudits, setTotalAudits] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(15);
  const [historySearch, setHistorySearch] = useState<string>("");
  const [historyReasonFilter, setHistoryReasonFilter] = useState<string>("");
  const [isLoadingHistory, setIsLoadingHistory] = useState<boolean>(true);

  const searchInputRef = useRef<HTMLInputElement>(null);
  const physicalQtyInputRef = useRef<HTMLInputElement>(null);

  // Search batches debounce
  useEffect(() => {
    if (!selectedBatchId && batchSearchQuery.trim().length >= 2) {
      setIsSearchingBatches(true);
      const timer = setTimeout(() => {
        purchasesApi
          .listBatches({
            query: batchSearchQuery.trim(),
            is_active: true,
            page_size: 20,
          })
          .then((res) => setBatchSearchResults(res.items))
          .catch((err) => console.error("Error searching batches:", err))
          .finally(() => setIsSearchingBatches(false));
      }, 250);
      return () => clearTimeout(timer);
    } else {
      setBatchSearchResults([]);
    }
  }, [batchSearchQuery, selectedBatchId]);

  // Load details when a batch is selected
  useEffect(() => {
    if (selectedBatchId) {
      inventoryApi
        .getBatchAuditDetails(selectedBatchId)
        .then((details) => {
          setBatchDetails(details);
          setPhysicalQuantity(details.current_quantity.toString());
          setTimeout(() => physicalQtyInputRef.current?.focus(), 50);
        })
        .catch((err) => {
          setFormError(`Failed to load batch: ${err.message}`);
        });
    } else {
      setBatchDetails(null);
      setPhysicalQuantity("");
    }
  }, [selectedBatchId]);

  // Load audit history
  const loadAuditHistory = useCallback(async () => {
    setIsLoadingHistory(true);
    try {
      const resp = await inventoryApi.listStockAudits({
        search: historySearch.trim() || undefined,
        reason: historyReasonFilter || undefined,
        page,
        page_size: pageSize,
      });
      setAudits(resp.items);
      setTotalAudits(resp.total);
      setTotalPages(resp.total_pages);
    } catch (err: any) {
      console.error("Error loading audit history:", err);
    } finally {
      setIsLoadingHistory(false);
    }
  }, [historySearch, historyReasonFilter, page, pageSize]);

  useEffect(() => {
    loadAuditHistory();
  }, [loadAuditHistory]);

  // Delta calculations
  const parsedPhysicalQty = parseInt(physicalQuantity, 10);
  const isValidNumber = !isNaN(parsedPhysicalQty) && parsedPhysicalQty >= 0;
  const systemQty = batchDetails ? batchDetails.current_quantity : 0;
  const deltaQty = isValidNumber ? parsedPhysicalQty - systemQty : 0;

  // Estimated loss/gain in paise
  let estimatedLossPaise = 0;
  if (batchDetails && deltaQty < 0) {
    const unitRate =
      batchDetails.pack_size > 0
        ? Math.floor(batchDetails.purchase_rate_paise / batchDetails.pack_size)
        : batchDetails.purchase_rate_paise;
    estimatedLossPaise = Math.abs(deltaQty) * unitRate;
  }

  // Handle audit form submission
  const handleSubmitAudit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canAudit) {
      setFormError("Only Admins and Pharmacists are authorized to perform stock audits.");
      return;
    }
    if (!selectedBatchId || !batchDetails) {
      setFormError("Please select a medicine batch to audit.");
      return;
    }
    if (!isValidNumber) {
      setFormError("Physical quantity must be a non-negative integer (>= 0).");
      return;
    }
    if (deltaQty === 0) {
      setFormError("Physical quantity matches current system stock. No adjustment needed.");
      return;
    }
    if (deltaQty < 0 && (!notes.trim() || notes.trim().length < 3)) {
      setFormError("Notes are mandatory for negative adjustments / inventory shrink.");
      return;
    }

    setIsSubmittingAudit(true);
    setFormError(null);
    setFormSuccess(null);

    try {
      const record = await inventoryApi.submitStockAudit({
        batch_id: selectedBatchId,
        physical_quantity: parsedPhysicalQty,
        reason,
        notes: notes.trim() || undefined,
      });

      setFormSuccess(
        `Audit record #${record.adjustment_number} committed successfully! Quantity updated from ${record.system_quantity} to ${record.physical_quantity} (${record.delta_quantity > 0 ? "+" : ""}${record.delta_quantity}).`
      );

      // Reset selection
      setSelectedBatchId(null);
      setBatchDetails(null);
      setBatchSearchQuery("");
      setNotes("");
      setPhysicalQuantity("");

      // Refresh history table
      loadAuditHistory();
    } catch (err: any) {
      setFormError(err.message || "Failed to commit stock audit.");
    } finally {
      setIsSubmittingAudit(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", gap: 14, overflowY: "auto" }}>
      {/* 1. Header Strip */}
      <div className="pos-panel" style={{ padding: "12px 18px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: "1.25rem", fontWeight: 700, color: "var(--text-main)" }}>
              Stock Audit
            </h2>
            <p style={{ margin: "4px 0 0", fontSize: "0.82rem", color: "var(--text-muted)" }}>
              Verify physical inventory counts and record stock adjustments.
            </p>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span
              style={{
                fontSize: "0.78rem",
                padding: "4px 10px",
                borderRadius: 4,
                backgroundColor: canAudit ? "rgba(16, 185, 129, 0.15)" : "rgba(239, 68, 68, 0.15)",
                color: canAudit ? "#10b981" : "#ef4444",
                fontWeight: 600,
              }}
            >
              {canAudit ? "Authorized to Adjust Stock" : "Read-Only (Cashier Mode)"}
            </span>
          </div>
        </div>
      </div>

      {/* 2. Top Half: Audit Entry Card */}
      {canAudit && (
        <div className="pos-panel" style={{ padding: "16px 20px" }}>
          <h3 style={{ fontSize: "1rem", fontWeight: 700, marginBottom: 12, color: "var(--accent-primary)" }}>
            Select Batch & Count Stock
          </h3>

          {formError && (
            <div
              style={{
                backgroundColor: "rgba(239, 68, 68, 0.15)",
                border: "1px solid var(--accent-danger)",
                color: "#fca5a5",
                padding: "8px 14px",
                borderRadius: 4,
                marginBottom: 12,
                fontSize: "0.85rem",
              }}
            >
              {formError}
            </div>
          )}

          {formSuccess && (
            <div
              style={{
                backgroundColor: "rgba(16, 185, 129, 0.15)",
                border: "1px solid var(--accent-success)",
                color: "#6ee7b7",
                padding: "8px 14px",
                borderRadius: 4,
                marginBottom: 12,
                fontSize: "0.85rem",
              }}
            >
              {formSuccess}
            </div>
          )}

          <form onSubmit={handleSubmitAudit}>
            <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 20 }}>
              {/* Batch Search / Selection */}
              <div>
                <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: 6 }}>
                  Medicine or Batch Number <span style={{ color: "var(--accent-danger)" }}>*</span>
                </label>
                {batchDetails ? (
                  <div
                    style={{
                      background: "var(--bg-surface-elevated)",
                      border: "1px solid var(--border-focus)",
                      borderRadius: 6,
                      padding: "10px 14px",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 700, fontSize: "0.95rem", color: "#ffffff" }}>
                        {batchDetails.medicine_name}
                      </div>
                      <div style={{ fontSize: "0.8rem", color: "var(--text-dim)", marginTop: 2 }}>
                        Batch: <strong style={{ color: "#38bdf8" }}>{batchDetails.batch_number}</strong> | Exp:{" "}
                        {batchDetails.expiry_date} | Pack: {batchDetails.pack_size}
                        {batchDetails.rack_location ? ` | Rack: ${batchDetails.rack_location}` : ""}
                      </div>
                    </div>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => {
                        setSelectedBatchId(null);
                        setBatchDetails(null);
                        setBatchSearchQuery("");
                      }}
                    >
                      Change Batch
                    </button>
                  </div>
                ) : (
                  <div style={{ position: "relative" }}>
                    <input
                      ref={searchInputRef}
                      type="text"
                      className="input-field"
                      placeholder="Type medicine name or batch number..."
                      value={batchSearchQuery}
                      onChange={(e) => setBatchSearchQuery(e.target.value)}
                      style={{ width: "100%", padding: "8px 12px" }}
                    />
                    {isSearchingBatches && (
                      <span style={{ position: "absolute", right: 10, top: 8, fontSize: "0.75rem", color: "var(--text-dim)" }}>
                        Searching...
                      </span>
                    )}
                    {batchSearchResults.length > 0 && (
                      <div
                        style={{
                          position: "absolute",
                          top: "100%",
                          left: 0,
                          right: 0,
                          backgroundColor: "var(--bg-surface-elevated)",
                          border: "1px solid var(--border-subtle)",
                          borderRadius: "0 0 6px 6px",
                          maxHeight: "220px",
                          overflowY: "auto",
                          zIndex: 20,
                          boxShadow: "0 10px 20px rgba(0,0,0,0.5)",
                        }}
                      >
                        {batchSearchResults.map((b) => (
                          <div
                            key={b.id}
                            onClick={() => setSelectedBatchId(b.id)}
                            style={{
                              padding: "8px 12px",
                              cursor: "pointer",
                              borderBottom: "1px solid rgba(255,255,255,0.05)",
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                            }}
                            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "#1e293b")}
                            onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
                          >
                            <div>
                              <strong style={{ color: "#f9fafb" }}>{b.medicine_name || `Medicine #${b.medicine_id}`}</strong>
                              <span style={{ color: "#38bdf8", marginLeft: 8, fontSize: "0.8rem", fontFamily: "var(--font-mono)" }}>
                                Batch {b.batch_number}
                              </span>
                            </div>
                            <div style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
                              Stock: <strong>{b.current_quantity}</strong> units | Exp: {b.expiry_date}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Counts & Delta Comparison Box */}
              <div
                style={{
                  background: "var(--bg-surface-elevated)",
                  borderRadius: 6,
                  padding: "10px 14px",
                  border: "1px solid var(--border-subtle)",
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr 1.2fr",
                  gap: 12,
                  alignItems: "center",
                }}
              >
                <div>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-dim)" }}>System Stock</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: 700, color: "var(--text-main)" }}>
                    {batchDetails ? `${systemQty} units` : "—"}
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-dim)" }}>Physical Count</div>
                  <input
                    ref={physicalQtyInputRef}
                    type="number"
                    min="0"
                    step="1"
                    className="input-field"
                    value={physicalQuantity}
                    onChange={(e) => setPhysicalQuantity(e.target.value)}
                    disabled={!batchDetails}
                    style={{ width: "100%", padding: "4px 8px", fontSize: "1.1rem", fontWeight: 700 }}
                  />
                </div>

                <div>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-dim)" }}>Variance (Delta)</div>
                  <div
                    style={{
                      fontSize: "1.15rem",
                      fontWeight: 700,
                      color: deltaQty === 0 ? "var(--text-muted)" : deltaQty > 0 ? "#10b981" : "#ef4444",
                    }}
                  >
                    {batchDetails && isValidNumber
                      ? `${deltaQty > 0 ? `+${deltaQty}` : deltaQty} units`
                      : "—"}
                  </div>
                  {deltaQty < 0 && estimatedLossPaise > 0 && (
                    <div style={{ fontSize: "0.72rem", color: "#f87171" }}>
                      Loss: {formatRupees(estimatedLossPaise)}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Reason & Mandatory Notes */}
            {batchDetails && (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1.5fr auto", gap: 16, marginTop: 16, alignItems: "flex-end" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: 6 }}>
                    Adjustment Reason <span style={{ color: "var(--accent-danger)" }}>*</span>
                  </label>
                  <select
                    className="input-field"
                    value={reason}
                    onChange={(e) => setReason(e.target.value as StockAdjustmentReason)}
                    style={{ width: "100%", padding: "8px 12px" }}
                  >
                    <option value="AUDIT_CORRECTION">AUDIT_CORRECTION (Counting reconciliation)</option>
                    <option value="BREAKAGE">BREAKAGE (Damaged / Broken vial)</option>
                    <option value="THEFT">THEFT (Unaccounted pilferage)</option>
                    <option value="EXPIRED_SCRAP">EXPIRED_SCRAP (Written off expired)</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: 6 }}>
                    Audit Notes {deltaQty < 0 ? <span style={{ color: "var(--accent-danger)" }}>(Mandatory for loss)</span> : "(Optional)"}
                  </label>
                  <input
                    type="text"
                    className="input-field"
                    placeholder="Provide justification or supervisor remarks..."
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    style={{ width: "100%", padding: "8px 12px" }}
                  />
                </div>

                <div>
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={isSubmittingAudit || deltaQty === 0 || !isValidNumber}
                    style={{ padding: "8px 20px", height: "40px" }}
                  >
                    {isSubmittingAudit ? "Committing..." : "Commit Audit"}
                  </button>
                </div>
              </div>
            )}
          </form>
        </div>
      )}

      {/* 3. Bottom Half: Audit History Table */}
      <div className="pos-panel" style={{ padding: "16px 20px", flex: 1, display: "flex", flexDirection: "column" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12, flexWrap: "wrap", gap: 10 }}>
          <h3 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-main)", margin: 0 }}>
            Audit Log & Adjustment History ({totalAudits} entries)
          </h3>

          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <input
              type="text"
              className="input-field"
              placeholder="Search audit #, medicine, batch..."
              value={historySearch}
              onChange={(e) => {
                setHistorySearch(e.target.value);
                setPage(1);
              }}
              style={{ width: "240px", padding: "6px 10px", fontSize: "0.82rem" }}
            />

            <select
              className="input-field"
              value={historyReasonFilter}
              onChange={(e) => {
                setHistoryReasonFilter(e.target.value);
                setPage(1);
              }}
              style={{ padding: "6px 10px", fontSize: "0.82rem" }}
            >
              <option value="">All Reasons</option>
              <option value="AUDIT_CORRECTION">AUDIT_CORRECTION</option>
              <option value="BREAKAGE">BREAKAGE</option>
              <option value="THEFT">THEFT</option>
              <option value="EXPIRED_SCRAP">EXPIRED_SCRAP</option>
            </select>
          </div>
        </div>

        {/* Audit Table */}
        <div style={{ flex: 1, overflowX: "auto" }}>
          <table className="table" style={{ width: "100%", fontSize: "0.82rem" }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left" }}>Audit Ref #</th>
                <th style={{ textAlign: "left" }}>Date & Time</th>
                <th style={{ textAlign: "left" }}>Medicine & Batch</th>
                <th style={{ textAlign: "right" }}>System</th>
                <th style={{ textAlign: "right" }}>Physical</th>
                <th style={{ textAlign: "right" }}>Delta</th>
                <th style={{ textAlign: "left" }}>Reason</th>
                <th style={{ textAlign: "right" }}>Estimated Loss</th>
                <th style={{ textAlign: "left" }}>Operator</th>
                <th style={{ textAlign: "left" }}>Notes</th>
              </tr>
            </thead>
            <tbody>
              {isLoadingHistory ? (
                <tr>
                  <td colSpan={10} style={{ textAlign: "center", padding: 24, color: "var(--text-dim)" }}>
                    Loading audit records...
                  </td>
                </tr>
              ) : audits.length === 0 ? (
                <tr>
                  <td colSpan={10} style={{ textAlign: "center", padding: 24, color: "var(--text-dim)" }}>
                    No stock adjustments recorded yet.
                  </td>
                </tr>
              ) : (
                audits.map((a) => (
                  <tr key={a.id}>
                    <td>
                      <strong style={{ color: "#38bdf8", fontFamily: "var(--font-mono)" }}>
                        {a.adjustment_number}
                      </strong>
                    </td>
                    <td style={{ color: "var(--text-muted)", fontSize: "0.78rem" }}>
                      {new Date(a.created_at).toLocaleString("en-IN", {
                        day: "2-digit",
                        month: "short",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </td>
                    <td>
                      <div>
                        <strong>{a.medicine_name}</strong>
                      </div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>
                        Batch: <span style={{ fontFamily: "var(--font-mono)" }}>{a.batch_number}</span> (Pack {a.pack_size})
                      </div>
                    </td>
                    <td style={{ textAlign: "right" }}>{a.system_quantity}</td>
                    <td style={{ textAlign: "right" }}>{a.physical_quantity}</td>
                    <td
                      style={{
                        textAlign: "right",
                        fontWeight: 700,
                        color: a.delta_quantity > 0 ? "#10b981" : "#ef4444",
                      }}
                    >
                      {a.delta_quantity > 0 ? `+${a.delta_quantity}` : a.delta_quantity}
                    </td>
                    <td>
                      <span
                        style={{
                          fontSize: "0.72rem",
                          padding: "2px 6px",
                          borderRadius: 4,
                          fontWeight: 600,
                          backgroundColor:
                            a.reason === "AUDIT_CORRECTION"
                              ? "rgba(2, 132, 199, 0.15)"
                              : a.reason === "EXPIRED_SCRAP"
                              ? "rgba(239, 68, 68, 0.15)"
                              : "rgba(245, 158, 11, 0.15)",
                          color:
                            a.reason === "AUDIT_CORRECTION"
                              ? "#38bdf8"
                              : a.reason === "EXPIRED_SCRAP"
                              ? "#f87171"
                              : "#fbbf24",
                        }}
                      >
                        {a.reason}
                      </span>
                    </td>
                    <td style={{ textAlign: "right", color: a.estimated_loss_paise > 0 ? "#f87171" : "var(--text-dim)" }}>
                      {a.estimated_loss_paise > 0 ? formatRupees(a.estimated_loss_paise) : "₹0.00"}
                    </td>
                    <td style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
                      {a.username || `User #${a.user_id}`}
                    </td>
                    <td style={{ fontSize: "0.78rem", color: "var(--text-muted)", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={a.notes || ""}>
                      {a.notes || "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <PaginationBar
          page={page}
          pageSize={pageSize}
          total={totalAudits}
          totalPages={totalPages}
          onPageChange={setPage}
          onPageSizeChange={(newSize) => {
            setPageSize(newSize);
            setPage(1);
          }}
        />
      </div>
    </div>
  );
};
