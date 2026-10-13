import React, { useState, useEffect, useCallback, useRef } from "react";
import type {
  Medicine,
  CreateMedicineInput,
  UpdateMedicineInput,
  Manufacturer,
  DosageForm,
  GSTRate,
} from "@pharmacy/api-contracts";
import { VALID_DOSAGE_FORMS, VALID_GST_RATES } from "@pharmacy/api-contracts";
import { useAuth } from "../context/AuthContext";
import * as mastersApi from "../api/masters";
import { PaginationBar } from "./PaginationBar";
import { ConfirmModal } from "./ConfirmModal";

export const MedicineMasterView: React.FC = () => {
  const { user } = useAuth();
  const canEdit = user?.role === "ADMIN" || user?.role === "PHARMACIST";

  // Data state
  const [medicines, setMedicines] = useState<Medicine[]>([]);
  const [manufacturers, setManufacturers] = useState<Manufacturer[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(20);

  // Filters
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [debouncedQuery, setDebouncedQuery] = useState<string>("");
  const [dosageFilter, setDosageFilter] = useState<string>("");
  const [activeFilter, setActiveFilter] = useState<string>("active"); // 'active' | 'inactive' | 'all'

  // Loading & error
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Modals state
  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [editingMedicine, setEditingMedicine] = useState<Medicine | null>(null);
  const [deactivatingMedicine, setDeactivatingMedicine] = useState<Medicine | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Quick manufacturer creation state
  const [showQuickMfgModal, setShowQuickMfgModal] = useState<boolean>(false);
  const [quickMfgName, setQuickMfgName] = useState<string>("");
  const [quickMfgCode, setQuickMfgCode] = useState<string>("");

  // Search debounce timer
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchQuery.trim());
      setPage(1); // Reset to page 1 on new search
    }, 250);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Load manufacturers for dropdown
  const loadManufacturers = useCallback(async () => {
    try {
      const resp = await mastersApi.listManufacturers({ page_size: 100, is_active: true });
      setManufacturers(resp.items);
    } catch (err) {
      console.error("Failed to load manufacturers list", err);
    }
  }, []);

  useEffect(() => {
    loadManufacturers();
  }, [loadManufacturers]);

  // Load medicines list
  const loadMedicines = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const activeParam =
        activeFilter === "active" ? true : activeFilter === "inactive" ? false : undefined;

      const resp = await mastersApi.listMedicines({
        query: debouncedQuery || undefined,
        dosage_form: dosageFilter || undefined,
        is_active: activeParam,
        page,
        page_size: pageSize,
      });

      setMedicines(resp.items);
      setTotal(resp.total);
      setTotalPages(resp.total_pages);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load medicines.";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [debouncedQuery, dosageFilter, activeFilter, page, pageSize]);

  useEffect(() => {
    loadMedicines();
  }, [loadMedicines]);

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

  // Handle Deactivation
  const handleConfirmDeactivate = async () => {
    if (!deactivatingMedicine) return;
    setIsSubmitting(true);
    try {
      await mastersApi.deactivateMedicine(deactivatingMedicine.id);
      setDeactivatingMedicine(null);
      loadMedicines();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to deactivate medicine.";
      setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Quick Manufacturer Submit
  const handleQuickMfgSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!quickMfgName.trim()) return;
    try {
      const newMfg = await mastersApi.createManufacturer({
        name: quickMfgName.trim(),
        short_code: quickMfgCode.trim() || null,
      });
      setManufacturers((prev) => [newMfg, ...prev]);
      setShowQuickMfgModal(false);
      setQuickMfgName("");
      setQuickMfgCode("");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create manufacturer.";
      setModalError(msg);
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
              placeholder="Search brand name, salt composition, code, barcode..."
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
            value={dosageFilter}
            onChange={(e) => {
              setDosageFilter(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All Dosage Forms</option>
            {VALID_DOSAGE_FORMS.map((form) => (
              <option key={form} value={form}>
                {form}
              </option>
            ))}
          </select>

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
            onClick={loadMedicines}
            disabled={isLoading}
            title="Refresh Catalog"
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
              title="Add New Medicine [Alt+N]"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              <span>+ Add Medicine</span>
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

      {/* Global Error Banner if any */}
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
                <th style={{ width: "110px" }}>Item Code</th>
                <th>Brand Name & Salt Composition</th>
                <th style={{ width: "130px" }}>Form & Pack</th>
                <th style={{ width: "160px" }}>Manufacturer</th>
                <th style={{ width: "100px" }}>Tax & HSN</th>
                <th style={{ width: "140px" }}>Compliance</th>
                <th style={{ width: "80px" }}>Rack</th>
                <th style={{ width: "90px" }}>Status</th>
                {canEdit && <th style={{ width: "120px", textAlign: "right" }}>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={canEdit ? 9 : 8}>
                    <div className="table-loading-overlay">
                      <span>Loading Medicines from SQLite Database...</span>
                    </div>
                  </td>
                </tr>
              ) : medicines.length === 0 ? (
                <tr>
                  <td colSpan={canEdit ? 9 : 8}>
                    <div className="table-empty-state">
                      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <circle cx="12" cy="12" r="10" />
                        <line x1="8" y1="12" x2="16" y2="12" />
                      </svg>
                      <strong style={{ color: "#ffffff", fontSize: "0.95rem" }}>No medicines matched your criteria</strong>
                      <p style={{ fontSize: "0.82rem", marginTop: 4 }}>
                        {debouncedQuery
                          ? `No records found for query "${debouncedQuery}". Check spelling or clear filters.`
                          : "Master medicine catalog is empty. Add your first medicine to get started."}
                      </p>
                    </div>
                  </td>
                </tr>
              ) : (
                medicines.map((med) => (
                  <tr key={med.id} className={!med.is_active ? "inactive-row" : ""}>
                    {/* Item Code & Barcode */}
                    <td className="col-code">
                      <div>{med.medicine_code || `MED-${med.id}`}</div>
                      {med.barcode && (
                        <div style={{ fontSize: "0.72rem", color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
                          {med.barcode}
                        </div>
                      )}
                    </td>

                    {/* Brand Name & Generic Salt */}
                    <td>
                      <div className="col-name">{med.brand_name}</div>
                      <div className="col-subtext">{med.generic_salt}</div>
                    </td>

                    {/* Dosage Form & Pack */}
                    <td>
                      <span className="pill-badge pill-dosage">{med.dosage_form}</span>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 2 }}>
                        {med.strength ? `${med.strength} • ` : ""}Pack of {med.pack_size}
                      </div>
                    </td>

                    {/* Manufacturer */}
                    <td style={{ color: "var(--text-muted)", fontSize: "0.82rem" }}>
                      {med.manufacturer_name || "—"}
                    </td>

                    {/* Tax & HSN */}
                    <td style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                      <div>GST {med.gst_rate}%</div>
                      <div style={{ fontSize: "0.72rem", color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
                        HSN {med.hsn_code}
                      </div>
                    </td>

                    {/* Compliance Badges */}
                    <td>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                        {med.is_schedule_h1 && <span className="pill-badge pill-sch-h1">Schedule H1</span>}
                        {med.is_schedule_h && <span className="pill-badge pill-sch-h">Schedule H</span>}
                        {med.is_narcotic && <span className="pill-badge pill-narcotic">Narcotic</span>}
                        {!med.is_schedule_h1 && !med.is_schedule_h && !med.is_narcotic && (
                          <span style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>General</span>
                        )}
                      </div>
                    </td>

                    {/* Rack / Shelf */}
                    <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem", color: "var(--text-muted)" }}>
                      {med.rack_location || "—"}
                    </td>

                    {/* Active Status */}
                    <td>
                      <span className={`pill-badge ${med.is_active ? "pill-active" : "pill-inactive"}`}>
                        {med.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>

                    {/* Actions */}
                    {canEdit && (
                      <td style={{ textAlign: "right" }}>
                        <div style={{ display: "inline-flex", gap: 6 }}>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => {
                              setModalError(null);
                              setEditingMedicine(med);
                            }}
                            title="Edit Medicine"
                          >
                            Edit
                          </button>
                          {med.is_active && (
                            <button
                              type="button"
                              className="btn btn-danger btn-sm"
                              onClick={() => setDeactivatingMedicine(med)}
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

        {/* 3. Pagination Bar */}
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

      {/* 4. Add / Edit Medicine Modal */}
      {(showAddModal || editingMedicine) && (
        <MedicineFormModal
          isOpen={true}
          isEdit={!!editingMedicine}
          initialData={editingMedicine}
          manufacturers={manufacturers}
          modalError={modalError}
          isSubmitting={isSubmitting}
          onClose={() => {
            setShowAddModal(false);
            setEditingMedicine(null);
            setModalError(null);
          }}
          onOpenQuickMfg={() => setShowQuickMfgModal(true)}
          onSubmit={async (payload) => {
            setIsSubmitting(true);
            setModalError(null);
            try {
              if (editingMedicine) {
                await mastersApi.updateMedicine(editingMedicine.id, payload as UpdateMedicineInput);
              } else {
                await mastersApi.createMedicine(payload as CreateMedicineInput);
              }
              setShowAddModal(false);
              setEditingMedicine(null);
              loadMedicines();
            } catch (err: unknown) {
              const msg = err instanceof Error ? err.message : "Failed to save medicine.";
              setModalError(msg);
            } finally {
              setIsSubmitting(false);
            }
          }}
        />
      )}

      {/* 5. Quick Manufacturer Creation Modal */}
      {showQuickMfgModal && (
        <div className="modal-backdrop" onClick={() => setShowQuickMfgModal(false)}>
          <div className="modal-dialog modal-dialog-medium" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title">+ Add New Manufacturer</div>
              <button className="btn btn-ghost btn-sm" onClick={() => setShowQuickMfgModal(false)}>✕</button>
            </div>
            <form onSubmit={handleQuickMfgSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label form-label-required">Company / Manufacturer Name</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. Sun Pharma Laboratories"
                    value={quickMfgName}
                    onChange={(e) => setQuickMfgName(e.target.value)}
                    autoFocus
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Short Code (Optional)</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. SUN"
                    value={quickMfgCode}
                    onChange={(e) => setQuickMfgCode(e.target.value)}
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => setShowQuickMfgModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary btn-sm">
                  Save Manufacturer
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 6. Deactivate Confirmation Modal */}
      <ConfirmModal
        isOpen={!!deactivatingMedicine}
        title="Confirm Medicine Deactivation"
        message="Are you sure you want to deactivate this medicine? It will be safely disabled from counter sales and searches while retaining historic batch and sale records."
        itemName={deactivatingMedicine ? `${deactivatingMedicine.brand_name} (${deactivatingMedicine.generic_salt})` : ""}
        confirmLabel="Deactivate Medicine"
        confirmVariant="danger"
        isLoading={isSubmitting}
        onConfirm={handleConfirmDeactivate}
        onCancel={() => setDeactivatingMedicine(null)}
      />
    </div>
  );
};

// ==========================================
// SUB-COMPONENT: MEDICINE FORM MODAL
// ==========================================

interface MedicineFormModalProps {
  isOpen: boolean;
  isEdit: boolean;
  initialData: Medicine | null;
  manufacturers: Manufacturer[];
  modalError: string | null;
  isSubmitting: boolean;
  onClose: () => void;
  onOpenQuickMfg: () => void;
  onSubmit: (payload: CreateMedicineInput | UpdateMedicineInput) => Promise<void>;
}

const MedicineFormModal: React.FC<MedicineFormModalProps> = ({
  isEdit,
  initialData,
  manufacturers,
  modalError,
  isSubmitting,
  onClose,
  onOpenQuickMfg,
  onSubmit,
}) => {
  const [formData, setFormData] = useState<CreateMedicineInput>({
    brand_name: initialData?.brand_name || "",
    generic_salt: initialData?.generic_salt || "",
    dosage_form: initialData?.dosage_form || "TABLET",
    strength: initialData?.strength || "",
    pack_size: initialData?.pack_size || 10,
    medicine_code: initialData?.medicine_code || "",
    barcode: initialData?.barcode || "",
    manufacturer_id: initialData?.manufacturer_id || null,
    hsn_code: initialData?.hsn_code || "3004",
    gst_rate: (initialData?.gst_rate as GSTRate) ?? 12,
    is_schedule_h1: initialData?.is_schedule_h1 || false,
    is_schedule_h: initialData?.is_schedule_h || false,
    is_narcotic: initialData?.is_narcotic || false,
    min_stock_units: initialData?.min_stock_units || 0,
    rack_location: initialData?.rack_location || "",
  });

  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const brandInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    brandInputRef.current?.focus();
  }, []);

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (!formData.brand_name.trim()) {
      errs.brand_name = "Brand name is required.";
    }
    if (!formData.generic_salt.trim()) {
      errs.generic_salt = "Generic salt composition is required.";
    }
    if (!formData.pack_size || formData.pack_size < 1) {
      errs.pack_size = "Pack size must be at least 1 unit.";
    }
    if (formData.hsn_code && !/^\d{4,8}$/.test(formData.hsn_code)) {
      errs.hsn_code = "HSN code must be 4 to 8 numeric digits (e.g. 3004).";
    }

    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    const payload: CreateMedicineInput = {
      ...formData,
      brand_name: formData.brand_name.trim(),
      generic_salt: formData.generic_salt.trim(),
      strength: formData.strength?.trim() || null,
      medicine_code: formData.medicine_code?.trim() || null,
      barcode: formData.barcode?.trim() || null,
      rack_location: formData.rack_location?.trim() || null,
      hsn_code: formData.hsn_code?.trim() || "3004",
      manufacturer_id: formData.manufacturer_id ? Number(formData.manufacturer_id) : null,
      pack_size: Number(formData.pack_size),
      gst_rate: Number(formData.gst_rate) as GSTRate,
      min_stock_units: Number(formData.min_stock_units || 0),
    };

    onSubmit(payload);
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-dialog modal-dialog-large" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" strokeWidth="2">
              <path d="m10.5 20.5 10-10a4.95 4.95 0 1 0-7-7l-10 10a4.95 4.95 0 1 0 7 7Z" />
              <path d="m8.5 8.5 7 7" />
            </svg>
            <span>{isEdit ? `Edit Medicine #${initialData?.id}` : "Add New Medicine"}</span>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={onClose} title="Close [Esc]">
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body" style={{ maxHeight: "72vh", overflowY: "auto" }}>
            {modalError && <div className="auth-error-banner">{modalError}</div>}

            {/* Core Identification */}
            <div className="form-grid-2">
              <div className="form-group">
                <label className="form-label form-label-required">Brand / Trade Name</label>
                <input
                  ref={brandInputRef}
                  type="text"
                  className={`form-input ${fieldErrors.brand_name ? "form-input-error" : ""}`}
                  placeholder="e.g. Augmentin 625 Duo"
                  value={formData.brand_name}
                  onChange={(e) => setFormData({ ...formData, brand_name: e.target.value })}
                  disabled={isSubmitting}
                />
                {fieldErrors.brand_name && <span className="form-error-text">{fieldErrors.brand_name}</span>}
              </div>

              <div className="form-group">
                <label className="form-label form-label-required">Generic Salt Composition</label>
                <input
                  type="text"
                  className={`form-input ${fieldErrors.generic_salt ? "form-input-error" : ""}`}
                  placeholder="e.g. Amoxicillin 500mg + Clavulanic Acid 125mg"
                  value={formData.generic_salt}
                  onChange={(e) => setFormData({ ...formData, generic_salt: e.target.value })}
                  disabled={isSubmitting}
                />
                {fieldErrors.generic_salt && <span className="form-error-text">{fieldErrors.generic_salt}</span>}
              </div>
            </div>

            {/* Formulation & Strength */}
            <div className="form-grid-3">
              <div className="form-group">
                <label className="form-label form-label-required">Dosage Form</label>
                <select
                  className="select-filter form-input"
                  value={formData.dosage_form}
                  onChange={(e) => setFormData({ ...formData, dosage_form: e.target.value as DosageForm })}
                  disabled={isSubmitting}
                >
                  {VALID_DOSAGE_FORMS.map((form) => (
                    <option key={form} value={form}>{form}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Strength</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. 625mg or 10mg/ml"
                  value={formData.strength || ""}
                  onChange={(e) => setFormData({ ...formData, strength: e.target.value })}
                  disabled={isSubmitting}
                />
              </div>

              <div className="form-group">
                <label className="form-label form-label-required">Pack Size (Units)</label>
                <input
                  type="number"
                  min="1"
                  className={`form-input ${fieldErrors.pack_size ? "form-input-error" : ""}`}
                  value={formData.pack_size}
                  onChange={(e) => setFormData({ ...formData, pack_size: Number(e.target.value) })}
                  disabled={isSubmitting}
                />
                {fieldErrors.pack_size && <span className="form-error-text">{fieldErrors.pack_size}</span>}
              </div>
            </div>

            {/* Manufacturer Selection & Codes */}
            <div className="form-grid-3">
              <div className="form-group">
                <label className="form-label" style={{ display: "flex", justifyContent: "space-between" }}>
                  <span>Manufacturer</span>
                  <button
                    type="button"
                    onClick={onOpenQuickMfg}
                    style={{ background: "none", border: "none", color: "#38bdf8", cursor: "pointer", fontSize: "0.72rem" }}
                  >
                    + New
                  </button>
                </label>
                <select
                  className="select-filter form-input"
                  value={formData.manufacturer_id || ""}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      manufacturer_id: e.target.value ? Number(e.target.value) : null,
                    })
                  }
                  disabled={isSubmitting}
                >
                  <option value="">Select Manufacturer...</option>
                  {manufacturers.map((mfg) => (
                    <option key={mfg.id} value={mfg.id}>
                      {mfg.name} {mfg.short_code ? `(${mfg.short_code})` : ""}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Item / Medicine Code</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. AUG-625"
                  value={formData.medicine_code || ""}
                  onChange={(e) => setFormData({ ...formData, medicine_code: e.target.value })}
                  disabled={isSubmitting}
                />
              </div>

              <div className="form-group">
                <label className="form-label">EAN / Barcode</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. 8901234567890"
                  value={formData.barcode || ""}
                  onChange={(e) => setFormData({ ...formData, barcode: e.target.value })}
                  disabled={isSubmitting}
                />
              </div>
            </div>

            {/* Tax, Logistics & Shelf Coordinate */}
            <div className="form-grid-3">
              <div className="form-group">
                <label className="form-label">HSN Code</label>
                <input
                  type="text"
                  className={`form-input ${fieldErrors.hsn_code ? "form-input-error" : ""}`}
                  placeholder="3004"
                  value={formData.hsn_code || "3004"}
                  onChange={(e) => setFormData({ ...formData, hsn_code: e.target.value })}
                  disabled={isSubmitting}
                />
                {fieldErrors.hsn_code && <span className="form-error-text">{fieldErrors.hsn_code}</span>}
              </div>

              <div className="form-group">
                <label className="form-label">GST Tax Slab</label>
                <select
                  className="select-filter form-input"
                  value={formData.gst_rate}
                  onChange={(e) => setFormData({ ...formData, gst_rate: Number(e.target.value) as GSTRate })}
                  disabled={isSubmitting}
                >
                  {VALID_GST_RATES.map((rate) => (
                    <option key={rate} value={rate}>
                      {rate}% GST
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Rack / Shelf Location</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. A-12, RACK-03"
                  value={formData.rack_location || ""}
                  onChange={(e) => setFormData({ ...formData, rack_location: e.target.value })}
                  disabled={isSubmitting}
                />
              </div>
            </div>

            {/* Regulatory & Compliance Checkboxes */}
            <div
              style={{
                marginTop: 8,
                padding: "10px 14px",
                backgroundColor: "var(--bg-input)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-sm)",
              }}
            >
              <span style={{ fontSize: "0.78rem", fontWeight: 700, color: "var(--text-muted)" }}>
                Statutory Compliance & Restriction Flags
              </span>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginTop: 6 }}>
                <label className="form-checkbox-row">
                  <input
                    type="checkbox"
                    checked={formData.is_schedule_h1}
                    onChange={(e) => setFormData({ ...formData, is_schedule_h1: e.target.checked })}
                  />
                  <span style={{ color: "#fca5a5" }}>Schedule H1 (Statutory Register)</span>
                </label>

                <label className="form-checkbox-row">
                  <input
                    type="checkbox"
                    checked={formData.is_schedule_h}
                    onChange={(e) => setFormData({ ...formData, is_schedule_h: e.target.checked })}
                  />
                  <span style={{ color: "#fcd34d" }}>Schedule H (Prescription Req.)</span>
                </label>

                <label className="form-checkbox-row">
                  <input
                    type="checkbox"
                    checked={formData.is_narcotic}
                    onChange={(e) => setFormData({ ...formData, is_narcotic: e.target.checked })}
                  />
                  <span style={{ color: "#d8b4fe" }}>Narcotic (Schedule X)</span>
                </label>
              </div>
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-secondary btn-sm" onClick={onClose} disabled={isSubmitting}>
              Cancel [Esc]
            </button>
            <button type="submit" className="btn btn-primary btn-sm" disabled={isSubmitting}>
              {isSubmitting ? "Saving..." : isEdit ? "Update Medicine" : "Create Medicine"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
