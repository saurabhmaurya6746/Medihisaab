import React, { useState, useEffect, useCallback, useRef } from "react";
import type { Supplier, CreateSupplierInput, UpdateSupplierInput } from "@pharmacy/api-contracts";
import { GSTIN_REGEX } from "@pharmacy/api-contracts";
import { useAuth } from "../context/AuthContext";
import * as mastersApi from "../api/masters";
import { PaginationBar } from "./PaginationBar";
import { ConfirmModal } from "./ConfirmModal";

export const SupplierMasterView: React.FC = () => {
  const { user } = useAuth();
  const canEdit = user?.role === "ADMIN" || user?.role === "PHARMACIST";

  // Data state
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(20);

  // Filters
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [debouncedQuery, setDebouncedQuery] = useState<string>("");
  const [activeFilter, setActiveFilter] = useState<string>("active");

  // Loading & error
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Modal states
  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [editingSupplier, setEditingSupplier] = useState<Supplier | null>(null);
  const [deactivatingSupplier, setDeactivatingSupplier] = useState<Supplier | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Search debounce
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchQuery.trim());
      setPage(1);
    }, 250);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Load suppliers list
  const loadSuppliers = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const activeParam =
        activeFilter === "active" ? true : activeFilter === "inactive" ? false : undefined;

      const resp = await mastersApi.listSuppliers({
        query: debouncedQuery || undefined,
        is_active: activeParam,
        page,
        page_size: pageSize,
      });

      setSuppliers(resp.items);
      setTotal(resp.total);
      setTotalPages(resp.total_pages);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load suppliers.";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [debouncedQuery, activeFilter, page, pageSize]);

  useEffect(() => {
    loadSuppliers();
  }, [loadSuppliers]);

  // Keyboard shortcut [Alt+N] to open Add Modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.altKey && (e.key === "n" || e.key === "N") && canEdit) {
        e.preventDefault();
        setModalError(null);
        setShowAddModal(true);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [canEdit]);

  // Deactivate supplier action
  const handleConfirmDeactivate = async () => {
    if (!deactivatingSupplier) return;
    setIsSubmitting(true);
    try {
      await mastersApi.deactivateSupplier(deactivatingSupplier.id);
      setDeactivatingSupplier(null);
      loadSuppliers();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to deactivate supplier.";
      setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="master-view-container">
      {/* 1. Toolbar */}
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
              placeholder="Search distributor name, GSTIN, phone, DL numbers..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              autoFocus
            />
            {searchQuery && (
              <button
                type="button"
                className="search-clear-btn"
                onClick={() => setSearchQuery("")}
                title="Clear Search"
              >
                ✕
              </button>
            )}
          </div>

          <select
            className="select-filter"
            value={activeFilter}
            onChange={(e) => {
              setActiveFilter(e.target.value);
              setPage(1);
            }}
          >
            <option value="active">Active Only</option>
            <option value="inactive">Inactive Only</option>
            <option value="all">All Records</option>
          </select>
        </div>

        <div className="toolbar-right">
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={loadSuppliers}
            disabled={isLoading}
            title="Refresh Suppliers"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
            </svg>
            <span>Refresh</span>
          </button>

          {canEdit ? (
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={() => {
                setModalError(null);
                setShowAddModal(true);
              }}
              title="Add New Supplier [Alt+N]"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              <span>+ Add Supplier</span>
            </button>
          ) : (
            <span
              style={{
                fontSize: "0.74rem",
                color: "var(--text-dim)",
                padding: "4px 8px",
                border: "1px dashed var(--border-subtle)",
                borderRadius: "var(--radius-sm)",
              }}
            >
              Read-Only Cashier Mode
            </span>
          )}
        </div>
      </div>

      {/* Global Error Banner */}
      {error && (
        <div className="auth-error-banner" style={{ margin: 0 }}>
          <span>{error}</span>
          <button
            className="btn btn-ghost btn-sm"
            style={{ marginLeft: "auto", padding: "0 4px" }}
            onClick={() => setError(null)}
          >
            ✕
          </button>
        </div>
      )}

      {/* 2. Data Table */}
      <div className="data-table-card">
        <div className="data-table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: "80px" }}>ID</th>
                <th>Supplier Name</th>
                <th style={{ width: "170px" }}>GSTIN</th>
                <th style={{ width: "160px" }}>Drug Licenses</th>
                <th style={{ width: "140px" }}>Phone / Contact</th>
                <th style={{ width: "110px" }}>Credit Days</th>
                <th style={{ width: "120px", textAlign: "right" }}>Current Payable</th>
                <th style={{ width: "90px" }}>Status</th>
                {canEdit && <th style={{ width: "120px", textAlign: "right" }}>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={canEdit ? 9 : 8}>
                    <div className="table-loading-overlay">
                      <span>Loading Suppliers Directory...</span>
                    </div>
                  </td>
                </tr>
              ) : suppliers.length === 0 ? (
                <tr>
                  <td colSpan={canEdit ? 9 : 8}>
                    <div className="table-empty-state">
                      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <circle cx="12" cy="12" r="10" />
                        <line x1="8" y1="12" x2="16" y2="12" />
                      </svg>
                      <strong style={{ color: "#ffffff", fontSize: "0.95rem" }}>No suppliers found</strong>
                      <p style={{ fontSize: "0.82rem", marginTop: 4 }}>
                        {debouncedQuery
                          ? `No suppliers matched "${debouncedQuery}".`
                          : "Supplier directory is currently empty. Add suppliers to record purchase invoices."}
                      </p>
                    </div>
                  </td>
                </tr>
              ) : (
                suppliers.map((sup) => (
                  <tr key={sup.id} className={!sup.is_active ? "inactive-row" : ""}>
                    <td className="col-code">#{sup.id}</td>

                    <td>
                      <div className="col-name">{sup.name}</div>
                      {sup.address && <div className="col-subtext">{sup.address}</div>}
                    </td>

                    <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.82rem", color: "#38bdf8" }}>
                      {sup.gstin || "—"}
                    </td>

                    <td style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
                      {sup.dl_number_20b && <div>20B: {sup.dl_number_20b}</div>}
                      {sup.dl_number_21b && <div>21B: {sup.dl_number_21b}</div>}
                      {!sup.dl_number_20b && !sup.dl_number_21b && <span>—</span>}
                    </td>

                    <td style={{ fontSize: "0.82rem" }}>
                      <div>{sup.phone || "—"}</div>
                      {sup.email && <div style={{ fontSize: "0.72rem", color: "var(--text-dim)" }}>{sup.email}</div>}
                    </td>

                    <td style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                      {sup.credit_days} days
                    </td>

                    <td className="col-amount" style={{ color: sup.current_payable_paise > 0 ? "#f87171" : "var(--text-muted)" }}>
                      ₹{(sup.current_payable_paise / 100).toFixed(2)}
                    </td>

                    <td>
                      <span className={`pill-badge ${sup.is_active ? "pill-active" : "pill-inactive"}`}>
                        {sup.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>

                    {canEdit && (
                      <td style={{ textAlign: "right" }}>
                        <div style={{ display: "inline-flex", gap: 6 }}>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => {
                              setModalError(null);
                              setEditingSupplier(sup);
                            }}
                            title="Edit Supplier"
                          >
                            Edit
                          </button>
                          {sup.is_active && (
                            <button
                              type="button"
                              className="btn btn-danger btn-sm"
                              onClick={() => setDeactivatingSupplier(sup)}
                              title="Safe Deactivate"
                            >
                              Deactivate
                            </button>
                          )}
                        </div>
                      </td>
                    )}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <PaginationBar
          page={page}
          pageSize={pageSize}
          total={total}
          totalPages={totalPages}
          onPageChange={(p) => setPage(p)}
          onPageSizeChange={(s) => {
            setPageSize(s);
            setPage(1);
          }}
        />
      </div>

      {/* 3. Add / Edit Supplier Modal */}
      {(showAddModal || editingSupplier) && (
        <SupplierFormModal
          isOpen={true}
          isEdit={!!editingSupplier}
          initialData={editingSupplier}
          modalError={modalError}
          isSubmitting={isSubmitting}
          onClose={() => {
            setShowAddModal(false);
            setEditingSupplier(null);
            setModalError(null);
          }}
          onSubmit={async (payload) => {
            setIsSubmitting(true);
            setModalError(null);
            try {
              if (editingSupplier) {
                await mastersApi.updateSupplier(editingSupplier.id, payload as UpdateSupplierInput);
              } else {
                await mastersApi.createSupplier(payload as CreateSupplierInput);
              }
              setShowAddModal(false);
              setEditingSupplier(null);
              loadSuppliers();
            } catch (err: unknown) {
              const msg = err instanceof Error ? err.message : "Failed to save supplier.";
              setModalError(msg);
            } finally {
              setIsSubmitting(false);
            }
          }}
        />
      )}

      {/* 4. Deactivate Confirmation Modal */}
      <ConfirmModal
        isOpen={!!deactivatingSupplier}
        title="Confirm Supplier Deactivation"
        message="Are you sure you want to deactivate this supplier? You will not be able to record new purchases from this supplier until reactivated."
        itemName={deactivatingSupplier ? `${deactivatingSupplier.name} (GSTIN: ${deactivatingSupplier.gstin || "N/A"})` : ""}
        confirmLabel="Deactivate Supplier"
        confirmVariant="danger"
        isLoading={isSubmitting}
        onConfirm={handleConfirmDeactivate}
        onCancel={() => setDeactivatingSupplier(null)}
      />
    </div>
  );
};

// ==========================================
// SUB-COMPONENT: SUPPLIER FORM MODAL
// ==========================================

interface SupplierFormModalProps {
  isOpen: boolean;
  isEdit: boolean;
  initialData: Supplier | null;
  modalError: string | null;
  isSubmitting: boolean;
  onClose: () => void;
  onSubmit: (payload: CreateSupplierInput | UpdateSupplierInput) => Promise<void>;
}

const SupplierFormModal: React.FC<SupplierFormModalProps> = ({
  isEdit,
  initialData,
  modalError,
  isSubmitting,
  onClose,
  onSubmit,
}) => {
  const [formData, setFormData] = useState<CreateSupplierInput>({
    name: initialData?.name || "",
    gstin: initialData?.gstin || "",
    dl_number_20b: initialData?.dl_number_20b || "",
    dl_number_21b: initialData?.dl_number_21b || "",
    phone: initialData?.phone || "",
    email: initialData?.email || "",
    address: initialData?.address || "",
    credit_days: initialData?.credit_days || 21,
  });

  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const nameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    nameRef.current?.focus();
  }, []);

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (!formData.name.trim()) {
      errs.name = "Supplier / Distributor name is required.";
    }
    if (formData.gstin?.trim()) {
      const upperGST = formData.gstin.trim().toUpperCase();
      if (!GSTIN_REGEX.test(upperGST)) {
        errs.gstin = "Invalid 15-character statutory GSTIN (e.g. 07AAAAA0000A1Z5).";
      }
    }
    if (formData.credit_days !== undefined && formData.credit_days < 0) {
      errs.credit_days = "Credit days cannot be negative.";
    }

    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    const payload: CreateSupplierInput = {
      name: formData.name.trim(),
      gstin: formData.gstin?.trim().toUpperCase() || null,
      dl_number_20b: formData.dl_number_20b?.trim() || null,
      dl_number_21b: formData.dl_number_21b?.trim() || null,
      phone: formData.phone?.trim() || null,
      email: formData.email?.trim() || null,
      address: formData.address?.trim() || null,
      credit_days: Number(formData.credit_days ?? 21),
    };

    onSubmit(payload);
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-dialog modal-dialog-large" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" strokeWidth="2">
              <rect x="1" y="3" width="15" height="13" />
              <polygon points="16 8 20 8 23 11 23 16 16 16 16 8" />
              <circle cx="5.5" cy="18.5" r="2.5" />
              <circle cx="18.5" cy="18.5" r="2.5" />
            </svg>
            <span>{isEdit ? `Edit Supplier #${initialData?.id}` : "Add New Supplier"}</span>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={onClose} title="Close [Esc]">
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body" style={{ maxHeight: "72vh", overflowY: "auto" }}>
            {modalError && <div className="auth-error-banner">{modalError}</div>}

            <div className="form-group">
              <label className="form-label form-label-required">Supplier / Distributor Firm Name</label>
              <input
                ref={nameRef}
                type="text"
                className={`form-input ${fieldErrors.name ? "form-input-error" : ""}`}
                placeholder="e.g. Vardhman Pharma Agencies"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                disabled={isSubmitting}
              />
              {fieldErrors.name && <span className="form-error-text">{fieldErrors.name}</span>}
            </div>

            <div className="form-grid-2">
              <div className="form-group">
                <label className="form-label">Statutory GSTIN</label>
                <input
                  type="text"
                  maxLength={15}
                  className={`form-input ${fieldErrors.gstin ? "form-input-error" : ""}`}
                  placeholder="e.g. 07AAAAA0000A1Z5"
                  value={formData.gstin || ""}
                  onChange={(e) => setFormData({ ...formData, gstin: e.target.value.toUpperCase() })}
                  disabled={isSubmitting}
                />
                {fieldErrors.gstin && <span className="form-error-text">{fieldErrors.gstin}</span>}
              </div>

              <div className="form-group">
                <label className="form-label">Credit Terms (Days)</label>
                <input
                  type="number"
                  min="0"
                  className={`form-input ${fieldErrors.credit_days ? "form-input-error" : ""}`}
                  value={formData.credit_days}
                  onChange={(e) => setFormData({ ...formData, credit_days: Number(e.target.value) })}
                  disabled={isSubmitting}
                />
                {fieldErrors.credit_days && <span className="form-error-text">{fieldErrors.credit_days}</span>}
              </div>
            </div>

            <div className="form-grid-2">
              <div className="form-group">
                <label className="form-label">Drug License 20B (Wholesale)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. DL-20B-98765"
                  value={formData.dl_number_20b || ""}
                  onChange={(e) => setFormData({ ...formData, dl_number_20b: e.target.value })}
                  disabled={isSubmitting}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Drug License 21B (Wholesale)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. DL-21B-98765"
                  value={formData.dl_number_21b || ""}
                  onChange={(e) => setFormData({ ...formData, dl_number_21b: e.target.value })}
                  disabled={isSubmitting}
                />
              </div>
            </div>

            <div className="form-grid-2">
              <div className="form-group">
                <label className="form-label">Contact Phone</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. 9811223344"
                  value={formData.phone || ""}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  disabled={isSubmitting}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Email Address</label>
                <input
                  type="email"
                  className="form-input"
                  placeholder="e.g. orders@vardhmanpharma.com"
                  value={formData.email || ""}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  disabled={isSubmitting}
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Registered Office / Warehouse Address</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. 24, Medicine Market, Bhagirath Palace, Delhi"
                value={formData.address || ""}
                onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                disabled={isSubmitting}
              />
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-secondary btn-sm" onClick={onClose} disabled={isSubmitting}>
              Cancel [Esc]
            </button>
            <button type="submit" className="btn btn-primary btn-sm" disabled={isSubmitting}>
              {isSubmitting ? "Saving..." : isEdit ? "Update Supplier" : "Create Supplier"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
