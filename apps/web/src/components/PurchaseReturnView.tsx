import React, { useState, useEffect } from "react";
import type {
  PurchaseInvoiceForReturnLookup,
  PurchaseInvoiceReturnableLine,
  PurchaseReturn,
} from "@pharmacy/api-contracts";
import { formatRupees } from "@pharmacy/api-contracts";
import * as returnsApi from "../api/returns";
import { PaginationBar } from "./PaginationBar";

export const PurchaseReturnView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"new_debit_note" | "history">("new_debit_note");
  const [invoiceQuery, setInvoiceQuery] = useState<string>("");
  const [invoiceLookup, setInvoiceLookup] = useState<PurchaseInvoiceForReturnLookup | null>(null);
  const [isSearching, setIsSearching] = useState<boolean>(false);
  const [lookupError, setLookupError] = useState<string | null>(null);

  interface LineReturnDraft {
    line: PurchaseInvoiceReturnableLine;
    returnUnits: number;
  }
  const [draftLines, setDraftLines] = useState<LineReturnDraft[]>([]);
  const [reason, setReason] = useState<string>("Damaged / defective stock from distributor");
  const [notes, setNotes] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [completedDebitNote, setCompletedDebitNote] = useState<PurchaseReturn | null>(null);

  // History state
  const [historyItems, setHistoryItems] = useState<PurchaseReturn[]>([]);
  const [historyPage, setHistoryPage] = useState<number>(1);
  const [historyTotalPages, setHistoryTotalPages] = useState<number>(1);
  const [historyTotal, setHistoryTotal] = useState<number>(0);
  const [historySearch, setHistorySearch] = useState<string>("");

  const handleLookup = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!invoiceQuery.trim()) return;

    setIsSearching(true);
    setLookupError(null);
    setCompletedDebitNote(null);
    try {
      const data = await returnsApi.lookupPurchaseInvoiceForReturn(invoiceQuery.trim());
      setInvoiceLookup(data);
      setDraftLines(
        data.lines.map((l: PurchaseInvoiceReturnableLine) => ({
          line: l,
          returnUnits: 0,
        }))
      );
    } catch (err: any) {
      setInvoiceLookup(null);
      setLookupError(err?.message || "Purchase invoice not found or not in POSTED status.");
    } finally {
      setIsSearching(false);
    }
  };

  const handleUnitsChange = (index: number, units: number) => {
    setDraftLines((prev) => {
      const copy = [...prev];
      const maxAvailable = copy[index].line.available_return_units;
      const maxStock = copy[index].line.current_batch_stock_units;
      const maxAllowed = Math.min(maxAvailable, maxStock);
      const validUnits = Math.max(0, Math.min(units, maxAllowed));
      copy[index] = { ...copy[index], returnUnits: validUnits };
      return copy;
    });
  };

  // Calculate estimated total debit amount
  const totalDebitPaise = draftLines.reduce((acc, d) => {
    if (d.returnUnits <= 0) return acc;
    const l = d.line;
    const unitRate = l.pack_size > 0 ? Math.floor(l.purchase_rate_paise / l.pack_size) : l.purchase_rate_paise;
    const taxable = unitRate * d.returnUnits;
    const tax = Math.round((taxable * l.gst_percentage) / 100);
    return acc + taxable + tax;
  }, 0);

  const handleSubmitDebitNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!invoiceLookup) return;

    const returnable = draftLines.filter((d) => d.returnUnits > 0);
    if (returnable.length === 0) {
      setSubmitError("Please specify return units for at least one line item.");
      return;
    }
    if (!reason.trim()) {
      setSubmitError("Return reason is mandatory.");
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const payload = {
        purchase_invoice_id: invoiceLookup.invoice_id,
        reason: reason.trim(),
        notes: notes.trim() || undefined,
        items: returnable.map((d) => ({
          purchase_invoice_line_id: d.line.purchase_invoice_line_id,
          return_units: d.returnUnits,
          return_packs: d.line.pack_size > 0 ? Math.floor(d.returnUnits / d.line.pack_size) : 0,
        })),
      };

      const result = await returnsApi.processPurchaseReturn(payload);
      setCompletedDebitNote(result);
      setInvoiceLookup(null);
      setInvoiceQuery("");
    } catch (err: any) {
      setSubmitError(err?.message || "Failed to process distributor purchase return.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const loadHistory = async (page = 1) => {
    try {
      const res = await returnsApi.listPurchaseReturns({
        page,
        page_size: 15,
        query: historySearch.trim() || undefined,
      });
      setHistoryItems(res.items);
      setHistoryTotal(res.total);
      setHistoryTotalPages(res.total_pages);
    } catch (err) {
      console.error("Failed to load purchase return history:", err);
    }
  };

  useEffect(() => {
    if (activeTab === "history") {
      loadHistory(historyPage);
    }
  }, [activeTab, historyPage]);

  return (
    <div className="pos-page-shell">
      {/* 1. Header */}
      <div className="pos-page-header">
        <div className="pos-page-header-info">
          <div className="pos-page-icon-badge">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
              <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
              <line x1="12" y1="22.08" x2="12" y2="12" />
            </svg>
          </div>
          <div>
            <h1 className="pos-page-title">
              <span>Purchase Returns</span>
            </h1>
            <p className="pos-page-subtitle">
              Return items to suppliers and update supplier balances.
            </p>
          </div>
        </div>

        <div className="pos-page-actions">
          <div className="pos-subnav-strip">
            <button
              type="button"
              onClick={() => {
                setActiveTab("new_debit_note");
                setCompletedDebitNote(null);
              }}
              className={`pos-subnav-btn ${activeTab === "new_debit_note" ? "active" : ""}`}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              <span>Create Return</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("history")}
              className={`pos-subnav-btn ${activeTab === "history" ? "active" : ""}`}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
              <span>Return History</span>
            </button>
          </div>
        </div>
      </div>

      {/* 2. Main Content Area */}
      {activeTab === "new_debit_note" ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 14, maxWidth: 960, margin: "0 auto", width: "100%" }}>
          {completedDebitNote ? (
            /* Success Debit Voucher Card */
            <div className="voucher-card">
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: "50%",
                    backgroundColor: "rgba(16, 185, 129, 0.15)",
                    border: "1px solid rgba(16, 185, 129, 0.4)",
                    color: "#34d399",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </div>
                <div>
                  <h2 style={{ fontSize: "1.15rem", fontWeight: 700, color: "#ffffff", margin: 0 }}>
                    Distributor Debit Note Created Successfully
                  </h2>
                  <p style={{ fontSize: "0.82rem", color: "var(--text-muted)", margin: "2px 0 0" }}>
                    Debit Note #{completedDebitNote.debit_note_number} (Ref: Invoice #{completedDebitNote.supplier_invoice_number})
                  </p>
                </div>
              </div>

              <div className="voucher-receipt-box">
                <div className="voucher-line">
                  <span style={{ color: "var(--text-muted)" }}>Distributor / Supplier:</span>
                  <span style={{ color: "#ffffff", fontWeight: 700 }}>{completedDebitNote.supplier_name}</span>
                </div>
                <div className="voucher-line">
                  <span style={{ color: "var(--text-muted)" }}>Total Debit Amount:</span>
                  <span style={{ color: "#34d399", fontWeight: 800, fontSize: "1.2rem" }}>
                    ₹{formatRupees(completedDebitNote.total_amount_paise)}
                  </span>
                </div>
                <div className="voucher-line">
                  <span style={{ color: "var(--text-muted)" }}>Debit Reason:</span>
                  <span style={{ color: "var(--text-main)" }}>{completedDebitNote.reason}</span>
                </div>
                <div className="voucher-line">
                  <span style={{ color: "var(--text-muted)" }}>Generated At:</span>
                  <span>{new Date(completedDebitNote.created_at).toLocaleString()}</span>
                </div>

                <div className="voucher-divider" />
                <div style={{ fontWeight: 700, color: "var(--text-muted)", fontSize: "0.78rem" }}>
                  Items Returned to Supplier:
                </div>
                {completedDebitNote.items.map((it) => (
                  <div key={it.id} className="voucher-line" style={{ paddingLeft: 8 }}>
                    <span>
                      {it.medicine_name} <span style={{ color: "var(--text-dim)" }}>(Batch: {it.batch_number})</span> &times; {it.return_units} units
                    </span>
                    <span style={{ color: "#ffffff", fontWeight: 700 }}>₹{formatRupees(it.line_total_paise)}</span>
                  </div>
                ))}
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
                <button
                  type="button"
                  onClick={() => window.print()}
                  className="btn btn-secondary"
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="6 9 6 2 18 2 18 9" />
                    <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
                    <rect x="6" y="14" width="12" height="8" />
                  </svg>
                  <span>Print Debit Note</span>
                </button>
                <button
                  type="button"
                  onClick={() => setCompletedDebitNote(null)}
                  className="btn btn-primary"
                >
                  + Create Another Debit Note
                </button>
              </div>
            </div>
          ) : (
            <>
              {/* Step 1: Look Up Posted Purchase Invoice */}
              <div className="pos-step-card">
                <div className="pos-step-header">
                  <h2 className="pos-step-title">
                    <span className="pos-step-num">1</span>
                    <span>Look Up Posted Purchase Invoice</span>
                  </h2>
                  <span style={{ fontSize: "0.76rem", color: "var(--text-dim)" }}>
                    Enter distributor invoice number or purchase invoice ID
                  </span>
                </div>
                <div className="pos-step-body">
                  <form onSubmit={handleLookup} className="lookup-form-row">
                    <div style={{ position: "relative", flex: 1 }}>
                      <input
                        type="text"
                        className="form-input"
                        placeholder="Enter Supplier Invoice Number or Purchase Invoice ID..."
                        value={invoiceQuery}
                        onChange={(e) => setInvoiceQuery(e.target.value)}
                        aria-label="Purchase invoice lookup"
                        autoFocus
                      />
                    </div>
                    <button
                      type="submit"
                      disabled={isSearching || !invoiceQuery.trim()}
                      className="btn btn-primary"
                      style={{ whiteSpace: "nowrap" }}
                    >
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="11" cy="11" r="8" />
                        <line x1="21" y1="21" x2="16.65" y2="16.65" />
                      </svg>
                      <span>{isSearching ? "Searching..." : "Lookup Purchase"}</span>
                    </button>
                  </form>

                  {lookupError && (
                    <div className="pos-alert pos-alert-error" style={{ marginTop: 12 }}>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="12" cy="12" r="10" />
                        <line x1="12" y1="8" x2="12" y2="12" />
                        <line x1="12" y1="16" x2="12.01" y2="16" />
                      </svg>
                      <span>{lookupError}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Step 2 & 3 & 4 (Rendered once purchase invoice is found) */}
              {invoiceLookup && (
                <form onSubmit={handleSubmitDebitNote} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  {/* Step 2: Invoice Details Card */}
                  <div className="pos-step-card">
                    <div className="pos-step-header">
                      <h2 className="pos-step-title">
                        <span className="pos-step-num">2</span>
                        <span>Distributor Invoice Details</span>
                      </h2>
                      <span className="pill-badge pill-active">POSTED INVOICE</span>
                    </div>
                    <div className="pos-step-body" style={{ padding: 12 }}>
                      <div className="meta-summary-grid">
                        <div className="meta-stat-item">
                          <span className="meta-stat-label">Purchase Invoice</span>
                          <span className="meta-stat-val col-code">{invoiceLookup.supplier_invoice_number}</span>
                        </div>
                        <div className="meta-stat-item">
                          <span className="meta-stat-label">Supplier</span>
                          <span className="meta-stat-val" style={{ color: "#34d399" }}>
                            {invoiceLookup.supplier_name}
                          </span>
                        </div>
                        <div className="meta-stat-item">
                          <span className="meta-stat-label">Current Supplier Payable</span>
                          <span className="meta-stat-val" style={{ color: "#f59e0b" }}>
                            ₹{formatRupees(invoiceLookup.supplier_current_payable_paise)}
                          </span>
                        </div>
                        <div className="meta-stat-item">
                          <span className="meta-stat-label">Invoice Date</span>
                          <span className="meta-stat-val" style={{ color: "var(--text-muted)" }}>
                            {invoiceLookup.invoice_date}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Step 3: Returnable Lines Table */}
                  <div className="pos-step-card">
                    <div className="pos-step-header">
                      <h2 className="pos-step-title">
                        <span className="pos-step-num">3</span>
                        <span>Enter Return Quantities for Distributor</span>
                      </h2>
                      <span style={{ fontSize: "0.76rem", color: "var(--text-dim)" }}>
                        Return units cannot exceed available returnable or on-hand batch stock
                      </span>
                    </div>
                    <div className="table-responsive-wrapper">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Medicine</th>
                            <th style={{ width: "160px" }}>Batch & Expiry</th>
                            <th style={{ width: "110px", textAlign: "right" }}>Inwarded</th>
                            <th style={{ width: "110px", textAlign: "right" }}>Returned</th>
                            <th style={{ width: "120px", textAlign: "right" }}>Available</th>
                            <th style={{ width: "120px", textAlign: "right" }}>On-Hand</th>
                            <th style={{ width: "120px", textAlign: "center" }}>Return Units</th>
                          </tr>
                        </thead>
                        <tbody>
                          {draftLines.map((d, index) => {
                            const maxPossible = Math.min(
                              d.line.available_return_units,
                              d.line.current_batch_stock_units
                            );
                            const isEligible = maxPossible > 0;
                            return (
                              <tr
                                key={d.line.purchase_invoice_line_id}
                                className={!isEligible ? "inactive-row" : ""}
                              >
                                <td>
                                  <div className="col-name">{d.line.medicine_name}</div>
                                  <div className="col-subtext">
                                    Pack Size: {d.line.pack_size} | GST: {d.line.gst_percentage}%
                                  </div>
                                </td>
                                <td>
                                  <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.82rem" }}>
                                    {d.line.batch_number}
                                  </div>
                                  <div style={{ fontSize: "0.74rem", color: "var(--text-dim)" }}>
                                    Exp: {d.line.expiry_date}
                                  </div>
                                </td>
                                <td className="col-amount" style={{ color: "var(--text-muted)" }}>
                                  {d.line.total_received_units}
                                </td>
                                <td className="col-amount" style={{ color: "var(--text-muted)" }}>
                                  {d.line.previously_returned_units}
                                </td>
                                <td className="col-amount" style={{ color: "#34d399", fontWeight: 700 }}>
                                  {d.line.available_return_units}
                                </td>
                                <td className="col-amount" style={{ color: "#f59e0b", fontWeight: 700 }}>
                                  {d.line.current_batch_stock_units}
                                </td>
                                <td style={{ textAlign: "center" }}>
                                  <input
                                    type="number"
                                    min="0"
                                    max={maxPossible}
                                    value={d.returnUnits}
                                    disabled={!isEligible}
                                    onChange={(e) => handleUnitsChange(index, parseInt(e.target.value, 10) || 0)}
                                    className="grid-qty-input"
                                    aria-label={`Return units for ${d.line.medicine_name}`}
                                  />
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Step 4: Reason, Notes & Confirmation */}
                  <div className="pos-step-card">
                    <div className="pos-step-header">
                      <h2 className="pos-step-title">
                        <span className="pos-step-num">4</span>
                        <span>Debit Reason & Submission</span>
                      </h2>
                      <span style={{ fontSize: "0.76rem", color: "var(--text-dim)" }}>
                        Deducts stock from batch and posts debit entry to supplier ledger
                      </span>
                    </div>
                    <div className="pos-step-body" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                        <div className="form-group" style={{ margin: 0 }}>
                          <label className="form-label form-label-required">
                            Debit Note Reason
                          </label>
                          <input
                            type="text"
                            required
                            className="form-input"
                            placeholder="e.g. Broken strips / Short expiry / Distributor recall"
                            value={reason}
                            onChange={(e) => setReason(e.target.value)}
                          />
                        </div>

                        <div className="form-group" style={{ margin: 0 }}>
                          <label className="form-label">
                            Notes / Reference (Optional)
                          </label>
                          <input
                            type="text"
                            className="form-input"
                            placeholder="e.g. Spoke with distributor rep Mr. Sharma"
                            value={notes}
                            onChange={(e) => setNotes(e.target.value)}
                          />
                        </div>
                      </div>

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

                      <div className="summary-submit-bar">
                        <div className="total-refund-callout">
                          <span style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
                            Total Debit Value:
                          </span>
                          <span className="total-refund-amount">
                            ₹{formatRupees(totalDebitPaise)}
                          </span>
                        </div>

                        <button
                          type="submit"
                          disabled={isSubmitting || totalDebitPaise <= 0}
                          className="btn btn-success"
                          style={{ padding: "9px 20px", fontSize: "0.92rem" }}
                        >
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <polyline points="20 6 9 17 4 12" />
                          </svg>
                          <span>{isSubmitting ? "Generating..." : "Generate Debit Note"}</span>
                        </button>
                      </div>
                    </div>
                  </div>
                </form>
              )}
            </>
          )}
        </div>
      ) : (
        /* History View */
        <div style={{ display: "flex", flexDirection: "column", gap: 12, flex: 1, minHeight: 0 }}>
          <div className="master-toolbar">
            <div className="toolbar-left">
              <div className="search-input-wrapper">
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
                  placeholder="Search by Debit Note #, Supplier, or Invoice #..."
                  value={historySearch}
                  onChange={(e) => setHistorySearch(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && loadHistory(1)}
                  aria-label="Search debit notes history"
                />
                {historySearch && (
                  <button
                    type="button"
                    className="search-clear-btn"
                    onClick={() => {
                      setHistorySearch("");
                      loadHistory(1);
                    }}
                    title="Clear search"
                  >
                    ✕
                  </button>
                )}
              </div>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => loadHistory(1)}
              >
                Search
              </button>
            </div>

            <div className="toolbar-right">
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => loadHistory(historyPage)}
                title="Refresh Debit Notes"
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
                    <th style={{ width: "160px" }}>Debit Note #</th>
                    <th style={{ width: "160px" }}>Supplier Invoice</th>
                    <th>Supplier Name</th>
                    <th style={{ width: "130px", textAlign: "right" }}>Amount (₹)</th>
                    <th>Reason</th>
                    <th style={{ width: "130px" }}>Created Date</th>
                  </tr>
                </thead>
                <tbody>
                  {historyItems.length === 0 ? (
                    <tr>
                      <td colSpan={6}>
                        <div className="table-empty-state">
                          <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
                          </svg>
                          <strong style={{ color: "var(--text-title)", fontSize: "1rem" }}>
                            {historySearch ? "No matching returns found" : "No purchase returns recorded"}
                          </strong>
                          <p style={{ fontSize: "0.82rem", marginTop: 4, maxWidth: 440 }}>
                            {historySearch
                              ? `No return records matched "${historySearch}". Clear search to view all.`
                              : "No purchase returns have been posted yet. You can return items against posted purchase invoices to adjust stock and supplier balances."}
                          </p>
                          <div style={{ marginTop: 14 }}>
                            {historySearch ? (
                              <button
                                type="button"
                                className="btn btn-secondary btn-sm"
                                onClick={() => {
                                  setHistorySearch("");
                                  loadHistory(1);
                                }}
                              >
                                Clear Search
                              </button>
                            ) : (
                              <button
                                type="button"
                                className="btn btn-primary btn-sm"
                                onClick={() => setActiveTab("new_debit_note")}
                              >
                                + Create First Debit Note
                              </button>
                            )}
                          </div>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    historyItems.map((dn) => (
                      <tr key={dn.id}>
                        <td className="col-code" style={{ color: "#34d399" }}>
                          {dn.debit_note_number}
                        </td>
                        <td className="col-code">
                          {dn.supplier_invoice_number}
                        </td>
                        <td className="col-name">
                          {dn.supplier_name}
                        </td>
                        <td className="col-amount" style={{ color: "#34d399", fontWeight: 700 }}>
                          ₹{formatRupees(dn.total_amount_paise)}
                        </td>
                        <td style={{ color: "var(--text-muted)", fontSize: "0.82rem" }}>
                          {dn.reason}
                        </td>
                        <td style={{ color: "var(--text-dim)", fontSize: "0.8rem", whiteSpace: "nowrap" }}>
                          {new Date(dn.created_at).toLocaleDateString("en-IN", {
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
