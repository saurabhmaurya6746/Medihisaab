import React, { useState, useEffect } from "react";
import type {
  InvoiceForReturnLookup,
  InvoiceReturnableItem,
  SalesReturn,
  SalesReturnRefundMode,
} from "@pharmacy/api-contracts";
import { formatRupees } from "@pharmacy/api-contracts";
import * as returnsApi from "../api/returns";
import { PaginationBar } from "./PaginationBar";

export const SalesReturnView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"new_return" | "history">("new_return");
  const [invoiceQuery, setInvoiceQuery] = useState<string>("");
  const [invoiceLookup, setInvoiceLookup] = useState<InvoiceForReturnLookup | null>(null);
  const [isSearching, setIsSearching] = useState<boolean>(false);
  const [lookupError, setLookupError] = useState<string | null>(null);

  // Return form state
  interface ReturnItemDraft {
    item: InvoiceReturnableItem;
    returnUnits: number;
    isResellable: boolean;
  }
  const [draftItems, setDraftItems] = useState<ReturnItemDraft[]>([]);
  const [refundMode, setRefundMode] = useState<SalesReturnRefundMode>("CASH");
  const [reason, setReason] = useState<string>("Customer requested return");
  const [notes, setNotes] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [completedReturn, setCompletedReturn] = useState<SalesReturn | null>(null);

  // History state
  const [historyItems, setHistoryItems] = useState<SalesReturn[]>([]);
  const [historyPage, setHistoryPage] = useState<number>(1);
  const [historyTotalPages, setHistoryTotalPages] = useState<number>(1);
  const [historyTotal, setHistoryTotal] = useState<number>(0);
  const [historySearch, setHistorySearch] = useState<string>("");

  const handleLookup = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!invoiceQuery.trim()) return;

    setIsSearching(true);
    setLookupError(null);
    setCompletedReturn(null);
    try {
      const data = await returnsApi.lookupSaleInvoiceForReturn(invoiceQuery.trim());
      setInvoiceLookup(data);
      // Initialize draft return items
      setDraftItems(
        data.items.map((it: InvoiceReturnableItem) => ({
          item: it,
          returnUnits: 0,
          isResellable: !it.is_expired,
        }))
      );
    } catch (err: any) {
      setInvoiceLookup(null);
      setLookupError(err?.message || "Invoice not found or could not be loaded.");
    } finally {
      setIsSearching(false);
    }
  };

  const handleUnitsChange = (index: number, units: number) => {
    setDraftItems((prev) => {
      const copy = [...prev];
      const maxUnits = copy[index].item.returnable_quantity_units;
      const validUnits = Math.max(0, Math.min(units, maxUnits));
      copy[index] = { ...copy[index], returnUnits: validUnits };
      return copy;
    });
  };

  const handleResellableToggle = (index: number, val: boolean) => {
    setDraftItems((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], isResellable: val };
      return copy;
    });
  };

  // Calculate total refund
  const totalRefundPaise = draftItems.reduce((acc, d) => {
    if (d.returnUnits <= 0) return acc;
    // Pro-rata unit rate calculation
    const effectiveRate = d.item.unit_rate_paise;
    const lineDiscount = Math.round((effectiveRate * d.item.discount_percent) / 100);
    const lineNet = effectiveRate - lineDiscount;
    const gstPaise = Math.round((lineNet * d.item.gst_rate) / 100);
    return acc + (lineNet + gstPaise) * d.returnUnits;
  }, 0);

  const handleSubmitReturn = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!invoiceLookup) return;

    const returnable = draftItems.filter((d) => d.returnUnits > 0);
    if (returnable.length === 0) {
      setSubmitError("Please enter return quantity for at least one item.");
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const payload = {
        sale_invoice_id: invoiceLookup.invoice_id,
        refund_mode: refundMode,
        reason: reason.trim(),
        notes: notes.trim() || undefined,
        items: returnable.map((d) => ({
          sale_item_id: d.item.sale_item_id,
          quantity_units: d.returnUnits,
          is_resellable: d.isResellable,
        })),
      };

      const result = await returnsApi.processSalesReturn(payload);
      setCompletedReturn(result);
      setInvoiceLookup(null);
      setInvoiceQuery("");
    } catch (err: any) {
      setSubmitError(err?.message || "Failed to process customer return.");
    } finally {
      setIsSubmitting(false);
    }
  };

  // Load history
  const loadHistory = async (page = 1) => {
    try {
      const res = await returnsApi.listSalesReturns({
        page,
        page_size: 15,
        query: historySearch.trim() || undefined,
      });
      setHistoryItems(res.items);
      setHistoryTotal(res.total);
      setHistoryTotalPages(res.total_pages);
    } catch (err) {
      console.error("Failed to load return history:", err);
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
              <polyline points="9 14 4 9 9 4" />
              <path d="M20 20v-7a4 4 0 0 0-4-4H4" />
            </svg>
          </div>
          <div>
            <h1 className="pos-page-title">
              <span>Sales Returns</span>
            </h1>
            <p className="pos-page-subtitle">
              Process customer returns and issue refunds or credit notes.
            </p>
          </div>
        </div>

        <div className="pos-page-actions">
          <div className="pos-subnav-strip">
            <button
              type="button"
              onClick={() => {
                setActiveTab("new_return");
                setCompletedReturn(null);
              }}
              className={`pos-subnav-btn ${activeTab === "new_return" ? "active" : ""}`}
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

      {/* 2. Main Content */}
      {activeTab === "new_return" ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 14, maxWidth: 960, margin: "0 auto", width: "100%" }}>
          {completedReturn ? (
            /* Success / Voucher View */
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
                    Sales Return Credit Note Generated Successfully
                  </h2>
                  <p style={{ fontSize: "0.82rem", color: "var(--text-muted)", margin: "2px 0 0" }}>
                    Credit Note #{completedReturn.return_number} (Ref: Invoice #{completedReturn.invoice_no})
                  </p>
                </div>
              </div>

              <div className="voucher-receipt-box">
                <div className="voucher-line">
                  <span style={{ color: "var(--text-muted)" }}>Customer:</span>
                  <span style={{ color: "#ffffff", fontWeight: 700 }}>{completedReturn.customer_name || "Walk-in Customer"}</span>
                </div>
                <div className="voucher-line">
                  <span style={{ color: "var(--text-muted)" }}>Refund Settlement Mode:</span>
                  <span className="pill-badge pill-active">{completedReturn.refund_mode}</span>
                </div>
                <div className="voucher-line">
                  <span style={{ color: "var(--text-muted)" }}>Total Refund Amount:</span>
                  <span style={{ color: "#34d399", fontWeight: 800, fontSize: "1.2rem" }}>
                    ₹{formatRupees(completedReturn.refund_amount_paise)}
                  </span>
                </div>
                <div className="voucher-line">
                  <span style={{ color: "var(--text-muted)" }}>Return Reason:</span>
                  <span style={{ color: "var(--text-main)" }}>{completedReturn.reason}</span>
                </div>
                <div className="voucher-line">
                  <span style={{ color: "var(--text-muted)" }}>Generated At:</span>
                  <span>{new Date(completedReturn.created_at).toLocaleString()}</span>
                </div>

                <div className="voucher-divider" />
                <div style={{ fontWeight: 700, color: "var(--text-muted)", fontSize: "0.78rem" }}>
                  Items Credited:
                </div>
                {completedReturn.items.map((it) => (
                  <div key={it.id} className="voucher-line" style={{ paddingLeft: 8 }}>
                    <span>
                      {it.medicine_name} <span style={{ color: "var(--text-dim)" }}>(Batch: {it.batch_number})</span> &times; {it.quantity_units} units
                    </span>
                    <span style={{ color: "#ffffff", fontWeight: 700 }}>₹{formatRupees(it.total_amount_paise)}</span>
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
                  <span>Print Credit Note</span>
                </button>
                <button
                  type="button"
                  onClick={() => setCompletedReturn(null)}
                  className="btn btn-primary"
                >
                  + Create Another Return
                </button>
              </div>
            </div>
          ) : (
            <>
              {/* Step 1: Invoice Lookup Card */}
              <div className="pos-step-card">
                <div className="pos-step-header">
                  <h2 className="pos-step-title">
                    <span className="pos-step-num">1</span>
                    <span>Look Up Original Sale Invoice</span>
                  </h2>
                  <span style={{ fontSize: "0.76rem", color: "var(--text-dim)" }}>
                    Enter invoice number or ID to inspect items
                  </span>
                </div>
                <div className="pos-step-body">
                  <form onSubmit={handleLookup} className="lookup-form-row">
                    <div style={{ position: "relative", flex: 1 }}>
                      <input
                        type="text"
                        className="form-input"
                        placeholder="Enter Invoice Number (e.g. INV-2026-0000001, INV/2026-27/00001) or Invoice ID..."
                        value={invoiceQuery}
                        onChange={(e) => setInvoiceQuery(e.target.value)}
                        aria-label="Sale invoice number"
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
                      <span>{isSearching ? "Searching..." : "Lookup Invoice"}</span>
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

              {/* Step 2 & 3 & 4 (Rendered once invoice is found) */}
              {invoiceLookup && (
                <form onSubmit={handleSubmitReturn} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  {/* Step 2: Invoice Details Card */}
                  <div className="pos-step-card">
                    <div className="pos-step-header">
                      <h2 className="pos-step-title">
                        <span className="pos-step-num">2</span>
                        <span>Original Invoice Details</span>
                      </h2>
                      <span className="pill-badge pill-active">VERIFIED INVOICE</span>
                    </div>
                    <div className="pos-step-body" style={{ padding: 12 }}>
                      <div className="meta-summary-grid">
                        <div className="meta-stat-item">
                          <span className="meta-stat-label">Invoice Number</span>
                          <span className="meta-stat-val col-code">{invoiceLookup.invoice_no}</span>
                        </div>
                        <div className="meta-stat-item">
                          <span className="meta-stat-label">Customer Name</span>
                          <span className="meta-stat-val" style={{ color: "#34d399" }}>
                            {invoiceLookup.customer_name || "Walk-in Customer"}
                          </span>
                        </div>
                        <div className="meta-stat-item">
                          <span className="meta-stat-label">Original Grand Total</span>
                          <span className="meta-stat-val">₹{formatRupees(invoiceLookup.grand_total_paise)}</span>
                        </div>
                        <div className="meta-stat-item">
                          <span className="meta-stat-label">Original Payment Mode</span>
                          <span className="meta-stat-val" style={{ color: "var(--text-muted)" }}>
                            {invoiceLookup.payment_mode}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Step 3: Return Item Selection Table */}
                  <div className="pos-step-card">
                    <div className="pos-step-header">
                      <h2 className="pos-step-title">
                        <span className="pos-step-num">3</span>
                        <span>Select Items and Quantities to Return</span>
                      </h2>
                      <span style={{ fontSize: "0.76rem", color: "var(--text-dim)" }}>
                        Enter return units for desired line items
                      </span>
                    </div>
                    <div className="table-responsive-wrapper">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Medicine</th>
                            <th style={{ width: "160px" }}>Batch & Expiry</th>
                            <th style={{ width: "100px", textAlign: "right" }}>Sold</th>
                            <th style={{ width: "110px", textAlign: "right" }}>Returned</th>
                            <th style={{ width: "130px", textAlign: "right" }}>Returnable</th>
                            <th style={{ width: "120px", textAlign: "center" }}>Return Qty</th>
                            <th style={{ width: "120px", textAlign: "center" }}>Resellable?</th>
                          </tr>
                        </thead>
                        <tbody>
                          {draftItems.map((d, index) => {
                            const isAvailable = d.item.returnable_quantity_units > 0;
                            return (
                              <tr
                                key={d.item.sale_item_id}
                                className={!isAvailable ? "inactive-row" : ""}
                              >
                                <td>
                                  <div className="col-name">{d.item.medicine_name}</div>
                                  <div className="col-subtext">Unit Rate: ₹{formatRupees(d.item.unit_rate_paise)}</div>
                                </td>
                                <td>
                                  <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.82rem" }}>
                                    {d.item.batch_number}
                                  </div>
                                  <div style={{ fontSize: "0.74rem", color: "var(--text-dim)" }}>
                                    Exp: {d.item.expiry_date}
                                    {d.item.is_expired && (
                                      <span className="badge badge-danger" style={{ marginLeft: 4 }}>
                                        EXPIRED
                                      </span>
                                    )}
                                  </div>
                                </td>
                                <td className="col-amount" style={{ color: "var(--text-muted)" }}>
                                  {d.item.sold_quantity_units}
                                </td>
                                <td className="col-amount" style={{ color: "var(--text-muted)" }}>
                                  {d.item.previously_returned_units}
                                </td>
                                <td className="col-amount" style={{ color: "#34d399", fontWeight: 700 }}>
                                  {d.item.returnable_quantity_units}
                                </td>
                                <td style={{ textAlign: "center" }}>
                                  <input
                                    type="number"
                                    min="0"
                                    max={d.item.returnable_quantity_units}
                                    value={d.returnUnits}
                                    disabled={!isAvailable}
                                    onChange={(e) => handleUnitsChange(index, parseInt(e.target.value, 10) || 0)}
                                    className="grid-qty-input"
                                    aria-label={`Return units for ${d.item.medicine_name}`}
                                  />
                                </td>
                                <td style={{ textAlign: "center" }}>
                                  <label style={{ display: "inline-flex", alignItems: "center", gap: 6, cursor: d.item.is_expired ? "not-allowed" : "pointer" }}>
                                    <input
                                      type="checkbox"
                                      checked={d.isResellable}
                                      disabled={d.item.is_expired}
                                      onChange={(e) => handleResellableToggle(index, e.target.checked)}
                                      style={{ accentColor: "var(--accent-primary)", width: 16, height: 16 }}
                                    />
                                    <span style={{ fontSize: "0.78rem", color: d.item.is_expired ? "var(--accent-danger)" : "var(--text-muted)" }}>
                                      {d.item.is_expired ? "Auto-Scrap" : "Restock"}
                                    </span>
                                  </label>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Step 4: Refund Options & Confirmation */}
                  <div className="pos-step-card">
                    <div className="pos-step-header">
                      <h2 className="pos-step-title">
                        <span className="pos-step-num">4</span>
                        <span>Refund Settlement & Credit Note Action</span>
                      </h2>
                      <span style={{ fontSize: "0.76rem", color: "var(--text-dim)" }}>
                        Select disbursement mode and provide reason
                      </span>
                    </div>
                    <div className="pos-step-body" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                        <div className="form-group" style={{ margin: 0 }}>
                          <label className="form-label form-label-required">
                            Refund Mode
                          </label>
                          <div className="mode-pill-grid">
                            {(["CASH", "UPI", "CARD", "KHATA", "STORE_CREDIT"] as SalesReturnRefundMode[]).map(
                              (mode) => (
                                <button
                                  key={mode}
                                  type="button"
                                  onClick={() => setRefundMode(mode)}
                                  className={`mode-pill-btn ${refundMode === mode ? "active" : ""}`}
                                >
                                  {mode}
                                </button>
                              )
                            )}
                          </div>
                        </div>

                        <div className="form-group" style={{ margin: 0 }}>
                          <label className="form-label form-label-required">
                            Return Reason
                          </label>
                          <input
                            type="text"
                            required
                            className="form-input"
                            placeholder="e.g. Doctor changed prescription / Wrong pack"
                            value={reason}
                            onChange={(e) => setReason(e.target.value)}
                          />
                        </div>
                      </div>

                      <div className="form-group" style={{ margin: 0 }}>
                        <label className="form-label">
                          Additional Remarks / Notes (Optional)
                        </label>
                        <input
                          type="text"
                          className="form-input"
                          placeholder="e.g. Customer brought receipt; seal intact"
                          value={notes}
                          onChange={(e) => setNotes(e.target.value)}
                        />
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
                            Total Refund Amount:
                          </span>
                          <span className="total-refund-amount">
                            ₹{formatRupees(totalRefundPaise)}
                          </span>
                        </div>

                        <button
                          type="submit"
                          disabled={isSubmitting || totalRefundPaise <= 0}
                          className="btn btn-success"
                          style={{ padding: "9px 20px", fontSize: "0.92rem" }}
                        >
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <polyline points="20 6 9 17 4 12" />
                          </svg>
                          <span>{isSubmitting ? "Processing..." : "Process Return (Issue Credit Note)"}</span>
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
                  placeholder="Search by Credit Note #, Invoice #, or Customer..."
                  value={historySearch}
                  onChange={(e) => setHistorySearch(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && loadHistory(1)}
                  aria-label="Search credit notes history"
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
                title="Refresh Credit Notes"
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
                    <th style={{ width: "160px" }}>Credit Note #</th>
                    <th style={{ width: "160px" }}>Orig. Invoice</th>
                    <th>Customer</th>
                    <th style={{ width: "130px" }}>Refund Mode</th>
                    <th style={{ width: "130px", textAlign: "right" }}>Amount (₹)</th>
                    <th>Reason</th>
                    <th style={{ width: "130px" }}>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {historyItems.length === 0 ? (
                    <tr>
                      <td colSpan={7}>
                        <div className="table-empty-state">
                          <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                            <polyline points="9 14 4 9 9 4" />
                            <path d="M20 20v-7a4 4 0 0 0-4-4H4" />
                          </svg>
                          <strong style={{ color: "#ffffff", fontSize: "1rem" }}>
                            {historySearch ? "No matching credit notes found" : "No customer credit notes recorded"}
                          </strong>
                          <p style={{ fontSize: "0.82rem", marginTop: 4, maxWidth: 440 }}>
                            {historySearch
                              ? `No credit note records matched query "${historySearch}". Clear search to view all.`
                              : "No sales return credit notes have been processed yet. Process returns against original sales invoices to generate credit vouchers."}
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
                                onClick={() => setActiveTab("new_return")}
                              >
                                + Create First Sales Return
                              </button>
                            )}
                          </div>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    historyItems.map((sr) => (
                      <tr key={sr.id}>
                        <td className="col-code" style={{ color: "#34d399" }}>
                          {sr.return_number}
                        </td>
                        <td className="col-code">
                          {sr.invoice_no}
                        </td>
                        <td className="col-name">
                          {sr.customer_name || "Walk-in Customer"}
                        </td>
                        <td>
                          <span className="pill-badge pill-dosage">
                            {sr.refund_mode}
                          </span>
                        </td>
                        <td className="col-amount" style={{ color: "#34d399", fontWeight: 700 }}>
                          ₹{formatRupees(sr.refund_amount_paise)}
                        </td>
                        <td style={{ color: "var(--text-muted)", fontSize: "0.82rem" }}>
                          {sr.reason}
                        </td>
                        <td style={{ color: "var(--text-dim)", fontSize: "0.8rem", whiteSpace: "nowrap" }}>
                          {new Date(sr.created_at).toLocaleDateString("en-IN", {
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
