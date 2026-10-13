import React, { useState, useEffect, useCallback, useRef } from "react";
import type { Customer, CreateCustomerInput, UpdateCustomerInput } from "@pharmacy/api-contracts";
import { formatRupees, rupeesToPaise } from "@pharmacy/api-contracts";
import { useAuth } from "../context/AuthContext";
import * as mastersApi from "../api/masters";
import { PaginationBar } from "./PaginationBar";
import { ConfirmModal } from "./ConfirmModal";

export const CustomerMasterView: React.FC = () => {
  const { user } = useAuth();
  const canEdit = user?.role === "ADMIN" || user?.role === "PHARMACIST";

  // Data state
  const [customers, setCustomers] = useState<Customer[]>([]);
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
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null);
  const [deactivatingCustomer, setDeactivatingCustomer] = useState<Customer | null>(null);
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

  // Load customers
  const loadCustomers = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const activeParam =
        activeFilter === "active" ? true : activeFilter === "inactive" ? false : undefined;

      const resp = await mastersApi.listCustomers({
        query: debouncedQuery || undefined,
        is_active: activeParam,
        page,
        page_size: pageSize,
      });

      setCustomers(resp.items);
      setTotal(resp.total);
      setTotalPages(resp.total_pages);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load customers.";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [debouncedQuery, activeFilter, page, pageSize]);

  useEffect(() => {
    loadCustomers();
  }, [loadCustomers]);

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

  // Deactivate customer
  const handleConfirmDeactivate = async () => {
    if (!deactivatingCustomer) return;
    setIsSubmitting(true);
    try {
      await mastersApi.deactivateCustomer(deactivatingCustomer.id);
      setDeactivatingCustomer(null);
      loadCustomers();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to deactivate customer.";
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
              placeholder="Search customer name or 10-digit mobile number..."
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
            onClick={loadCustomers}
            disabled={isLoading}
            title="Refresh Customers"
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
              title="Add New Customer [Alt+N]"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              <span>+ Add Customer</span>
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
                <th>Patient / Customer Name</th>
                <th style={{ width: "160px" }}>Phone / Mobile</th>
                <th>Residential Address</th>
                <th style={{ width: "180px" }}>Consulting Doctor</th>
                <th style={{ width: "130px", textAlign: "right" }}>Credit Limit</th>
                <th style={{ width: "130px", textAlign: "right" }}>Khata Balance</th>
                <th style={{ width: "90px" }}>Status</th>
                {canEdit && <th style={{ width: "120px", textAlign: "right" }}>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={canEdit ? 9 : 8}>
                    <div className="table-loading-overlay">
                      <span>Loading Customer Directory...</span>
                    </div>
                  </td>
                </tr>
              ) : customers.length === 0 ? (
                <tr>
                  <td colSpan={canEdit ? 9 : 8}>
                    <div className="table-empty-state">
                      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <circle cx="12" cy="12" r="10" />
                        <line x1="8" y1="12" x2="16" y2="12" />
                      </svg>
                      <strong style={{ color: "#ffffff", fontSize: "0.95rem" }}>No customers found</strong>
                      <p style={{ fontSize: "0.82rem", marginTop: 4 }}>
                        {debouncedQuery
                          ? `No records found matching "${debouncedQuery}".`
                          : "Customer directory is currently empty. Add customer profiles for credit khata tracking."}
                      </p>
                    </div>
                  </td>
                </tr>
              ) : (
                customers.map((cust) => (
                  <tr key={cust.id} className={!cust.is_active ? "inactive-row" : ""}>
                    <td className="col-code">#{cust.id}</td>

                    <td>
                      <div className="col-name">{cust.name}</div>
                    </td>

                    <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.82rem", color: "#38bdf8" }}>
                      {cust.phone || "—"}
                    </td>

                    <td style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                      {cust.address || "—"}
                    </td>

                    <td style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                      {cust.default_doctor || "—"}
                    </td>

                    <td className="col-amount" style={{ color: "var(--text-muted)" }}>
                      ₹{(cust.credit_limit_paise / 100).toFixed(2)}
                    </td>

                    <td
                      className="col-amount"
                      style={{
                        color: cust.current_balance_paise > cust.credit_limit_paise ? "#ef4444" : cust.current_balance_paise > 0 ? "#f59e0b" : "#10b981",
                      }}
                    >
                      ₹{(cust.current_balance_paise / 100).toFixed(2)}
                    </td>

                    <td>
                      <span className={`pill-badge ${cust.is_active ? "pill-active" : "pill-inactive"}`}>
                        {cust.is_active ? "Active" : "Inactive"}
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
                              setEditingCustomer(cust);
                            }}
                            title="Edit Customer"
                          >
                            Edit
                          </button>
                          {cust.is_active && (
                            <button
                              type="button"
                              className="btn btn-danger btn-sm"
                              onClick={() => setDeactivatingCustomer(cust)}
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

      {/* 3. Add / Edit Customer Modal */}
      {(showAddModal || editingCustomer) && (
        <CustomerFormModal
          isOpen={true}
          isEdit={!!editingCustomer}
          initialData={editingCustomer}
          modalError={modalError}
          isSubmitting={isSubmitting}
          onClose={() => {
            setShowAddModal(false);
            setEditingCustomer(null);
            setModalError(null);
          }}
          onSubmit={async (payload) => {
            setIsSubmitting(true);
            setModalError(null);
            try {
              if (editingCustomer) {
                await mastersApi.updateCustomer(editingCustomer.id, payload as UpdateCustomerInput);
              } else {
                await mastersApi.createCustomer(payload as CreateCustomerInput);
              }
              setShowAddModal(false);
              setEditingCustomer(null);
              loadCustomers();
            } catch (err: unknown) {
              const msg = err instanceof Error ? err.message : "Failed to save customer profile.";
              setModalError(msg);
            } finally {
              setIsSubmitting(false);
            }
          }}
        />
      )}

      {/* 4. Deactivate Confirmation Modal */}
      <ConfirmModal
        isOpen={!!deactivatingCustomer}
        title="Confirm Customer Deactivation"
        message="Are you sure you want to deactivate this customer account? This will hide the customer from counter credit lookup while preserving their historic Khata transactions."
        itemName={deactivatingCustomer ? `${deactivatingCustomer.name} (Phone: ${deactivatingCustomer.phone || "N/A"})` : ""}
        confirmLabel="Deactivate Customer"
        confirmVariant="danger"
        isLoading={isSubmitting}
        onConfirm={handleConfirmDeactivate}
        onCancel={() => setDeactivatingCustomer(null)}
      />
    </div>
  );
};

// ==========================================
// SUB-COMPONENT: CUSTOMER FORM MODAL
// ==========================================

interface CustomerFormModalProps {
  isOpen: boolean;
  isEdit: boolean;
  initialData: Customer | null;
  modalError: string | null;
  isSubmitting: boolean;
  onClose: () => void;
  onSubmit: (payload: CreateCustomerInput | UpdateCustomerInput) => Promise<void>;
}

const CustomerFormModal: React.FC<CustomerFormModalProps> = ({
  isEdit,
  initialData,
  modalError,
  isSubmitting,
  onClose,
  onSubmit,
}) => {
  const [formData, setFormData] = useState<CreateCustomerInput>({
    name: initialData?.name || "",
    phone: initialData?.phone || "",
    address: initialData?.address || "",
    default_doctor: initialData?.default_doctor || "",
    credit_limit_paise: initialData?.credit_limit_paise ?? 500000,
  });

  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const nameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    nameRef.current?.focus();
  }, []);

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (!formData.name.trim()) {
      errs.name = "Customer / Patient name is required.";
    }
    if (formData.phone?.trim()) {
      const cleanPhone = formData.phone.trim();
      if (!/^\d{10,12}$/.test(cleanPhone)) {
        errs.phone = "Phone number should be 10 to 12 digits.";
      }
    }
    if (formData.credit_limit_paise !== undefined && formData.credit_limit_paise < 0) {
      errs.credit_limit_paise = "Credit limit cannot be negative.";
    }

    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    const payload: CreateCustomerInput = {
      name: formData.name.trim(),
      phone: formData.phone?.trim() || null,
      address: formData.address?.trim() || null,
      default_doctor: formData.default_doctor?.trim() || null,
      credit_limit_paise: Number(formData.credit_limit_paise ?? 500000),
    };

    onSubmit(payload);
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-dialog modal-dialog-medium" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" strokeWidth="2">
              <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
              <circle cx="9" cy="7" r="4" />
              <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
              <path d="M16 3.13a4 4 0 0 1 0 7.75" />
            </svg>
            <span>{isEdit ? `Edit Customer #${initialData?.id}` : "Add New Customer"}</span>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={onClose} title="Close [Esc]">
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {modalError && <div className="auth-error-banner">{modalError}</div>}

            <div className="form-group">
              <label className="form-label form-label-required">Customer / Patient Name</label>
              <input
                ref={nameRef}
                type="text"
                className={`form-input ${fieldErrors.name ? "form-input-error" : ""}`}
                placeholder="e.g. Ramesh Kumar"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                disabled={isSubmitting}
              />
              {fieldErrors.name && <span className="form-error-text">{fieldErrors.name}</span>}
            </div>

            <div className="form-grid-2">
              <div className="form-group">
                <label className="form-label">Phone / Mobile Number</label>
                <input
                  type="text"
                  maxLength={12}
                  className={`form-input ${fieldErrors.phone ? "form-input-error" : ""}`}
                  placeholder="e.g. 9876543210"
                  value={formData.phone || ""}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  disabled={isSubmitting}
                />
                {fieldErrors.phone && <span className="form-error-text">{fieldErrors.phone}</span>}
              </div>

              <div className="form-group">
                <label className="form-label">Credit Limit (₹)</label>
                <input
                  type="number"
                  min="0"
                  step="100"
                  className={`form-input ${fieldErrors.credit_limit_paise ? "form-input-error" : ""}`}
                  value={formData.credit_limit_paise !== undefined ? formatRupees(formData.credit_limit_paise) : ""}
                  onChange={(e) => setFormData({ ...formData, credit_limit_paise: rupeesToPaise(e.target.value) })}
                  disabled={isSubmitting}
                />
                {fieldErrors.credit_limit_paise && <span className="form-error-text">{fieldErrors.credit_limit_paise}</span>}
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Consulting / Default Doctor</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Dr. A.K. Gupta, MD"
                value={formData.default_doctor || ""}
                onChange={(e) => setFormData({ ...formData, default_doctor: e.target.value })}
                disabled={isSubmitting}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Residential Address</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. H.No 142, Sector 9, Rohini"
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
              {isSubmitting ? "Saving..." : isEdit ? "Update Customer" : "Create Customer"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
