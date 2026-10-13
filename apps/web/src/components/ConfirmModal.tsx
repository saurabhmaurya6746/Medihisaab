import React, { useEffect } from "react";

interface ConfirmModalProps {
  isOpen: boolean;
  title: string;
  message: string;
  itemName?: string;
  confirmLabel?: string;
  confirmVariant?: "danger" | "primary" | "warning";
  isLoading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export const ConfirmModal: React.FC<ConfirmModalProps> = ({
  isOpen,
  title,
  message,
  itemName,
  confirmLabel = "Confirm",
  confirmVariant = "danger",
  isLoading = false,
  onConfirm,
  onCancel,
}) => {
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onCancel();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onCancel]);

  if (!isOpen) return null;

  const btnClass =
    confirmVariant === "danger"
      ? "btn-danger"
      : confirmVariant === "warning"
      ? "btn-secondary"
      : "btn-primary";

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal-dialog modal-dialog-medium" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title" style={{ color: confirmVariant === "danger" ? "#f87171" : "#ffffff" }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
              <line x1="12" y1="9" x2="12" y2="13" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
            <span>{title}</span>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={onCancel}>
            ✕
          </button>
        </div>

        <div className="modal-body">
          <p style={{ fontSize: "0.9rem", color: "var(--text-main)", marginBottom: itemName ? 8 : 0 }}>
            {message}
          </p>
          {itemName && (
            <div
              style={{
                padding: "8px 12px",
                backgroundColor: "var(--bg-input)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-sm)",
                fontFamily: "var(--font-mono)",
                fontWeight: 600,
                color: "#38bdf8",
                fontSize: "0.88rem",
              }}
            >
              {itemName}
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary btn-sm" onClick={onCancel} disabled={isLoading}>
            Cancel [Esc]
          </button>
          <button
            className={`btn ${btnClass} btn-sm`}
            onClick={onConfirm}
            disabled={isLoading}
            autoFocus
          >
            {isLoading ? "Processing..." : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
};
