import React, { useEffect, useState } from "react";
import type { SubstituteMedicine } from "@pharmacy/api-contracts";
import { formatRupees } from "@pharmacy/api-contracts";

interface SubstituteModalProps {
  isOpen: boolean;
  onClose: () => void;
  originalMedicineName: string;
  genericSalt: string;
  substitutes: SubstituteMedicine[];
  onSelectSubstitute: (medicine: SubstituteMedicine) => void;
}

export const SubstituteModal: React.FC<SubstituteModalProps> = ({
  isOpen,
  onClose,
  originalMedicineName,
  genericSalt,
  substitutes,
  onSelectSubstitute,
}) => {
  const [selectedIndex, setSelectedIndex] = useState<number>(0);

  useEffect(() => {
    if (isOpen) {
      setSelectedIndex(0);
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev < substitutes.length - 1 ? prev + 1 : prev));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev > 0 ? prev - 1 : prev));
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (substitutes[selectedIndex]) {
          onSelectSubstitute(substitutes[selectedIndex]);
          onClose();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, substitutes, selectedIndex, onSelectSubstitute, onClose]);

  if (!isOpen) return null;

  return (
    <div className="pos-modal-overlay">
      <div className="pos-modal-card" style={{ maxWidth: 750 }}>
        <div className="pos-modal-header">
          <h3>Generic Substitutes — {originalMedicineName}</h3>
          <button type="button" className="pos-modal-close" onClick={onClose} title="Close [Esc]">
            &times;
          </button>
        </div>

        <div style={{ padding: "8px 16px", backgroundColor: "var(--bg-secondary, #1e293b)", fontSize: "0.85rem", borderBottom: "1px solid var(--border-color)" }}>
          <span style={{ color: "var(--text-dim)" }}>Matching Composition: </span>
          <strong style={{ color: "#38bdf8" }}>{genericSalt}</strong>
        </div>

        <div className="pos-modal-body" style={{ maxHeight: 380, overflowY: "auto", padding: 0 }}>
          {substitutes.length === 0 ? (
            <div style={{ padding: 32, textAlign: "center", color: "var(--text-dim)" }}>
              No in-stock substitute brands found with identical composition.
            </div>
          ) : (
            <table className="pos-table" style={{ width: "100%", margin: 0 }}>
              <thead>
                <tr>
                  <th style={{ width: 40 }}>#</th>
                  <th>Brand Name</th>
                  <th>Form</th>
                  <th>Pack</th>
                  <th style={{ textAlign: "right" }}>Total Stock</th>
                  <th style={{ textAlign: "right" }}>Pack MRP</th>
                  <th>Recommended Batch</th>
                  <th style={{ textAlign: "center" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {substitutes.map((sub, idx) => {
                  const isSelected = idx === selectedIndex;
                  return (
                    <tr
                      key={sub.id}
                      style={{
                        backgroundColor: isSelected ? "var(--bg-active, #1e293b)" : undefined,
                        cursor: "pointer",
                      }}
                      onClick={() => {
                        onSelectSubstitute(sub);
                        onClose();
                      }}
                      onMouseEnter={() => setSelectedIndex(idx)}
                    >
                      <td style={{ textAlign: "center" }}>{idx + 1}</td>
                      <td>
                        <strong>{sub.brand_name}</strong>
                        {sub.is_schedule_h1 && (
                          <span className="badge badge-danger" style={{ marginLeft: 6, fontSize: "0.65rem" }}>
                            H1
                          </span>
                        )}
                        {sub.rack_location && (
                          <div style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>
                            Rack: {sub.rack_location}
                          </div>
                        )}
                      </td>
                      <td>{sub.dosage_form}</td>
                      <td>{sub.pack_size}s</td>
                      <td style={{ textAlign: "right", fontWeight: 700, color: "#10b981" }}>
                        {sub.total_stock_units} units
                      </td>
                      <td style={{ textAlign: "right" }}>
                        {sub.recommended_mrp_paise ? formatRupees(sub.recommended_mrp_paise) : "—"}
                      </td>
                      <td style={{ fontFamily: "monospace", fontSize: "0.8rem" }}>
                        {sub.recommended_batch_number || "—"} ({sub.recommended_expiry_date || "—"})
                      </td>
                      <td style={{ textAlign: "center" }}>
                        <button
                          type="button"
                          className="btn btn-sm btn-primary"
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectSubstitute(sub);
                            onClose();
                          }}
                        >
                          Select
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        <div className="pos-modal-footer" style={{ display: "flex", justifyContent: "space-between" }}>
          <div style={{ fontSize: "0.8rem", color: "var(--text-dim)" }}>
            Use <kbd>&uarr;</kbd> <kbd>&darr;</kbd> to navigate, <kbd>Enter</kbd> to substitute, <kbd>Esc</kbd> to cancel.
          </div>
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};
