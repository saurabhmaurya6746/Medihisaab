import React, { useEffect } from "react";

interface ShortcutsHelpModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface ShortcutGroup {
  category: string;
  shortcuts: { key: string; description: string }[];
}

const SHORTCUT_GROUPS: ShortcutGroup[] = [
  {
    category: "Navigation & Terminal",
    shortcuts: [
      { key: "F1", description: "Counter Sales & Billing" },
      { key: "F2", description: "Medicines Master" },
      { key: "F3", description: "Suppliers Master" },
      { key: "F4", description: "Customer Khata (Credit Ledger)" },
      { key: "F5", description: "Customers Master" },
      { key: "F6", description: "Purchases & Inwarding" },
      { key: "F7", description: "Inventory & Expiry Tracking" },
      { key: "F8", description: "Physical Stock Audit" },
      { key: "F9", description: "Admin Reports & Registers" },
      { key: "F10", description: "Log Out / Exit Terminal" },
      { key: "F11", description: "Fast Operator Switch (PIN)" },
      { key: "F12", description: "Open this Shortcuts Help Panel" },
    ],
  },
  {
    category: "Billing Counter (F1)",
    shortcuts: [
      { key: "Enter", description: "Search / Add Item to Cart / Confirm" },
      { key: "F2", description: "Change Batch for Selected Medicine" },
      { key: "F3", description: "Search Generic Salt Substitutes" },
      { key: "F9", description: "Proceed to Payment & Checkout" },
      { key: "Ctrl + H", description: "Hold Current Bill" },
      { key: "Ctrl + R", description: "Recall Held Bill" },
      { key: "Ctrl + W", description: "Add Medicine to Reorder / Want-Book" },
      { key: "Ctrl + K", description: "Customer Khata Deposit" },
      { key: "Esc", description: "Close Active Modal / Cancel Action" },
    ],
  },
  {
    category: "Returns & Scrap Registers",
    shortcuts: [
      { key: "Ctrl + Shift + R", description: "Customer Sales Returns" },
      { key: "Ctrl + Shift + P", description: "Supplier Purchase Returns (Debit Note)" },
      { key: "Ctrl + Shift + W", description: "Wastage & Breakage Scrap Register" },
    ],
  },
];

export const ShortcutsHelpModal: React.FC<ShortcutsHelpModalProps> = ({ isOpen, onClose }) => {
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal-dialog"
        style={{ maxWidth: 650 }}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="shortcuts-dialog-title"
      >
        <div className="modal-header">
          <div className="modal-title" id="shortcuts-dialog-title">
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              style={{ color: "var(--accent-primary)" }}
            >
              <rect x="2" y="4" width="20" height="16" rx="2" />
              <path d="M6 8h.001M10 8h.001M14 8h.001M18 8h.001M6 12h.001M10 12h.001M14 12h.001M18 12h.001M8 16h8" />
            </svg>
            <span>Keyboard Shortcuts Guide</span>
          </div>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={onClose}
            title="Close [Esc]"
            aria-label="Close shortcuts guide"
          >
            ✕
          </button>
        </div>

        <div className="modal-body" style={{ maxHeight: "65vh", overflowY: "auto", display: "flex", flexDirection: "column", gap: 18 }}>
          {SHORTCUT_GROUPS.map((group) => (
            <div key={group.category}>
              <h4 style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--text-dim)", textTransform: "none", marginBottom: 8 }}>
                {group.category}
              </h4>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: "6px 12px",
                  background: "var(--bg-card, #111827)",
                  padding: "10px 14px",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--border-subtle)",
                }}
              >
                {group.shortcuts.map((sc) => (
                  <div
                    key={sc.key}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      fontSize: "0.82rem",
                      padding: "3px 0",
                    }}
                  >
                    <span style={{ color: "var(--text-muted)" }}>{sc.description}</span>
                    <kbd
                      style={{
                        padding: "2px 6px",
                        borderRadius: "3px",
                        fontSize: "0.75rem",
                        fontFamily: "var(--font-mono)",
                        background: "var(--kbd-bg)",
                        color: "var(--kbd-color)",
                        border: "1px solid var(--kbd-border)",
                      }}
                    >
                      {sc.key}
                    </kbd>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="modal-footer" style={{ justifyContent: "space-between" }}>
          <span style={{ fontSize: "0.78rem", color: "var(--text-dim)" }}>
            Tip: Hover over any button to see its keyboard shortcut tooltip.
          </span>
          <button type="button" className="btn btn-secondary btn-sm" onClick={onClose}>
            Close [Esc]
          </button>
        </div>
      </div>
    </div>
  );
};
