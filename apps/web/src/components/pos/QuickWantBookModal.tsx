import React, { useState, useEffect, useRef } from "react";
import type { Supplier, Medicine } from "@pharmacy/api-contracts";
import * as mastersApi from "../../api/masters";
import * as inventoryApi from "../../api/inventory";

interface QuickWantBookModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialMedicineId?: number;
  initialMedicineName?: string;
  onSuccess?: () => void;
}

export const QuickWantBookModal: React.FC<QuickWantBookModalProps> = ({
  isOpen,
  onClose,
  initialMedicineId,
  initialMedicineName,
  onSuccess,
}) => {
  const [medicines, setMedicines] = useState<Medicine[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [selectedMedicineId, setSelectedMedicineId] = useState<number | null>(
    initialMedicineId || null
  );
  const [searchQuery, setSearchQuery] = useState<string>(initialMedicineName || "");
  const [quantityPacks, setQuantityPacks] = useState<number>(10);
  const [selectedSupplierId, setSelectedSupplierId] = useState<number | null>(null);
  const [notes, setNotes] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const searchInputRef = useRef<HTMLInputElement>(null);
  const qtyInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setError(null);
      setSuccessMessage(null);
      if (initialMedicineId) {
        setSelectedMedicineId(initialMedicineId);
        setSearchQuery(initialMedicineName || "");
        setTimeout(() => qtyInputRef.current?.focus(), 50);
      } else {
        setSelectedMedicineId(null);
        setSearchQuery("");
        setTimeout(() => searchInputRef.current?.focus(), 50);
      }

      // Load active suppliers
      mastersApi
        .listSuppliers({ page_size: 100, is_active: true })
        .then((res) => setSuppliers(res.items))
        .catch((err) => console.error("Failed to load suppliers:", err));
    }
  }, [isOpen, initialMedicineId, initialMedicineName]);

  // Search medicines on typing
  useEffect(() => {
    if (!isOpen || selectedMedicineId !== null) return;
    if (searchQuery.trim().length >= 2) {
      const timer = setTimeout(() => {
        mastersApi
          .listMedicines({ query: searchQuery.trim(), page_size: 15, is_active: true })
          .then((res) => setMedicines(res.items))
          .catch((err: unknown) => console.error("Failed to search medicines:", err));
      }, 200);
      return () => clearTimeout(timer);
    } else {
      setMedicines([]);
    }
  }, [searchQuery, isOpen, selectedMedicineId]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedMedicineId) {
      setError("Please select a medicine to add to Want-Book.");
      return;
    }
    if (quantityPacks <= 0) {
      setError("Requested quantity must be at least 1 pack.");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      await inventoryApi.createWantBookItem({
        medicine_id: selectedMedicineId,
        requested_quantity_packs: quantityPacks,
        supplier_id: selectedSupplierId || undefined,
        notes: notes.trim() || undefined,
      });

      setSuccessMessage("Medicine added to Want-Book successfully!");
      if (onSuccess) onSuccess();
      setTimeout(() => {
        onClose();
      }, 700);
    } catch (err: any) {
      setError(err.message || "Failed to add to Want-Book.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      className="modal-backdrop"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(0, 0, 0, 0.75)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="modal-box"
        style={{
          width: "520px",
          backgroundColor: "var(--bg-surface)",
          border: "1px solid var(--border-subtle)",
          borderRadius: "var(--radius-lg)",
          boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.5)",
          overflow: "hidden",
        }}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            e.stopPropagation();
            onClose();
          }
        }}
      >
        <div
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid var(--border-subtle)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            background: "linear-gradient(180deg, rgba(2, 132, 199, 0.1) 0%, transparent 100%)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span
              style={{
                backgroundColor: "rgba(2, 132, 199, 0.2)",
                color: "var(--accent-primary)",
                padding: "4px 8px",
                borderRadius: 4,
                fontWeight: 700,
                fontSize: "0.75rem",
              }}
            >
              Ctrl+W
            </span>
            <h3 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: "var(--text-main)" }}>
              Quick Want-Book Entry
            </h3>
          </div>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={onClose}
            style={{ padding: "2px 8px" }}
          >
            Esc
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ padding: "20px" }}>
          {error && (
            <div
              style={{
                backgroundColor: "rgba(239, 68, 68, 0.15)",
                border: "1px solid var(--accent-danger)",
                color: "#fca5a5",
                padding: "8px 12px",
                borderRadius: "var(--radius-sm)",
                marginBottom: 16,
                fontSize: "0.85rem",
              }}
            >
              {error}
            </div>
          )}

          {successMessage && (
            <div
              style={{
                backgroundColor: "rgba(16, 185, 129, 0.15)",
                border: "1px solid var(--accent-success)",
                color: "#6ee7b7",
                padding: "8px 12px",
                borderRadius: "var(--radius-sm)",
                marginBottom: 16,
                fontSize: "0.85rem",
              }}
            >
              {successMessage}
            </div>
          )}

          {/* Medicine Selection / Search */}
          <div style={{ marginBottom: 16 }}>
            <label
              style={{
                display: "block",
                marginBottom: 6,
                fontSize: "0.82rem",
                color: "var(--text-muted)",
              }}
            >
              Medicine <span style={{ color: "var(--accent-danger)" }}>*</span>
            </label>
            {selectedMedicineId ? (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  background: "var(--bg-input)",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "var(--radius-sm)",
                  padding: "8px 12px",
                }}
              >
                <div>
                  <span style={{ fontWeight: 600, color: "#38bdf8" }}>{searchQuery}</span>
                </div>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  style={{ fontSize: "0.75rem", padding: "2px 8px" }}
                  onClick={() => {
                    setSelectedMedicineId(null);
                    setSearchQuery("");
                    setTimeout(() => searchInputRef.current?.focus(), 50);
                  }}
                >
                  Change
                </button>
              </div>
            ) : (
              <div style={{ position: "relative" }}>
                <input
                  ref={searchInputRef}
                  type="text"
                  className="input-field"
                  placeholder="Type medicine name or salt to search..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  style={{ width: "100%", padding: "8px 12px" }}
                />
                {medicines.length > 0 && (
                  <div
                    style={{
                      position: "absolute",
                      top: "100%",
                      left: 0,
                      right: 0,
                      backgroundColor: "var(--bg-surface-elevated)",
                      border: "1px solid var(--border-subtle)",
                      borderRadius: "0 0 6px 6px",
                      maxHeight: "180px",
                      overflowY: "auto",
                      zIndex: 10,
                      boxShadow: "0 8px 16px rgba(0,0,0,0.4)",
                    }}
                  >
                    {medicines.map((m) => (
                      <div
                        key={m.id}
                        onClick={() => {
                          setSelectedMedicineId(m.id);
                          setSearchQuery(`${m.brand_name} (${m.dosage_form})`);
                          setTimeout(() => qtyInputRef.current?.focus(), 50);
                        }}
                        style={{
                          padding: "8px 12px",
                          cursor: "pointer",
                          borderBottom: "1px solid rgba(255,255,255,0.05)",
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "#1e293b")}
                        onMouseLeave={(e) =>
                          (e.currentTarget.style.backgroundColor = "transparent")
                        }
                      >
                        <div>
                          <strong style={{ color: "#f9fafb" }}>{m.brand_name}</strong>
                          <span style={{ color: "var(--text-dim)", marginLeft: 6, fontSize: "0.8rem" }}>
                            {m.dosage_form}
                          </span>
                        </div>
                        <div style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
                          Pack: {m.pack_size}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Requested Quantity (Packs) & Preferred Supplier */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
            <div>
              <label
                style={{
                  display: "block",
                  marginBottom: 6,
                  fontSize: "0.82rem",
                  color: "var(--text-muted)",
                }}
              >
                Quantity (Packs) <span style={{ color: "var(--accent-danger)" }}>*</span>
              </label>
              <input
                ref={qtyInputRef}
                type="number"
                min="1"
                step="1"
                className="input-field"
                value={quantityPacks}
                onChange={(e) => setQuantityPacks(parseInt(e.target.value, 10) || 0)}
                style={{ width: "100%", padding: "8px 12px" }}
              />
            </div>

            <div>
              <label
                style={{
                  display: "block",
                  marginBottom: 6,
                  fontSize: "0.82rem",
                  color: "var(--text-muted)",
                }}
              >
                Preferred Supplier
              </label>
              <select
                className="input-field"
                value={selectedSupplierId || ""}
                onChange={(e) =>
                  setSelectedSupplierId(e.target.value ? Number(e.target.value) : null)
                }
                style={{ width: "100%", padding: "8px 12px" }}
              >
                <option value="">-- None / Any --</option>
                {suppliers.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Notes */}
          <div style={{ marginBottom: 20 }}>
            <label
              style={{
                display: "block",
                marginBottom: 6,
                fontSize: "0.82rem",
                color: "var(--text-muted)",
              }}
            >
              Notes / Reason (e.g., Customer inquiry, Urgent shortage)
            </label>
            <input
              type="text"
              className="input-field"
              placeholder="e.g., Demanded by 3 walk-ins today"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              style={{ width: "100%", padding: "8px 12px" }}
            />
          </div>

          {/* Footer Actions */}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={isSubmitting || !selectedMedicineId}
            >
              {isSubmitting ? "Adding..." : "Add to Want-Book"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
