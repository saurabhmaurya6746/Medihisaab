import React, { useEffect, useState } from "react";
import type { HeldBill } from "@pharmacy/api-contracts";
import { formatRupees } from "@pharmacy/api-contracts";

interface HeldBillsModalProps {
  isOpen: boolean;
  onClose: () => void;
  heldBills: HeldBill[];
  onRecallBill: (bill: HeldBill) => void;
  onDeleteBill: (id: number) => void;
}

export const HeldBillsModal: React.FC<HeldBillsModalProps> = ({
  isOpen,
  onClose,
  heldBills,
  onRecallBill,
  onDeleteBill,
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
        setSelectedIndex((prev) => (prev < heldBills.length - 1 ? prev + 1 : prev));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev > 0 ? prev - 1 : prev));
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (heldBills[selectedIndex]) {
          onRecallBill(heldBills[selectedIndex]);
          onClose();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, heldBills, selectedIndex, onRecallBill, onClose]);

  if (!isOpen) return null;

  return (
    <div className="pos-modal-overlay">
      <div className="pos-modal-card" style={{ maxWidth: 700 }}>
        <div className="pos-modal-header">
          <h3>Recall Held Bills</h3>
          <button type="button" className="pos-modal-close" onClick={onClose} title="Close [Esc]">
            &times;
          </button>
        </div>

        <div className="pos-modal-body" style={{ maxHeight: 380, overflowY: "auto", padding: 0 }}>
          {heldBills.length === 0 ? (
            <div style={{ padding: 32, textAlign: "center", color: "var(--text-dim)" }}>
              No held bills currently parked. Use <kbd>Ctrl+H</kbd> to park an active bill.
            </div>
          ) : (
            <table className="pos-table" style={{ width: "100%", margin: 0 }}>
              <thead>
                <tr>
                  <th>Ref No</th>
                  <th>Customer / Notes</th>
                  <th style={{ textAlign: "center" }}>Items</th>
                  <th style={{ textAlign: "right" }}>Total Amount</th>
                  <th>Parked Time</th>
                  <th style={{ textAlign: "center" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {heldBills.map((bill, idx) => {
                  const isSelected = idx === selectedIndex;
                  return (
                    <tr
                      key={bill.id}
                      style={{
                        backgroundColor: isSelected ? "var(--bg-active, #1e293b)" : undefined,
                        cursor: "pointer",
                      }}
                      onClick={() => {
                        onRecallBill(bill);
                        onClose();
                      }}
                      onMouseEnter={() => setSelectedIndex(idx)}
                    >
                      <td style={{ fontWeight: 700, fontFamily: "monospace", color: "#38bdf8" }}>
                        {bill.hold_reference}
                      </td>
                      <td>
                        <strong>{bill.customer_name || "Walk-in Customer"}</strong>
                        {bill.notes && (
                          <div style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>
                            Note: {bill.notes}
                          </div>
                        )}
                      </td>
                      <td style={{ textAlign: "center" }}>{bill.items.length}</td>
                      <td style={{ textAlign: "right", fontWeight: 700, color: "#10b981" }}>
                        {formatRupees(bill.grand_total_paise)}
                      </td>
                      <td style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>
                        {bill.created_at.slice(11, 19)}
                      </td>
                      <td style={{ textAlign: "center" }}>
                        <div style={{ display: "flex", gap: 6, justifyContent: "center" }}>
                          <button
                            type="button"
                            className="btn btn-sm btn-primary"
                            onClick={(e) => {
                              e.stopPropagation();
                              onRecallBill(bill);
                              onClose();
                            }}
                          >
                            Recall
                          </button>
                          <button
                            type="button"
                            className="btn btn-sm btn-danger"
                            onClick={(e) => {
                              e.stopPropagation();
                              if (window.confirm(`Discard held bill ${bill.hold_reference}?`)) {
                                onDeleteBill(bill.id);
                              }
                            }}
                          >
                            &times;
                          </button>
                        </div>
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
            Use <kbd>&uarr;</kbd> <kbd>&darr;</kbd> to navigate, <kbd>Enter</kbd> to recall, <kbd>Esc</kbd> to close.
          </div>
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
