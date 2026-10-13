import React, { useState, useEffect, useCallback } from "react";
import type {
  Customer,
  CustomerAgingReport,
  KhataLedgerEntry,
  CustomerDepositReceipt,
} from "@pharmacy/api-contracts";
import { formatRupees } from "@pharmacy/api-contracts";
import * as khataApi from "../api/khata";
import * as mastersApi from "../api/masters";
import { QuickCustomerDepositModal } from "./pos/QuickCustomerDepositModal";
import { PaginationBar } from "./PaginationBar";

export const CustomerKhataView: React.FC = () => {
  const [agingReport, setAgingReport] = useState<CustomerAgingReport | null>(null);
  const [selectedCustomerId, setSelectedCustomerId] = useState<number | null>(null);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [ledgerEntries, setLedgerEntries] = useState<KhataLedgerEntry[]>([]);
  const [ledgerPage, setLedgerPage] = useState<number>(1);
  const [ledgerTotalPages, setLedgerTotalPages] = useState<number>(1);
  const [ledgerTotal, setLedgerTotal] = useState<number>(0);

  const [activeTab, setActiveTab] = useState<"aging" | "ledger">("aging");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Quick Deposit Modal state
  const [isDepositModalOpen, setIsDepositModalOpen] = useState<boolean>(false);
  const [depositTargetCustomer, setDepositTargetCustomer] = useState<Customer | null>(null);

  // Load aging summary
  const loadAgingReport = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await khataApi.getCustomerAging();
      setAgingReport(data);
    } catch (err: any) {
      setError(err?.message || "Failed to load Khata aging report.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAgingReport();
  }, [loadAgingReport]);

  // Load customer ledger entries
  const loadCustomerLedger = useCallback(async (customerId: number, page: number = 1) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await khataApi.getCustomerKhata(customerId, { page, page_size: 15 });
      setLedgerEntries(res.items);
      setLedgerTotalPages(res.total_pages);
      setLedgerTotal(res.total);
    } catch (err: any) {
      setError(err?.message || "Failed to load customer ledger.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleSelectCustomer = async (cId: number) => {
    setSelectedCustomerId(cId);
    setActiveTab("ledger");
    setLedgerPage(1);

    // Fetch customer profile
    try {
      const cust = await mastersApi.getCustomer(cId);
      setSelectedCustomer(cust);
    } catch (err) {
      console.error("Failed to load customer profile:", err);
    }

    loadCustomerLedger(cId, 1);
  };

  const handleOpenDepositModal = (customer?: Customer | null) => {
    setDepositTargetCustomer(customer || selectedCustomer || null);
    setIsDepositModalOpen(true);
  };

  const handleDepositSuccess = (_receipt: CustomerDepositReceipt) => {
    loadAgingReport();
    if (selectedCustomerId) {
      loadCustomerLedger(selectedCustomerId, ledgerPage);
      mastersApi.getCustomer(selectedCustomerId).then(setSelectedCustomer).catch(console.error);
    }
  };

  // Keyboard shortcut Ctrl+K to open deposit modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.key.toLowerCase() === "k") {
        e.preventDefault();
        handleOpenDepositModal();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedCustomer]);

  const filteredAgingCustomers = agingReport?.customers.filter((c) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return c.customer_name.toLowerCase().includes(q) || (c.customer_phone && c.customer_phone.includes(q));
  }) || [];

  return (
    <div className="pos-page-shell">
      {/* 1. Page Header */}
      <div className="pos-page-header">
        <div className="pos-page-header-info">
          <div className="pos-page-icon-badge">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
              <line x1="8" y1="6" x2="16" y2="6" />
              <line x1="8" y1="10" x2="14" y2="10" />
            </svg>
          </div>
          <div>
            <h1 className="pos-page-title">
              <span>Customer Khata</span>
            </h1>
            <p className="pos-page-subtitle">
              Track customer credit and payments
            </p>
          </div>
        </div>

        <div className="pos-page-actions">
          {/* Sub-Nav Tabs */}
          <div className="pos-subnav-strip">
            <button
              type="button"
              onClick={() => setActiveTab("aging")}
              className={`pos-subnav-btn ${activeTab === "aging" ? "active" : ""}`}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <line x1="3" y1="9" x2="21" y2="9" />
                <line x1="9" y1="21" x2="9" y2="9" />
              </svg>
              <span>Overdue Balances</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("ledger")}
              className={`pos-subnav-btn ${activeTab === "ledger" ? "active" : ""}`}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="8" y1="6" x2="21" y2="6" />
                <line x1="8" y1="12" x2="21" y2="12" />
                <line x1="8" y1="18" x2="21" y2="18" />
              </svg>
              <span>Customer Ledger</span>
              {selectedCustomer && (
                <span style={{ marginLeft: 6, fontSize: "0.78rem", color: "var(--accent-primary)" }}>
                  ({selectedCustomer.name})
                </span>
              )}
            </button>
          </div>

          <button
            type="button"
            onClick={() => handleOpenDepositModal(selectedCustomer)}
            className="btn btn-primary"
            title="Record Customer Payment or Deposit (Ctrl+K)"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="2" y="5" width="20" height="14" rx="2" />
              <line x1="2" y1="10" x2="22" y2="10" />
            </svg>
            <span>Record Deposit</span>
          </button>
        </div>
      </div>

      {/* Global Error Banner */}
      {error && (
        <div className="pos-alert pos-alert-error" role="alert">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <span style={{ flex: 1 }}>{error}</span>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setError(null)}
            aria-label="Dismiss error"
          >
            ✕
          </button>
        </div>
      )}

      {/* 2. Summary KPI Cards */}
      {agingReport && (
        <div className="kpi-grid">
          <div className="kpi-card">
            <div className="kpi-card-label">Total outstanding</div>
            <div className="kpi-card-value">₹{formatRupees(agingReport.total_outstanding_paise)}</div>
            <div className="kpi-card-sub">
              Across {agingReport.total_customers} customer account{agingReport.total_customers === 1 ? "" : "s"}
            </div>
          </div>

          <div className="kpi-card">
            <div className="kpi-card-label">Current</div>
            <div className="kpi-card-value" style={{ color: "var(--accent-success)" }}>
              ₹{formatRupees(agingReport.total_0_30_paise)}
            </div>
            <div className="kpi-card-sub">Up to 30 days</div>
          </div>

          <div className="kpi-card">
            <div className="kpi-card-label">31–60 days overdue</div>
            <div className="kpi-card-value" style={{ color: "var(--accent-warning)" }}>
              ₹{formatRupees(agingReport.total_31_60_paise)}
            </div>
            <div className="kpi-card-sub">Due for payment</div>
          </div>

          <div className="kpi-card">
            <div className="kpi-card-label">60+ days overdue</div>
            <div className="kpi-card-value" style={{ color: "var(--accent-danger)" }}>
              ₹{formatRupees(agingReport.total_60_plus_paise)}
            </div>
            <div className="kpi-card-sub" style={{ color: "var(--accent-danger)", fontWeight: 600 }}>
              Requires follow-up
            </div>
          </div>
        </div>
      )}

      {/* 3. Main Content Tab Views */}
      {activeTab === "aging" ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 12, flex: 1, minHeight: 0 }}>
          {/* Toolbar */}
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
                  placeholder="Search accounts by customer name or phone..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  aria-label="Search Khata customers"
                />
                {searchQuery && (
                  <button
                    type="button"
                    className="search-clear-btn"
                    onClick={() => setSearchQuery("")}
                    title="Clear search"
                  >
                    ✕
                  </button>
                )}
              </div>
            </div>

            <div className="toolbar-right">
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={loadAgingReport}
                disabled={isLoading}
                title="Refresh accounts"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
                </svg>
                <span>{isLoading ? "Refreshing..." : "Refresh"}</span>
              </button>
            </div>
          </div>

          {/* Aging Table Card */}
          <div className="data-table-card">
            <div className="table-responsive-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Customer Name</th>
                    <th style={{ width: "130px" }}>Phone</th>
                    <th style={{ width: "120px", textAlign: "right" }}>Credit Limit</th>
                    <th style={{ width: "120px", textAlign: "right" }}>Current</th>
                    <th style={{ width: "120px", textAlign: "right" }}>31–60 Days</th>
                    <th style={{ width: "120px", textAlign: "right" }}>60+ Days</th>
                    <th style={{ width: "140px", textAlign: "right" }}>Total Balance</th>
                    <th style={{ width: "160px", textAlign: "center" }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {isLoading && (!agingReport || agingReport.customers.length === 0) ? (
                    <tr>
                      <td colSpan={8}>
                        <div className="table-loading-overlay">
                          <span className="pulse-dot healthy" />
                          <span>Loading customer accounts...</span>
                        </div>
                      </td>
                    </tr>
                  ) : filteredAgingCustomers.length === 0 ? (
                    <tr>
                      <td colSpan={8}>
                        <div className="table-empty-state">
                          <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                            <circle cx="12" cy="12" r="10" />
                            <line x1="8" y1="12" x2="16" y2="12" />
                          </svg>
                          <strong style={{ color: "var(--text-title)", fontSize: "1rem" }}>
                            {searchQuery ? "No matching accounts found" : "No outstanding customer accounts"}
                          </strong>
                          <p style={{ fontSize: "0.82rem", marginTop: 4, maxWidth: 440 }}>
                            {searchQuery
                              ? `No customer credit accounts matched "${searchQuery}". Clear query to see all accounts.`
                              : "All customer credit accounts are clear with zero balance."}
                          </p>
                          <div style={{ marginTop: 14 }}>
                            {searchQuery ? (
                              <button
                                type="button"
                                className="btn btn-secondary btn-sm"
                                onClick={() => setSearchQuery("")}
                              >
                                Clear Search
                              </button>
                            ) : (
                              <button
                                type="button"
                                className="btn btn-primary btn-sm"
                                onClick={() => handleOpenDepositModal()}
                              >
                                + Record Advance Deposit
                              </button>
                            )}
                          </div>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    filteredAgingCustomers.map((c) => (
                      <tr key={c.customer_id}>
                        <td className="col-name">
                          <div>{c.customer_name}</div>
                          <div className="col-subtext">ID: #{c.customer_id}</div>
                        </td>
                        <td style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                          {c.customer_phone || "—"}
                        </td>
                        <td className="col-amount" style={{ color: "var(--text-muted)" }}>
                          ₹{formatRupees(c.credit_limit_paise)}
                        </td>
                        <td className="col-amount" style={{ color: "var(--accent-success)" }}>
                          ₹{formatRupees(c.bucket_0_30_paise)}
                        </td>
                        <td className="col-amount" style={{ color: "var(--accent-warning)" }}>
                          ₹{formatRupees(c.bucket_31_60_paise)}
                        </td>
                        <td className="col-amount" style={{ color: "var(--accent-danger)", fontWeight: 700 }}>
                          ₹{formatRupees(c.bucket_60_plus_paise)}
                        </td>
                        <td className="col-amount" style={{ fontWeight: 700, fontSize: "0.92rem" }}>
                          ₹{formatRupees(c.total_outstanding_paise)}
                        </td>
                        <td style={{ textAlign: "center" }}>
                          <div style={{ display: "inline-flex", gap: 6 }}>
                            <button
                              type="button"
                              onClick={() => handleSelectCustomer(c.customer_id)}
                              className="btn btn-secondary btn-sm"
                              title="View Customer Transaction Ledger"
                            >
                              Ledger
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                const matchCust = {
                                  id: c.customer_id,
                                  name: c.customer_name,
                                  phone: c.customer_phone || null,
                                  credit_limit_paise: c.credit_limit_paise,
                                  current_balance_paise: c.total_outstanding_paise,
                                  is_active: true,
                                } as Customer;
                                handleOpenDepositModal(matchCust);
                              }}
                              className="btn btn-secondary btn-sm"
                              title="Record Repayment or Deposit"
                            >
                              Deposit
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : (
        /* Ledger Detail View */
        <div style={{ display: "flex", flexDirection: "column", gap: 12, flex: 1, minHeight: 0 }}>
          {selectedCustomer ? (
            <div className="pos-card" style={{ padding: "14px 18px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <h2 style={{ fontSize: "1.15rem", fontWeight: 700, color: "var(--text-title)", margin: 0 }}>
                      {selectedCustomer.name}
                    </h2>
                    <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>ID #{selectedCustomer.id}</span>
                  </div>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 16,
                      marginTop: 6,
                      fontSize: "0.82rem",
                      color: "var(--text-muted)",
                      flexWrap: "wrap",
                    }}
                  >
                    <span>Phone: <strong style={{ color: "var(--text-main)", fontFamily: "var(--font-mono)" }}>{selectedCustomer.phone || "N/A"}</strong></span>
                    <span>•</span>
                    <span>Credit Limit: <strong style={{ color: "var(--text-main)", fontFamily: "var(--font-mono)" }}>₹{formatRupees(selectedCustomer.credit_limit_paise)}</strong></span>
                    <span>•</span>
                    <span>
                      Current Balance:{" "}
                      <strong style={{ color: "var(--accent-warning)", fontFamily: "var(--font-mono)", fontSize: "0.95rem" }}>
                        ₹{formatRupees(selectedCustomer.current_balance_paise)}
                      </strong>
                    </span>
                  </div>
                </div>

                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <button
                    type="button"
                    onClick={() => setActiveTab("aging")}
                    className="btn btn-secondary btn-sm"
                  >
                    ← Back to Balances
                  </button>
                  <button
                    type="button"
                    onClick={() => handleOpenDepositModal(selectedCustomer)}
                    className="btn btn-primary btn-sm"
                  >
                    + Record Payment
                  </button>
                  <button
                    type="button"
                    onClick={() => window.print()}
                    className="btn btn-secondary btn-sm"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polyline points="6 9 6 2 18 2 18 9" />
                      <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
                      <rect x="6" y="14" width="12" height="8" />
                    </svg>
                    <span>Print Statement</span>
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="pos-card" style={{ padding: "32px 18px", textAlign: "center" }}>
              <div className="table-empty-state">
                <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                  <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
                <strong style={{ color: "var(--text-title)", fontSize: "1rem" }}>No Customer Account Selected</strong>
                <p style={{ fontSize: "0.82rem", marginTop: 4, maxWidth: 440 }}>
                  Select an account from the Balances tab or search above to view itemized transactions.
                </p>
                <button
                  type="button"
                  style={{ marginTop: 14 }}
                  className="btn btn-secondary btn-sm"
                  onClick={() => setActiveTab("aging")}
                >
                  View Customer Balances
                </button>
              </div>
            </div>
          )}

          {selectedCustomer && (
            <div className="data-table-card">
              <div className="table-responsive-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th style={{ width: "160px" }}>Date / Time</th>
                      <th style={{ width: "130px" }}>Transaction</th>
                      <th style={{ width: "100px" }}>Type</th>
                      <th style={{ width: "120px", textAlign: "right" }}>Amount (₹)</th>
                      <th style={{ width: "130px", textAlign: "right" }}>Balance After</th>
                      <th style={{ width: "180px" }}>Ref / Receipt #</th>
                      <th>Notes</th>
                      <th style={{ width: "110px" }}>Operator</th>
                    </tr>
                  </thead>
                  <tbody>
                    {isLoading ? (
                      <tr>
                        <td colSpan={8}>
                          <div className="table-loading-overlay">
                            <span className="pulse-dot healthy" />
                            <span>Loading customer ledger history...</span>
                          </div>
                        </td>
                      </tr>
                    ) : ledgerEntries.length === 0 ? (
                      <tr>
                        <td colSpan={8}>
                          <div className="table-empty-state">
                            <strong style={{ color: "var(--text-title)", fontSize: "0.95rem" }}>No Transactions Recorded</strong>
                            <p style={{ fontSize: "0.82rem", marginTop: 4 }}>
                              No credit sales or deposit vouchers exist for this customer account yet.
                            </p>
                            <button
                              type="button"
                              style={{ marginTop: 12 }}
                              className="btn btn-primary btn-sm"
                              onClick={() => handleOpenDepositModal(selectedCustomer)}
                            >
                              + Record First Deposit
                            </button>
                          </div>
                        </td>
                      </tr>
                    ) : (
                      ledgerEntries.map((e) => (
                        <tr key={e.id}>
                          <td style={{ color: "var(--text-muted)", fontSize: "0.8rem", whiteSpace: "nowrap" }}>
                            {new Date(e.created_at).toLocaleString("en-IN", {
                              day: "2-digit",
                              month: "short",
                              year: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </td>
                          <td>
                            <span style={{ fontSize: "0.78rem", fontWeight: 600 }}>
                              {e.transaction_type === "SALE_CREDIT"
                                ? "Credit Sale"
                                : e.transaction_type === "PAYMENT"
                                ? "Payment"
                                : e.transaction_type === "RETURN_REFUND"
                                ? "Return Refund"
                                : e.transaction_type}
                            </span>
                          </td>
                          <td>
                            <span
                              style={{
                                fontWeight: 700,
                                color: e.entry_type === "DEBIT" ? "var(--accent-warning)" : "var(--accent-success)",
                              }}
                            >
                              {e.entry_type}
                            </span>
                          </td>
                          <td className="col-amount" style={{ color: "var(--text-main)" }}>
                            ₹{formatRupees(e.amount_paise)}
                          </td>
                          <td className="col-amount" style={{ color: "var(--text-muted)" }}>
                            ₹{formatRupees(e.balance_paise)}
                          </td>
                          <td className="col-code">
                            {e.receipt_no || (e.reference_type ? `${e.reference_type} #${e.reference_id || ""}` : "—")}
                          </td>
                          <td style={{ color: "var(--text-dim)", maxWidth: "240px" }}>
                            <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                              {e.notes || "—"}
                            </div>
                          </td>
                          <td style={{ color: "var(--text-dim)", fontSize: "0.8rem" }}>
                            @{e.username || "system"}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {ledgerTotalPages > 1 && (
                <PaginationBar
                  page={ledgerPage}
                  totalPages={ledgerTotalPages}
                  total={ledgerTotal}
                  pageSize={15}
                  onPageChange={(p) => {
                    setLedgerPage(p);
                    if (selectedCustomerId) loadCustomerLedger(selectedCustomerId, p);
                  }}
                />
              )}
            </div>
          )}
        </div>
      )}

      {/* Quick Customer Deposit Modal */}
      <QuickCustomerDepositModal
        isOpen={isDepositModalOpen}
        onClose={() => setIsDepositModalOpen(false)}
        initialCustomer={depositTargetCustomer}
        onSuccess={handleDepositSuccess}
      />
    </div>
  );
};
