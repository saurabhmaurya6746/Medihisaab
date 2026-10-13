import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";

interface PinSwitchModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
}

export const PinSwitchModal: React.FC<PinSwitchModalProps> = ({
  isOpen,
  onClose,
  title = "Quick Operator Switch",
}) => {
  const { performPinSwitch } = useAuth();
  const [pin, setPin] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const resetState = useCallback(() => {
    setPin("");
    setError(null);
    setIsSubmitting(false);
  }, []);

  const handleClose = useCallback(() => {
    resetState();
    onClose();
  }, [onClose, resetState]);

  const submitPin = useCallback(async (pinToSubmit: string) => {
    if (pinToSubmit.length !== 4) {
      setError("Please enter complete 4-digit PIN.");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      await performPinSwitch({ pin: pinToSubmit });
      handleClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Invalid operator PIN.";
      setError(msg);
      setPin(""); // Clear on error so operator can immediately try again
    } finally {
      setIsSubmitting(false);
    }
  }, [performPinSwitch, handleClose]);

  // Handle keypresses directly when modal is open
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        handleClose();
      } else if (e.key >= "0" && e.key <= "9") {
        e.preventDefault();
        if (pin.length < 4) {
          const nextPin = pin + e.key;
          setPin(nextPin);
          if (nextPin.length === 4) {
            submitPin(nextPin);
          }
        }
      } else if (e.key === "Backspace") {
        e.preventDefault();
        setPin((prev) => prev.slice(0, -1));
        setError(null);
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (pin.length === 4) {
          submitPin(pin);
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, pin, handleClose, submitPin]);

  if (!isOpen) return null;

  const handleKeyClick = (digit: string) => {
    if (pin.length < 4) {
      const nextPin = pin + digit;
      setPin(nextPin);
      if (nextPin.length === 4) {
        submitPin(nextPin);
      }
    }
  };

  const handleClear = () => {
    setPin("");
    setError(null);
  };

  return (
    <div className="modal-backdrop" onClick={handleClose}>
      <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#38bdf8"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
            <span>{title}</span>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={handleClose} title="Close [Esc]">
            ✕
          </button>
        </div>

        <div className="modal-body">
          <p style={{ textAlign: "center", fontSize: "0.86rem", color: "var(--text-muted)", marginBottom: 16 }}>
            Enter your 4-digit numeric operator PIN to switch counter identity:
          </p>

          {error && <div className="auth-error-banner">{error}</div>}

          <div className="pin-pad-container">
            {/* Visual PIN dots */}
            <div className="pin-display-dots">
              {[0, 1, 2, 3].map((index) => (
                <div
                  key={index}
                  className={`pin-dot ${pin.length > index ? "filled" : ""}`}
                />
              ))}
            </div>

            {/* Keypad Buttons */}
            <div className="pin-keypad-grid">
              {["1", "2", "3", "4", "5", "6", "7", "8", "9"].map((digit) => (
                <button
                  key={digit}
                  className="pin-key-btn"
                  onClick={() => handleKeyClick(digit)}
                  disabled={isSubmitting}
                >
                  {digit}
                </button>
              ))}
              <button
                className="pin-key-btn"
                style={{ fontSize: "0.9rem", color: "var(--text-muted)" }}
                onClick={handleClear}
                disabled={isSubmitting || pin.length === 0}
                title="Clear"
              >
                Clear
              </button>
              <button
                className="pin-key-btn"
                onClick={() => handleKeyClick("0")}
                disabled={isSubmitting}
              >
                0
              </button>
              <button
                className="pin-key-btn"
                style={{ fontSize: "1rem", color: "var(--accent-warning)" }}
                onClick={() => setPin((prev) => prev.slice(0, -1))}
                disabled={isSubmitting || pin.length === 0}
                title="Backspace"
              >
                ⌫
              </button>
            </div>
          </div>
        </div>

        <div className="modal-footer" style={{ justifyContent: "space-between" }}>
          <span style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>
            Enter 4-digit PIN, or press Escape to cancel
          </span>
          <button className="btn btn-secondary btn-sm" onClick={handleClose}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};
