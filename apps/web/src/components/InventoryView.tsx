import React, { useState, useEffect, useCallback } from "react";
import type {
  ExpiryFilterType,
  ExpiryDashboardResponse,
  SupplierReturnDumpGroup,
  LowStockMedicineItem,
  WantBookItem,
  WantBookStatus,
  Supplier,
} from "@pharmacy/api-contracts";
import { formatRupees } from "@pharmacy/api-contracts";
import * as inventoryApi from "../api/inventory";
import * as mastersApi from "../api/masters";
import { PaginationBar } from "./PaginationBar";
import { QuickWantBookModal } from "./pos/QuickWantBookModal";

type InventoryTab = "expiry" | "return_dump" | "want_book";

export const InventoryView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<InventoryTab>("expiry");

  // =========================================================================
  // 1. EXPIRY DASHBOARD STATE
  // =========================================================================
  const [expiryFilter, setExpiryFilter] = useState<ExpiryFilterType>("ALL");
  const [expirySearch, setExpirySearch] = useState<string>("");
  const [expiryData, setExpiryData] = useState<ExpiryDashboardResponse | null>(null);
  const [expiryPage, setExpiryPage] = useState<number>(1);
  const [expiryPageSize, setExpiryPageSize] = useState<number>(20);
  const [isExpiryLoading, setIsExpiryLoading] = useState<boolean>(true);

  // Load Expiry Dashboard
  const loadExpiryDashboard = useCallback(async () => {
    setIsExpiryLoading(true);
    try {
      const resp = await inventoryApi.getExpiryDashboard({
        filter: expiryFilter,
        query: expirySearch.trim() || undefined,
        page: expiryPage,
        page_size: expiryPageSize,
      });
      setExpiryData(resp);
    } catch (err) {
      console.error("Failed to load expiry dashboard:", err);
    } finally {
      setIsExpiryLoading(false);
    }
  }, [expiryFilter, expirySearch, expiryPage, expiryPageSize]);

  useEffect(() => {
    if (activeTab === "expiry") {
      loadExpiryDashboard();
    }
  }, [activeTab, loadExpiryDashboard]);

  // =========================================================================
  // 2. SUPPLIER RETURN DUMP STATE
  // =========================================================================
  const [returnDays, setReturnDays] = useState<number>(60);
  const [returnSupplierId, setReturnSupplierId] = useState<number | undefined>(undefined);
  const [returnDumpGroups, setReturnDumpGroups] = useState<SupplierReturnDumpGroup[]>([]);
  const [allSuppliers, setAllSuppliers] = useState<Supplier[]>([]);
  const [isReturnDumpLoading, setIsReturnDumpLoading] = useState<boolean>(false);

  // Load Return Dump
  const loadReturnDump = useCallback(async () => {
    setIsReturnDumpLoading(true);
    try {
      const data = await inventoryApi.getSupplierReturnDump({
        days: returnDays,
        supplier_id: returnSupplierId,
      });
      setReturnDumpGroups(data);
    } catch (err) {
      console.error("Failed to load return dump:", err);
    } finally {
      setIsReturnDumpLoading(false);
    }
  }, [returnDays, returnSupplierId]);

  useEffect(() => {
    if (activeTab === "return_dump") {
      loadReturnDump();
      mastersApi
        .listSuppliers({ page_size: 100, is_active: true })
        .then((res) => setAllSuppliers(res.items))
        .catch((err) => console.error("Failed to load suppliers for return dump:", err));
    }
  }, [activeTab, loadReturnDump]);

  // =========================================================================
  // 3. WANT-BOOK & LOW-STOCK STATE
  // =========================================================================
  const [wantBookSubTab, setWantBookSubTab] = useState<"low_stock" | "want_list">("low_stock");
  const [lowStockItems, setLowStockItems] = useState<LowStockMedicineItem[]>([]);
  const [isLowStockLoading, setIsLowStockLoading] = useState<boolean>(false);
  const [lowStockSearch, setLowStockSearch] = useState<string>("");

  const [wantBookStatusFilter, setWantBookStatusFilter] = useState<WantBookStatus | "ALL">("ALL");
  const [wantBookItems, setWantBookItems] = useState<WantBookItem[]>([]);
  const [wantBookTotal, setWantBookTotal] = useState<number>(0);
  const [wantBookTotalPages, setWantBookTotalPages] = useState<number>(1);
  const [wantBookPage, setWantBookPage] = useState<number>(1);
  const [wantBookPageSize, setWantBookPageSize] = useState<number>(20);
  const [isWantBookLoading, setIsWantBookLoading] = useState<boolean>(false);

  // Quick Want-Book Modal
  const [showAddWantModal, setShowAddWantModal] = useState<boolean>(false);
  const [targetMedForWant, setTargetMedForWant] = useState<{ id: number; name: string } | null>(null);

  // Load Low Stock
  const loadLowStock = useCallback(async () => {
    setIsLowStockLoading(true);
    try {
      const items = await inventoryApi.getLowStockMedicines({
        query: lowStockSearch.trim() || undefined,
        limit: 100,
      });
      setLowStockItems(items);
    } catch (err) {
      console.error("Failed to load low stock items:", err);
    } finally {
      setIsLowStockLoading(false);
    }
  }, [lowStockSearch]);

  // Load Want-Book List
  const loadWantBookList = useCallback(async () => {
    setIsWantBookLoading(true);
    try {
      const resp = await inventoryApi.listWantBook({
        status: wantBookStatusFilter === "ALL" ? undefined : wantBookStatusFilter,
        page: wantBookPage,
        page_size: wantBookPageSize,
      });
      setWantBookItems(resp.items);
      setWantBookTotal(resp.total);
      setWantBookTotalPages(resp.total_pages);
    } catch (err) {
      console.error("Failed to load want-book list:", err);
    } finally {
      setIsWantBookLoading(false);
    }
  }, [wantBookStatusFilter, wantBookPage, wantBookPageSize]);

  useEffect(() => {
    if (activeTab === "want_book") {
      if (wantBookSubTab === "low_stock") {
        loadLowStock();
      } else {
        loadWantBookList();
      }
    }
  }, [activeTab, wantBookSubTab, loadLowStock, loadWantBookList]);

  const handleUpdateWantStatus = async (id: number, newStatus: WantBookStatus) => {
    try {
      await inventoryApi.updateWantBookStatus(id, { status: newStatus });
      loadWantBookList();
    } catch (err: any) {
      alert(`Failed to update status: ${err.message}`);
    }
  };

  const handleDeleteWantItem = async (id: number) => {
    if (!window.confirm("Remove this entry from Want-Book?")) return;
    try {
      await inventoryApi.deleteWantBookItem(id);
      loadWantBookList();
    } catch (err: any) {
      alert(`Failed to delete item: ${err.message}`);
    }
  };

  const handlePrintReturnDump = () => {
    window.print();
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", gap: 12, overflowY: "auto" }}>
      {/* 1. Header & Sub-Navigation */}
      <div className="pos-panel" style={{ padding: "12px 18px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: "1.25rem", fontWeight: 700, color: "var(--text-main)" }}>
              Inventory & Expiry
            </h2>
            <p style={{ margin: "4px 0 0", fontSize: "0.82rem", color: "var(--text-muted)" }}>
              Monitor stock levels, batch expiry dates, and supplier returns.
            </p>
          </div>

          {/* Sub-Tab Navigation Strip */}
          <div style={{ display: "flex", gap: 6, backgroundColor: "var(--bg-app)", padding: 4, borderRadius: 6 }}>
            <button
              type="button"
              className={`btn btn-sm ${activeTab === "expiry" ? "btn-primary" : "btn-secondary"}`}
              onClick={() => setActiveTab("expiry")}
              style={{ fontWeight: 600 }}
            >
              Expiry
            </button>
            <button
              type="button"
              className={`btn btn-sm ${activeTab === "return_dump" ? "btn-primary" : "btn-secondary"}`}
              onClick={() => setActiveTab("return_dump")}
              style={{ fontWeight: 600 }}
            >
              Supplier Returns
            </button>
            <button
              type="button"
              className={`btn btn-sm ${activeTab === "want_book" ? "btn-primary" : "btn-secondary"}`}
              onClick={() => setActiveTab("want_book")}
              style={{ fontWeight: 600 }}
            >
              Reorder List
            </button>
          </div>
        </div>
      </div>

      {/* =========================================================================
          TAB 1: EXPIRY DASHBOARD
          ========================================================================= */}
      {activeTab === "expiry" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {/* Summary Cards */}
          {expiryData?.summary && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10 }}>
              {/* Expired */}
              <div
                style={{
                  background: "rgba(239, 68, 68, 0.1)",
                  border: "1px solid rgba(239, 68, 68, 0.3)",
                  borderRadius: 6,
                  padding: "10px 14px",
                  cursor: "pointer",
                }}
                onClick={() => {
                  setExpiryFilter("EXPIRED");
                  setExpiryPage(1);
                }}
              >
                <div style={{ fontSize: "0.75rem", color: "#f87171", fontWeight: 700 }}>
                  Expired (Past / Today)
                </div>
                <div style={{ fontSize: "1.4rem", fontWeight: 800, color: "#ef4444", marginTop: 4 }}>
                  {expiryData.summary.expired_count} <span style={{ fontSize: "0.85rem", fontWeight: 400 }}>batches</span>
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 2 }}>
                  Loss: <strong>{formatRupees(expiryData.summary.expired_value_paise)}</strong>
                </div>
              </div>

              {/* Within 30 Days */}
              <div
                style={{
                  background: "rgba(249, 115, 22, 0.1)",
                  border: "1px solid rgba(249, 115, 22, 0.3)",
                  borderRadius: 6,
                  padding: "10px 14px",
                  cursor: "pointer",
                }}
                onClick={() => {
                  setExpiryFilter("WITHIN_30_DAYS");
                  setExpiryPage(1);
                }}
              >
                <div style={{ fontSize: "0.75rem", color: "#fb923c", fontWeight: 700 }}>
                  0 – 30 Days
                </div>
                <div style={{ fontSize: "1.4rem", fontWeight: 800, color: "#f97316", marginTop: 4 }}>
                  {expiryData.summary.within_30_count} <span style={{ fontSize: "0.85rem", fontWeight: 400 }}>batches</span>
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 2 }}>
                  Value: <strong>{formatRupees(expiryData.summary.within_30_value_paise)}</strong>
                </div>
              </div>

              {/* Within 60 Days */}
              <div
                style={{
                  background: "rgba(245, 158, 11, 0.1)",
                  border: "1px solid rgba(245, 158, 11, 0.3)",
                  borderRadius: 6,
                  padding: "10px 14px",
                  cursor: "pointer",
                }}
                onClick={() => {
                  setExpiryFilter("WITHIN_60_DAYS");
                  setExpiryPage(1);
                }}
              >
                <div style={{ fontSize: "0.75rem", color: "#fcd34d", fontWeight: 700 }}>
                  31 – 60 Days
                </div>
                <div style={{ fontSize: "1.4rem", fontWeight: 800, color: "#f59e0b", marginTop: 4 }}>
                  {expiryData.summary.within_60_count} <span style={{ fontSize: "0.85rem", fontWeight: 400 }}>batches</span>
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 2 }}>
                  Value: <strong>{formatRupees(expiryData.summary.within_60_value_paise)}</strong>
                </div>
              </div>

              {/* Within 90 Days */}
              <div
                style={{
                  background: "rgba(234, 179, 8, 0.1)",
                  border: "1px solid rgba(234, 179, 8, 0.3)",
                  borderRadius: 6,
                  padding: "10px 14px",
                  cursor: "pointer",
                }}
                onClick={() => {
                  setExpiryFilter("WITHIN_90_DAYS");
                  setExpiryPage(1);
                }}
              >
                <div style={{ fontSize: "0.75rem", color: "#facc15", fontWeight: 700 }}>
                  61 – 90 Days
                </div>
                <div style={{ fontSize: "1.4rem", fontWeight: 800, color: "#eab308", marginTop: 4 }}>
                  {expiryData.summary.within_90_count} <span style={{ fontSize: "0.85rem", fontWeight: 400 }}>batches</span>
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 2 }}>
                  Value: <strong>{formatRupees(expiryData.summary.within_90_value_paise)}</strong>
                </div>
              </div>

              {/* Within 180 Days */}
              <div
                style={{
                  background: "rgba(56, 189, 248, 0.1)",
                  border: "1px solid rgba(56, 189, 248, 0.3)",
                  borderRadius: 6,
                  padding: "10px 14px",
                  cursor: "pointer",
                }}
                onClick={() => {
                  setExpiryFilter("WITHIN_180_DAYS");
                  setExpiryPage(1);
                }}
              >
                <div style={{ fontSize: "0.75rem", color: "#38bdf8", fontWeight: 700 }}>
                  91 – 180 Days
                </div>
                <div style={{ fontSize: "1.4rem", fontWeight: 800, color: "#38bdf8", marginTop: 4 }}>
                  {expiryData.summary.within_180_count} <span style={{ fontSize: "0.85rem", fontWeight: 400 }}>batches</span>
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 2 }}>
                  Value: <strong>{formatRupees(expiryData.summary.within_180_value_paise)}</strong>
                </div>
              </div>

              {/* Total At-Risk Value */}
              <div
                style={{
                  background: "rgba(168, 85, 247, 0.1)",
                  border: "1px solid rgba(168, 85, 247, 0.3)",
                  borderRadius: 6,
                  padding: "10px 14px",
                  cursor: "pointer",
                }}
                onClick={() => {
                  setExpiryFilter("ALL");
                  setExpiryPage(1);
                }}
              >
                <div style={{ fontSize: "0.75rem", color: "#c084fc", fontWeight: 700 }}>
                  Total At-Risk Stock
                </div>
                <div style={{ fontSize: "1.4rem", fontWeight: 800, color: "#a855f7", marginTop: 4 }}>
                  {formatRupees(expiryData.summary.total_at_risk_value_paise)}
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 2 }}>
                  Filter: <strong>{expiryFilter}</strong>
                </div>
              </div>
            </div>
          )}

          {/* Filter Pills & Search */}
          <div className="pos-panel" style={{ padding: "12px 18px", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10 }}>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {(
                [
                  { id: "ALL", label: "All At-Risk (<= 180d)" },
                  { id: "EXPIRED", label: "Expired" },
                  { id: "WITHIN_30_DAYS", label: "0–30 Days" },
                  { id: "WITHIN_60_DAYS", label: "31–60 Days" },
                  { id: "WITHIN_90_DAYS", label: "61–90 Days" },
                  { id: "WITHIN_180_DAYS", label: "91–180 Days" },
                ] as const
              ).map((f) => (
                <button
                  key={f.id}
                  type="button"
                  className={`btn btn-sm ${expiryFilter === f.id ? "btn-primary" : "btn-secondary"}`}
                  onClick={() => {
                    setExpiryFilter(f.id);
                    setExpiryPage(1);
                  }}
                  style={{ fontSize: "0.78rem" }}
                >
                  {f.label}
                </button>
              ))}
            </div>

            <div>
              <input
                type="text"
                className="input-field"
                placeholder="Search medicine, salt, batch..."
                value={expirySearch}
                onChange={(e) => {
                  setExpirySearch(e.target.value);
                  setExpiryPage(1);
                }}
                style={{ width: "260px", padding: "6px 12px", fontSize: "0.82rem" }}
              />
            </div>
          </div>

          {/* Batch Table */}
          <div className="pos-panel" style={{ padding: "16px 20px" }}>
            <div style={{ overflowX: "auto" }}>
              <table className="table" style={{ width: "100%", fontSize: "0.82rem" }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: "left" }}>Medicine & Salt</th>
                    <th style={{ textAlign: "left" }}>Batch Number</th>
                    <th style={{ textAlign: "left" }}>Expiry Date</th>
                    <th style={{ textAlign: "left" }}>Status</th>
                    <th style={{ textAlign: "right" }}>Stock (Units)</th>
                    <th style={{ textAlign: "right" }}>Packs</th>
                    <th style={{ textAlign: "right" }}>Rate / MRP</th>
                    <th style={{ textAlign: "right" }}>Stock Value</th>
                    <th style={{ textAlign: "left" }}>Rack</th>
                    <th style={{ textAlign: "left" }}>Supplier</th>
                  </tr>
                </thead>
                <tbody>
                  {isExpiryLoading ? (
                    <tr>
                      <td colSpan={10} style={{ textAlign: "center", padding: 24, color: "var(--text-dim)" }}>
                        Loading expiry records...
                      </td>
                    </tr>
                  ) : !expiryData?.items || expiryData.items.length === 0 ? (
                    <tr>
                      <td colSpan={10} style={{ textAlign: "center", padding: 24, color: "var(--text-dim)" }}>
                        No batches match the selected expiry criteria.
                      </td>
                    </tr>
                  ) : (
                    expiryData.items.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <div>
                            <strong style={{ color: "#f9fafb" }}>{item.medicine_name}</strong>
                            <span style={{ fontSize: "0.75rem", color: "var(--text-dim)", marginLeft: 6 }}>
                              {item.dosage_form}
                            </span>
                          </div>
                          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                            {item.generic_salt || "—"}
                          </div>
                        </td>
                        <td>
                          <strong style={{ fontFamily: "var(--font-mono)", color: "#38bdf8" }}>
                            {item.batch_number}
                          </strong>
                        </td>
                        <td style={{ fontFamily: "var(--font-mono)" }}>{item.expiry_date}</td>
                        <td>
                          {item.is_expired ? (
                            <span
                              style={{
                                padding: "2px 6px",
                                borderRadius: 4,
                                backgroundColor: "rgba(239, 68, 68, 0.2)",
                                color: "#ef4444",
                                fontWeight: 700,
                                fontSize: "0.72rem",
                              }}
                            >
                              EXPIRED
                            </span>
                          ) : (
                            <span
                              style={{
                                padding: "2px 6px",
                                borderRadius: 4,
                                backgroundColor:
                                  item.days_to_expiry <= 30
                                    ? "rgba(249, 115, 22, 0.2)"
                                    : item.days_to_expiry <= 60
                                    ? "rgba(245, 158, 11, 0.2)"
                                    : "rgba(56, 189, 248, 0.2)",
                                color:
                                  item.days_to_expiry <= 30
                                    ? "#f97316"
                                    : item.days_to_expiry <= 60
                                    ? "#f59e0b"
                                    : "#38bdf8",
                                fontWeight: 600,
                                fontSize: "0.72rem",
                              }}
                            >
                              {item.days_to_expiry} days left
                            </span>
                          )}
                        </td>
                        <td style={{ textAlign: "right", fontWeight: 600 }}>{item.current_quantity}</td>
                        <td style={{ textAlign: "right", color: "var(--text-muted)" }}>{item.available_packs}</td>
                        <td style={{ textAlign: "right", fontSize: "0.78rem" }}>
                          <div>{formatRupees(item.purchase_rate_paise)}</div>
                          <div style={{ color: "var(--text-dim)" }}>MRP {formatRupees(item.mrp_paise)}</div>
                        </td>
                        <td style={{ textAlign: "right", fontWeight: 700, color: "#10b981" }}>
                          {formatRupees(item.estimated_stock_value_paise)}
                        </td>
                        <td style={{ color: "var(--text-muted)" }}>{item.rack_location || "—"}</td>
                        <td style={{ color: "var(--text-muted)", fontSize: "0.78rem" }}>
                          {item.supplier_name || "—"}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {expiryData && (
              <PaginationBar
                page={expiryPage}
                pageSize={expiryPageSize}
                total={expiryData.total}
                totalPages={expiryData.total_pages}
                onPageChange={setExpiryPage}
                onPageSizeChange={(newSize) => {
                  setExpiryPageSize(newSize);
                  setExpiryPage(1);
                }}
              />
            )}
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB 2: SUPPLIER RETURN DUMP
          ========================================================================= */}
      {activeTab === "return_dump" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {/* Controls */}
          <div className="pos-panel" style={{ padding: "12px 18px", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>Threshold:</span>
                <select
                  className="input-field"
                  value={returnDays}
                  onChange={(e) => setReturnDays(Number(e.target.value))}
                  style={{ padding: "6px 10px", fontSize: "0.82rem" }}
                >
                  <option value={30}>Expiring within 30 Days</option>
                  <option value={60}>Expiring within 60 Days</option>
                  <option value={90}>Expiring within 90 Days</option>
                  <option value={180}>Expiring within 180 Days</option>
                </select>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>Supplier:</span>
                <select
                  className="input-field"
                  value={returnSupplierId || ""}
                  onChange={(e) => setReturnSupplierId(e.target.value ? Number(e.target.value) : undefined)}
                  style={{ padding: "6px 10px", fontSize: "0.82rem", minWidth: "180px" }}
                >
                  <option value="">-- All Suppliers --</option>
                  {allSuppliers.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={handlePrintReturnDump}
                style={{ display: "flex", alignItems: "center", gap: 6 }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="6 9 6 2 18 2 18 9" />
                  <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
                  <rect x="6" y="14" width="12" height="8" />
                </svg>
                <span>Print Return Dump</span>
              </button>
            </div>
          </div>

          {/* Grouped Supplier Cards */}
          {isReturnDumpLoading ? (
            <div className="pos-panel" style={{ padding: 30, textAlign: "center", color: "var(--text-dim)" }}>
              Generating supplier return breakdown...
            </div>
          ) : returnDumpGroups.length === 0 ? (
            <div className="pos-panel" style={{ padding: 30, textAlign: "center", color: "var(--text-dim)" }}>
              No near-expiry batches found for selected threshold and suppliers.
            </div>
          ) : (
            returnDumpGroups.map((group, gIdx) => (
              <div key={gIdx} className="pos-panel" style={{ padding: "16px 20px" }}>
                {/* Supplier Header Strip */}
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    borderBottom: "1px solid var(--border-subtle)",
                    paddingBottom: 10,
                    marginBottom: 12,
                    flexWrap: "wrap",
                    gap: 10,
                  }}
                >
                  <div>
                    <h3 style={{ margin: 0, fontSize: "1.05rem", fontWeight: 700, color: "#38bdf8" }}>
                      {group.supplier_name}
                    </h3>
                    <div style={{ fontSize: "0.78rem", color: "var(--text-dim)", marginTop: 2 }}>
                      {group.supplier_phone ? `Phone: ${group.supplier_phone}` : ""}
                      {group.supplier_gstin ? ` | GSTIN: ${group.supplier_gstin}` : ""}
                    </div>
                  </div>

                  <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
                    <div style={{ textAlign: "right" }}>
                      <span style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>Total Batches:</span>
                      <strong style={{ marginLeft: 6, color: "var(--text-main)" }}>{group.total_batches}</strong>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <span style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>Total Units:</span>
                      <strong style={{ marginLeft: 6, color: "var(--text-main)" }}>{group.total_units}</strong>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <span style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>Claim Value:</span>
                      <strong style={{ marginLeft: 6, color: "#10b981", fontSize: "1rem" }}>
                        {formatRupees(group.total_value_paise)}
                      </strong>
                    </div>
                  </div>
                </div>

                {/* Batches Table */}
                <div style={{ overflowX: "auto" }}>
                  <table className="table" style={{ width: "100%", fontSize: "0.82rem" }}>
                    <thead>
                      <tr>
                        <th style={{ textAlign: "left" }}>Medicine Name</th>
                        <th style={{ textAlign: "left" }}>Batch Number</th>
                        <th style={{ textAlign: "left" }}>Expiry Date</th>
                        <th style={{ textAlign: "left" }}>Days Left</th>
                        <th style={{ textAlign: "right" }}>Return Units</th>
                        <th style={{ textAlign: "right" }}>Packs</th>
                        <th style={{ textAlign: "right" }}>Unit Rate</th>
                        <th style={{ textAlign: "right" }}>Total Return Value</th>
                        <th style={{ textAlign: "left" }}>Rack</th>
                      </tr>
                    </thead>
                    <tbody>
                      {group.batches.map((b) => (
                        <tr key={b.id}>
                          <td>
                            <strong>{b.medicine_name}</strong>
                            <span style={{ fontSize: "0.75rem", color: "var(--text-dim)", marginLeft: 6 }}>
                              ({b.dosage_form})
                            </span>
                          </td>
                          <td style={{ fontFamily: "var(--font-mono)", color: "#38bdf8" }}>{b.batch_number}</td>
                          <td style={{ fontFamily: "var(--font-mono)" }}>{b.expiry_date}</td>
                          <td>
                            <span
                              style={{
                                color: b.is_expired ? "#ef4444" : "#f59e0b",
                                fontWeight: 700,
                                fontSize: "0.75rem",
                              }}
                            >
                              {b.is_expired ? "EXPIRED" : `${b.days_to_expiry} days`}
                            </span>
                          </td>
                          <td style={{ textAlign: "right", fontWeight: 700 }}>{b.current_quantity}</td>
                          <td style={{ textAlign: "right", color: "var(--text-muted)" }}>{b.available_packs}</td>
                          <td style={{ textAlign: "right" }}>{formatRupees(b.purchase_rate_paise)}</td>
                          <td style={{ textAlign: "right", fontWeight: 700, color: "#10b981" }}>
                            {formatRupees(b.estimated_stock_value_paise)}
                          </td>
                          <td style={{ color: "var(--text-muted)" }}>{b.rack_location || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* =========================================================================
          TAB 3: WANT-BOOK & LOW-STOCK REORDER
          ========================================================================= */}
      {activeTab === "want_book" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {/* Sub Navigation Strip */}
          <div className="pos-panel" style={{ padding: "12px 18px", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10 }}>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                type="button"
                className={`btn btn-sm ${wantBookSubTab === "low_stock" ? "btn-primary" : "btn-secondary"}`}
                onClick={() => setWantBookSubTab("low_stock")}
                style={{ fontWeight: 600 }}
              >
                Low Stock Alerts
              </button>
              <button
                type="button"
                className={`btn btn-sm ${wantBookSubTab === "want_list" ? "btn-primary" : "btn-secondary"}`}
                onClick={() => setWantBookSubTab("want_list")}
                style={{ fontWeight: 600 }}
              >
                Want-Book Requests
              </button>
            </div>

            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={() => {
                setTargetMedForWant(null);
                setShowAddWantModal(true);
              }}
              title="Add Item to Reorder / Want-Book (Ctrl+W)"
            >
              + Add Want-Book Item
            </button>
          </div>

          {/* SUB-VIEW 1: LOW STOCK ALERTS */}
          {wantBookSubTab === "low_stock" && (
            <div className="pos-panel" style={{ padding: "16px 20px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12, flexWrap: "wrap", gap: 10 }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: "1rem", fontWeight: 700, color: "var(--text-main)" }}>
                    Medicines At or Below Safety Stock ({lowStockItems.length} items)
                  </h3>
                  <p style={{ margin: "2px 0 0", fontSize: "0.78rem", color: "var(--text-muted)" }}>
                    Calculated based on minimum stock levels configured on medicines.
                  </p>
                </div>

                <input
                  type="text"
                  className="input-field"
                  placeholder="Filter low stock list..."
                  value={lowStockSearch}
                  onChange={(e) => setLowStockSearch(e.target.value)}
                  style={{ width: "220px", padding: "6px 10px", fontSize: "0.82rem" }}
                />
              </div>

              <div style={{ overflowX: "auto" }}>
                <table className="table" style={{ width: "100%", fontSize: "0.82rem" }}>
                  <thead>
                    <tr>
                      <th style={{ textAlign: "left" }}>Medicine Name</th>
                      <th style={{ textAlign: "left" }}>Dosage & Salt</th>
                      <th style={{ textAlign: "right" }}>Pack Size</th>
                      <th style={{ textAlign: "right" }}>Current Units</th>
                      <th style={{ textAlign: "right" }}>Current Packs</th>
                      <th style={{ textAlign: "right" }}>Min Units</th>
                      <th style={{ textAlign: "right" }}>Suggested Reorder</th>
                      <th style={{ textAlign: "left" }}>Preferred Supplier</th>
                      <th style={{ textAlign: "left" }}>Rack</th>
                      <th style={{ textAlign: "center" }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {isLowStockLoading ? (
                      <tr>
                        <td colSpan={10} style={{ textAlign: "center", padding: 24, color: "var(--text-dim)" }}>
                          Scanning stock levels...
                        </td>
                      </tr>
                    ) : lowStockItems.length === 0 ? (
                      <tr>
                        <td colSpan={10} style={{ textAlign: "center", padding: 24, color: "var(--text-dim)" }}>
                          No medicines currently below min_stock_units. Stock levels are healthy!
                        </td>
                      </tr>
                    ) : (
                      lowStockItems.map((item) => (
                        <tr key={item.medicine_id}>
                          <td>
                            <strong style={{ color: "#f9fafb" }}>{item.brand_name}</strong>
                          </td>
                          <td style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                            {item.dosage_form} | {item.generic_salt || "—"}
                          </td>
                          <td style={{ textAlign: "right" }}>{item.pack_size}</td>
                          <td
                            style={{
                              textAlign: "right",
                              fontWeight: 700,
                              color: item.current_stock_units === 0 ? "#ef4444" : "#f59e0b",
                            }}
                          >
                            {item.current_stock_units}
                          </td>
                          <td style={{ textAlign: "right", color: "var(--text-muted)" }}>{item.current_packs}</td>
                          <td style={{ textAlign: "right", color: "var(--text-dim)" }}>{item.min_stock_units}</td>
                          <td style={{ textAlign: "right", fontWeight: 700, color: "#38bdf8" }}>
                            {item.suggested_reorder_packs} packs
                          </td>
                          <td style={{ color: "var(--text-muted)", fontSize: "0.78rem" }}>
                            {item.preferred_supplier_name || "—"}
                          </td>
                          <td style={{ color: "var(--text-muted)" }}>{item.rack_location || "—"}</td>
                          <td style={{ textAlign: "center" }}>
                            <button
                              type="button"
                              className="btn btn-primary btn-sm"
                              style={{ fontSize: "0.72rem", padding: "2px 8px" }}
                              onClick={() => {
                                setTargetMedForWant({ id: item.medicine_id, name: item.brand_name });
                                setShowAddWantModal(true);
                              }}
                            >
                              + Want-Book
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* SUB-VIEW 2: WANT-BOOK REQUESTS */}
          {wantBookSubTab === "want_list" && (
            <div className="pos-panel" style={{ padding: "16px 20px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12, flexWrap: "wrap", gap: 10 }}>
                {/* Status Filter Tabs */}
                <div style={{ display: "flex", gap: 6 }}>
                  {(["ALL", "PENDING", "ORDERED", "RECEIVED"] as const).map((st) => (
                    <button
                      key={st}
                      type="button"
                      className={`btn btn-sm ${wantBookStatusFilter === st ? "btn-primary" : "btn-secondary"}`}
                      onClick={() => {
                        setWantBookStatusFilter(st);
                        setWantBookPage(1);
                      }}
                      style={{ fontSize: "0.78rem" }}
                    >
                      {st}
                    </button>
                  ))}
                </div>

                <span style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                  Total Requests: <strong>{wantBookTotal}</strong>
                </span>
              </div>

              <div style={{ overflowX: "auto" }}>
                <table className="table" style={{ width: "100%", fontSize: "0.82rem" }}>
                  <thead>
                    <tr>
                      <th style={{ textAlign: "left" }}>Medicine</th>
                      <th style={{ textAlign: "right" }}>Requested Packs</th>
                      <th style={{ textAlign: "right" }}>Stock / Min</th>
                      <th style={{ textAlign: "left" }}>Status</th>
                      <th style={{ textAlign: "left" }}>Supplier</th>
                      <th style={{ textAlign: "left" }}>Operator</th>
                      <th style={{ textAlign: "left" }}>Date Added</th>
                      <th style={{ textAlign: "left" }}>Notes</th>
                      <th style={{ textAlign: "center" }}>Status Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {isWantBookLoading ? (
                      <tr>
                        <td colSpan={9} style={{ textAlign: "center", padding: 24, color: "var(--text-dim)" }}>
                          Loading want-book items...
                        </td>
                      </tr>
                    ) : wantBookItems.length === 0 ? (
                      <tr>
                        <td colSpan={9} style={{ textAlign: "center", padding: 24, color: "var(--text-dim)" }}>
                          No want-book requests matching filter.
                        </td>
                      </tr>
                    ) : (
                      wantBookItems.map((wb) => (
                        <tr key={wb.id}>
                          <td>
                            <strong>{wb.medicine_name}</strong>
                            <div style={{ fontSize: "0.72rem", color: "var(--text-dim)" }}>
                              {wb.dosage_form} (Pack {wb.pack_size})
                            </div>
                          </td>
                          <td style={{ textAlign: "right", fontWeight: 700, color: "#38bdf8" }}>
                            {wb.requested_quantity_packs} packs
                          </td>
                          <td style={{ textAlign: "right", fontSize: "0.78rem" }}>
                            {wb.current_stock_units} / {wb.min_stock_units}
                          </td>
                          <td>
                            <span
                              style={{
                                fontSize: "0.72rem",
                                padding: "2px 6px",
                                borderRadius: 4,
                                fontWeight: 700,
                                backgroundColor:
                                  wb.status === "PENDING"
                                    ? "rgba(245, 158, 11, 0.15)"
                                    : wb.status === "ORDERED"
                                    ? "rgba(2, 132, 199, 0.15)"
                                    : "rgba(16, 185, 129, 0.15)",
                                color:
                                  wb.status === "PENDING"
                                    ? "#fbbf24"
                                    : wb.status === "ORDERED"
                                    ? "#38bdf8"
                                    : "#34d399",
                              }}
                            >
                              {wb.status}
                            </span>
                          </td>
                          <td style={{ color: "var(--text-muted)", fontSize: "0.78rem" }}>
                            {wb.supplier_name || "—"}
                          </td>
                          <td style={{ color: "var(--text-muted)", fontSize: "0.78rem" }}>
                            {wb.requested_by_name || "—"}
                          </td>
                          <td style={{ color: "var(--text-dim)", fontSize: "0.78rem" }}>
                            {new Date(wb.created_at).toLocaleDateString("en-IN", {
                              day: "2-digit",
                              month: "short",
                            })}
                          </td>
                          <td style={{ color: "var(--text-muted)", fontSize: "0.78rem", maxWidth: 150, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={wb.notes || ""}>
                            {wb.notes || "—"}
                          </td>
                          <td style={{ textAlign: "center" }}>
                            <div style={{ display: "flex", gap: 6, justifyContent: "center" }}>
                              {wb.status === "PENDING" && (
                                <button
                                  type="button"
                                  className="btn btn-secondary btn-sm"
                                  style={{ fontSize: "0.72rem", padding: "2px 6px" }}
                                  onClick={() => handleUpdateWantStatus(wb.id, "ORDERED")}
                                  title="Mark as Ordered from Supplier"
                                >
                                  Mark Ordered
                                </button>
                              )}
                              {wb.status === "ORDERED" && (
                                <button
                                  type="button"
                                  className="btn btn-secondary btn-sm"
                                  style={{ fontSize: "0.72rem", padding: "2px 6px", color: "#34d399" }}
                                  onClick={() => handleUpdateWantStatus(wb.id, "RECEIVED")}
                                  title="Mark as Received at Pharmacy"
                                >
                                  Mark Received
                                </button>
                              )}
                              <button
                                type="button"
                                className="btn btn-danger btn-sm"
                                style={{ fontSize: "0.72rem", padding: "2px 6px" }}
                                onClick={() => handleDeleteWantItem(wb.id)}
                                title="Remove item"
                              >
                                ×
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              <PaginationBar
                page={wantBookPage}
                pageSize={wantBookPageSize}
                total={wantBookTotal}
                totalPages={wantBookTotalPages}
                onPageChange={setWantBookPage}
                onPageSizeChange={(newSize) => {
                  setWantBookPageSize(newSize);
                  setWantBookPage(1);
                }}
              />
            </div>
          )}
        </div>
      )}

      {/* Quick Want-Book Entry Modal */}
      <QuickWantBookModal
        isOpen={showAddWantModal}
        onClose={() => {
          setShowAddWantModal(false);
          setTargetMedForWant(null);
        }}
        initialMedicineId={targetMedForWant?.id}
        initialMedicineName={targetMedForWant?.name}
        onSuccess={() => {
          if (activeTab === "want_book") {
            if (wantBookSubTab === "low_stock") loadLowStock();
            else loadWantBookList();
          }
        }}
      />
    </div>
  );
};
