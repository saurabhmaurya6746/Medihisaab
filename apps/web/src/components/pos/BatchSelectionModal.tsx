import React, { useEffect, useState } from "react";
import type { BatchItemResult } from "../../api/sales";
import { formatRupees } from "@pharmacy/api-contracts";

interface BatchSelectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  medicineName: string;
  batches: BatchItemResult[];
  selectedBatchId?: number | null;
  onSelectBatch: (batch: BatchItemResult) => void;
}

export const BatchSelectionModal: React.FC<BatchSelectionModalProps> = ({
  isOpen,
  onClose,
  medicineName,
  batches,
  selectedBatchId,
  onSelectBatch,
}) => {
  const [selectedIndex, setSelectedIndex] = useState<number>(0);

  useEffect(() => {
    if (isOpen) {
      const idx = batches.findIndex((b) => b.id === selectedBatchId);
      setSelectedIndex(idx >= 0 ? idx : 0);
    }
  }, [isOpen, batches, selectedBatchId]);

  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev < batches.length - 1 ? prev + 1 : prev));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev > 0 ? prev - 1 : prev));
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (batches[selectedIndex] && batches[selectedIndex].is_available) {
          onSelectBatch(batches[selectedIndex]);
          onClose();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, batches, selectedIndex, onSelectBatch, onClose]);

  if (!isOpen) return null;

  return (
    <div className="pos-modal-overlay">
      <div className="pos-modal-card" style={{ maxWidth: 680 }}>
        <div className="pos-modal-header">
          <h3>Select Batch — {medicineName}</h3>
          <button type="button" className="pos-modal-close" onClick={onClose} title="Close [Esc]">
            &times;
          </button>
        </div>

        <div className="pos-modal-body" style={{ maxHeight: 380, overflowY: "auto", padding: 0 }}>
          {batches.length === 0 ? (
            <div style={{ padding: 24, textAlign: "center", color: "var(--text-dim)" }}>
              No batches available for this medicine.
            </div>
          ) : (
            <table className="pos-table" style={{ width: "100%", margin: 0 }}>
              <thead>
                <tr>
                  <th style={{ width: 40 }}>#</th>
                  <th>Batch No</th>
                  <th>Expiry</th>
                  <th style={{ textAlign: "right" }}>Pack MRP</th>
                  <th style={{ textAlign: "right" }}>Unit MRP</th>
                  <th style={{ textAlign: "right" }}>Stock (Units)</th>
                  <th style={{ textAlign: "center" }}>Status</th>
                  <th style={{ textAlign: "center" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {batches.map((batch, idx) => {
                  const isSelected = idx === selectedIndex;
                  const isCurrent = batch.id === selectedBatchId;
                  const canPick = batch.is_available;

                  return (
                    <tr
                      key={batch.id}
                      style={{
                        backgroundColor: isSelected ? "var(--bg-active, #1e293b)" : undefined,
                        cursor: canPick ? "pointer" : "not-allowed",
                        opacity: canPick ? 1 : 0.55,
                      }}
                      onClick={() => {
                        if (canPick) {
                          onSelectBatch(batch);
                          onClose();
                        }
                      }}
                      onMouseEnter={() => setSelectedIndex(idx)}
                    >
                      <td style={{ textAlign: "center" }}>
                        {isCurrent && <span style={{ color: "#10b981" }}>&#10003;</span>}
                      </td>
                      <td style={{ fontWeight: 600, fontFamily: "monospace" }}>{batch.batch_number}</td>
                      <td>
                        <span
                          style={{
                            color: batch.is_expired ? "#ef4444" : undefined,
                            fontWeight: batch.is_expired ? 700 : undefined,
                          }}
                        >
                          {batch.expiry_date}
                        </span>
                      </td>
                      <td style={{ textAlign: "right" }}>{formatRupees(batch.mrp_paise)}</td>
                      <td style={{ textAlign: "right", color: "#38bdf8" }}>{formatRupees(batch.unit_mrp_paise)}</td>
                      <td style={{ textAlign: "right", fontWeight: 600 }}>{batch.current_quantity}</td>
                      <td style={{ textAlign: "center" }}>
                        {batch.is_expired ? (
                          <span className="badge badge-danger">Expired</span>
                        ) : batch.current_quantity <= 0 ? (
                          <span className="badge badge-warning">Out of stock</span>
                        ) : (
                          <span className="badge badge-success">In stock</span>
                        )}
                      </td>
                      <td style={{ textAlign: "center" }}>
                        <button
                          type="button"
                          className="btn btn-sm btn-primary"
                          disabled={!canPick}
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectBatch(batch);
                            onClose();
                          }}
                        >
                          Pick
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
            Use <kbd>&uarr;</kbd> <kbd>&darr;</kbd> to navigate, <kbd>Enter</kbd> to pick, <kbd>Esc</kbd> to close.
          </div>
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
