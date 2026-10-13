import React, { useEffect, useRef, useState } from "react";
import type { Customer, PaymentAllocationInput, SalePaymentMode } from "@pharmacy/api-contracts";
import { formatRupees } from "@pharmacy/api-contracts";
import { useSettings } from "../../context/SettingsContext";

interface PaymentModalProps {
  isOpen: boolean;
  onClose: () => void;
  grandTotalPaise: number;
  selectedCustomer: Customer | null;
  customers: Customer[];
  onSelectCustomer: (customer: Customer | null) => void;
  onConfirmCheckout: (paymentDetails: {
    payment_mode: SalePaymentMode;
    payments?: PaymentAllocationInput[];
    cash_tendered_paise: number;
  }) => void;
  isSubmitting: boolean;
}

export const PaymentModal: React.FC<PaymentModalProps> = ({
  isOpen,
  onClose,
  grandTotalPaise,
  selectedCustomer,
  customers,
  onSelectCustomer,
  onConfirmCheckout,
  isSubmitting,
}) => {
  const { isPreferenceEnabled } = useSettings();
  const allowCreditSales = isPreferenceEnabled("allowCreditSales");

  const [paymentMode, setPaymentMode] = useState<SalePaymentMode>("CASH");
  const [cashTenderedRupees, setCashTenderedRupees] = useState<string>("");

  // Split tender inputs (in Rupees)
  const [splitCashRupees, setSplitCashRupees] = useState<string>("");
  const [splitUpiRupees, setSplitUpiRupees] = useState<string>("");
  const [splitCardRupees, setSplitCardRupees] = useState<string>("");
  const [splitKhataRupees, setSplitKhataRupees] = useState<string>("");
  const [upiRef, setUpiRef] = useState<string>("");
  const [cardRef, setCardRef] = useState<string>("");

  const [validationError, setValidationError] = useState<string | null>(null);

  // If credit sales are disabled and khata was somehow selected, fallback to cash
  useEffect(() => {
    if (!allowCreditSales && paymentMode === "KHATA") {
      setPaymentMode("CASH");
    }
  }, [allowCreditSales, paymentMode]);

  const cashInputRef = useRef<HTMLInputElement>(null);

  // Initialize tender state whenever modal opens
  useEffect(() => {
    if (isOpen) {
      setPaymentMode("CASH");
      const totalRs = (grandTotalPaise / 100).toFixed(2);
      setCashTenderedRupees(totalRs);
      setSplitCashRupees("");
      setSplitUpiRupees("");
      setSplitCardRupees("");
      setSplitKhataRupees("");
      setUpiRef("");
      setCardRef("");
      setValidationError(null);
      setTimeout(() => {
        cashInputRef.current?.focus();
        cashInputRef.current?.select();
      }, 50);
    }
  }, [isOpen, grandTotalPaise]);

  // Window hotkeys inside modal (Esc to close, Enter to submit)
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  const tenderedPaise = Math.round((parseFloat(cashTenderedRupees) || 0) * 100);
  const changeReturnedPaise = Math.max(0, tenderedPaise - grandTotalPaise);

  // Split allocations calculation
  const splitCashPaise = Math.round((parseFloat(splitCashRupees) || 0) * 100);
  const splitUpiPaise = Math.round((parseFloat(splitUpiRupees) || 0) * 100);
  const splitCardPaise = Math.round((parseFloat(splitCardRupees) || 0) * 100);
  const splitKhataPaise = Math.round((parseFloat(splitKhataRupees) || 0) * 100);

  const totalSplitAllocatedPaise = splitCashPaise + splitUpiPaise + splitCardPaise + splitKhataPaise;
  const splitRemainingPaise = grandTotalPaise - totalSplitAllocatedPaise;

  const handleQuickCash = (amountRupees: number) => {
    setCashTenderedRupees(amountRupees.toString());
    cashInputRef.current?.focus();
  };

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setValidationError(null);

    if (paymentMode === "CASH") {
      if (tenderedPaise < grandTotalPaise) {
        setValidationError(
          `Cash tendered (${formatRupees(tenderedPaise)}) is less than total bill (${formatRupees(grandTotalPaise)}).`
        );
        return;
      }
      onConfirmCheckout({
        payment_mode: "CASH",
        cash_tendered_paise: tenderedPaise,
      });
    } else if (paymentMode === "UPI") {
      onConfirmCheckout({
        payment_mode: "UPI",
        cash_tendered_paise: grandTotalPaise,
        payments: [{ payment_mode: "UPI", amount_paise: grandTotalPaise, reference_note: upiRef || "UPI" }],
      });
    } else if (paymentMode === "CARD") {
      onConfirmCheckout({
        payment_mode: "CARD",
        cash_tendered_paise: grandTotalPaise,
        payments: [{ payment_mode: "CARD", amount_paise: grandTotalPaise, reference_note: cardRef || "Card" }],
      });
    } else if (paymentMode === "KHATA") {
      if (!selectedCustomer) {
        setValidationError("A registered customer account is mandatory for Khata (credit) billing.");
        return;
      }
      const newBal = selectedCustomer.current_balance_paise + grandTotalPaise;
      if (newBal > selectedCustomer.credit_limit_paise) {
        setValidationError(
          `Customer credit limit exceeded! Available credit: ${formatRupees(
            Math.max(0, selectedCustomer.credit_limit_paise - selectedCustomer.current_balance_paise)
          )}.`
        );
        return;
      }
      onConfirmCheckout({
        payment_mode: "KHATA",
        cash_tendered_paise: 0,
        payments: [{ payment_mode: "KHATA", amount_paise: grandTotalPaise, reference_note: "Khata Ledger" }],
      });
    } else if (paymentMode === "SPLIT") {
      if (totalSplitAllocatedPaise !== grandTotalPaise) {
        setValidationError(
          `Total allocated (${formatRupees(totalSplitAllocatedPaise)}) must exactly equal grand total (${formatRupees(
            grandTotalPaise
          )}). Difference: ${formatRupees(Math.abs(splitRemainingPaise))}.`
        );
        return;
      }
      if (splitCashPaise > 0 && tenderedPaise < splitCashPaise) {
        setValidationError(
          `Cash tendered (${formatRupees(tenderedPaise)}) is less than cash split allocation (${formatRupees(
            splitCashPaise
          )}).`
        );
        return;
      }
      if (splitKhataPaise > 0) {
        if (!selectedCustomer) {
          setValidationError("Customer profile is required when Khata split allocation is used.");
          return;
        }
        const newBal = selectedCustomer.current_balance_paise + splitKhataPaise;
        if (newBal > selectedCustomer.credit_limit_paise) {
          setValidationError(`Khata allocation exceeds customer credit limit.`);
          return;
        }
      }

      const allocations: PaymentAllocationInput[] = [];
      if (splitCashPaise > 0) allocations.push({ payment_mode: "CASH", amount_paise: splitCashPaise });
      if (splitUpiPaise > 0)
        allocations.push({ payment_mode: "UPI", amount_paise: splitUpiPaise, reference_note: upiRef || "UPI" });
      if (splitCardPaise > 0)
        allocations.push({ payment_mode: "CARD", amount_paise: splitCardPaise, reference_note: cardRef || "Card" });
      if (splitKhataPaise > 0) allocations.push({ payment_mode: "KHATA", amount_paise: splitKhataPaise });

      onConfirmCheckout({
        payment_mode: "SPLIT",
        cash_tendered_paise: splitCashPaise > 0 ? tenderedPaise : 0,
        payments: allocations,
      });
    }
  };

  if (!isOpen) return null;

  return (
    <div className="pos-modal-overlay">
      <div className="pos-modal-card" style={{ maxWidth: 640 }}>
        <div className="pos-modal-header">
          <h3>Payment & Checkout</h3>
          <button type="button" className="pos-modal-close" onClick={onClose} title="Close [Esc]">
            &times;
          </button>
        </div>

        {/* Big Grand Total Display */}
        <div
          style={{
            padding: "16px 20px",
            backgroundColor: "var(--bg-secondary, #0f172a)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            borderBottom: "1px solid var(--border-color)",
          }}
        >
          <div>
            <div style={{ fontSize: "0.8rem", color: "var(--text-dim)" }}>
              Total Payable Amount
            </div>
            <div style={{ fontSize: "2.1rem", fontWeight: 800, color: "#10b981", lineHeight: 1.1 }}>
              {formatRupees(grandTotalPaise)}
            </div>
          </div>

          {/* Payment Mode Selector Pills */}
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", justifyContent: "flex-end" }}>
            {(["CASH", "UPI", "CARD", "KHATA", "SPLIT"] as SalePaymentMode[])
              .filter((mode) => allowCreditSales || mode !== "KHATA")
              .map((mode) => (
                <button
                  key={mode}
                  type="button"
                  className={`btn btn-sm ${paymentMode === mode ? "btn-primary" : "btn-secondary"}`}
                  style={{ fontWeight: paymentMode === mode ? 700 : 400 }}
                  onClick={() => {
                    setPaymentMode(mode);
                    setValidationError(null);
                  }}
                >
                  {mode}
                </button>
              ))}
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="pos-modal-body" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {validationError && (
              <div className="pos-alert pos-alert-error" style={{ margin: 0, padding: "8px 12px", fontSize: "0.85rem" }}>
                {validationError}
              </div>
            )}

            {/* CASH MODE */}
            {paymentMode === "CASH" && (
              <div>
                <label className="pos-label" htmlFor="cash-tendered-input">
                  Cash Tendered (₹)
                </label>
                <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                  <input
                    id="cash-tendered-input"
                    ref={cashInputRef}
                    type="number"
                    step="0.01"
                    className="pos-input"
                    style={{ fontSize: "1.4rem", fontWeight: 700, textAlign: "right" }}
                    value={cashTenderedRupees}
                    onChange={(e) => setCashTenderedRupees(e.target.value)}
                    required
                  />
                  <div
                    style={{
                      padding: "8px 16px",
                      borderRadius: 6,
                      backgroundColor: "rgba(16, 185, 129, 0.1)",
                      border: "1px solid rgba(16, 185, 129, 0.3)",
                      textAlign: "right",
                      minWidth: 150,
                    }}
                  >
                    <div style={{ fontSize: "0.72rem", color: "var(--text-dim)" }}>Change to return</div>
                    <div style={{ fontSize: "1.3rem", fontWeight: 800, color: "#10b981" }}>
                      {formatRupees(changeReturnedPaise)}
                    </div>
                  </div>
                </div>

                {/* Quick Cash Presets */}
                <div style={{ display: "flex", gap: 6, marginTop: 10, flexWrap: "wrap" }}>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => handleQuickCash(grandTotalPaise / 100)}
                  >
                    Exact ({formatRupees(grandTotalPaise)})
                  </button>
                  {[50, 100, 200, 500, 1000, 2000].map((amt) => (
                    <button
                      key={amt}
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleQuickCash(amt)}
                    >
                      ₹{amt}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* UPI MODE */}
            {paymentMode === "UPI" && (
              <div>
                <label className="pos-label" htmlFor="upi-ref-input">
                  UPI Reference / Transaction ID (Optional)
                </label>
                <input
                  id="upi-ref-input"
                  type="text"
                  className="pos-input"
                  placeholder="e.g. UPI/123456789012"
                  value={upiRef}
                  onChange={(e) => setUpiRef(e.target.value)}
                />
                <div style={{ marginTop: 8, fontSize: "0.82rem", color: "var(--text-dim)" }}>
                  QR code or UPI Collect received for <strong>{formatRupees(grandTotalPaise)}</strong>.
                </div>
              </div>
            )}

            {/* CARD MODE */}
            {paymentMode === "CARD" && (
              <div>
                <label className="pos-label" htmlFor="card-ref-input">
                  Card Last 4 Digits / POS Auth Code (Optional)
                </label>
                <input
                  id="card-ref-input"
                  type="text"
                  className="pos-input"
                  placeholder="e.g. Auth-9821 or 4321"
                  value={cardRef}
                  onChange={(e) => setCardRef(e.target.value)}
                />
                <div style={{ marginTop: 8, fontSize: "0.82rem", color: "var(--text-dim)" }}>
                  POS terminal swipe/dip approved for <strong>{formatRupees(grandTotalPaise)}</strong>.
                </div>
              </div>
            )}

            {/* KHATA MODE */}
            {paymentMode === "KHATA" && (
              <div>
                <label className="pos-label" htmlFor="khata-customer-select">
                  Select Khata Account Customer <span style={{ color: "#ef4444" }}>*</span>
                </label>
                <select
                  id="khata-customer-select"
                  className="pos-input"
                  value={selectedCustomer?.id || ""}
                  onChange={(e) => {
                    const c = customers.find((cust) => cust.id === Number(e.target.value)) || null;
                    onSelectCustomer(c);
                  }}
                  required
                >
                  <option value="">-- Choose registered customer --</option>
                  {customers
                    .filter((c) => c.is_active)
                    .map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name} ({c.phone || "No phone"}) — Balance: {formatRupees(c.current_balance_paise)} / Limit:{" "}
                        {formatRupees(c.credit_limit_paise)}
                      </option>
                    ))}
                </select>

                {selectedCustomer && (
                  <div
                    style={{
                      marginTop: 12,
                      padding: 12,
                      borderRadius: 6,
                      backgroundColor: "var(--bg-secondary, #1e293b)",
                      border: "1px solid var(--border-color)",
                      display: "grid",
                      gridTemplateColumns: "1fr 1fr 1fr",
                      gap: 8,
                      fontSize: "0.85rem",
                    }}
                  >
                    <div>
                      <div style={{ color: "var(--text-dim)" }}>Credit Limit</div>
                      <strong>{formatRupees(selectedCustomer.credit_limit_paise)}</strong>
                    </div>
                    <div>
                      <div style={{ color: "var(--text-dim)" }}>Current Debt</div>
                      <strong style={{ color: "#f59e0b" }}>{formatRupees(selectedCustomer.current_balance_paise)}</strong>
                    </div>
                    <div>
                      <div style={{ color: "var(--text-dim)" }}>Remaining Credit</div>
                      <strong
                        style={{
                          color:
                            selectedCustomer.credit_limit_paise - selectedCustomer.current_balance_paise >= grandTotalPaise
                              ? "#10b981"
                              : "#ef4444",
                        }}
                      >
                        {formatRupees(
                          Math.max(0, selectedCustomer.credit_limit_paise - selectedCustomer.current_balance_paise)
                        )}
                      </strong>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* SPLIT TENDER MODE */}
            {paymentMode === "SPLIT" && (
              <div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                  <div>
                    <label className="pos-label" htmlFor="split-cash-input">Cash Portion (₹)</label>
                    <input
                      id="split-cash-input"
                      type="number"
                      step="0.01"
                      className="pos-input"
                      placeholder="0.00"
                      value={splitCashRupees}
                      onChange={(e) => setSplitCashRupees(e.target.value)}
                    />
                  </div>

                  <div>
                    <label className="pos-label" htmlFor="split-upi-input">UPI Portion (₹)</label>
                    <input
                      id="split-upi-input"
                      type="number"
                      step="0.01"
                      className="pos-input"
                      placeholder="0.00"
                      value={splitUpiRupees}
                      onChange={(e) => setSplitUpiRupees(e.target.value)}
                    />
                  </div>

                  <div>
                    <label className="pos-label" htmlFor="split-card-input">Card Portion (₹)</label>
                    <input
                      id="split-card-input"
                      type="number"
                      step="0.01"
                      className="pos-input"
                      placeholder="0.00"
                      value={splitCardRupees}
                      onChange={(e) => setSplitCardRupees(e.target.value)}
                    />
                  </div>

                  {allowCreditSales && (
                    <div>
                      <label className="pos-label" htmlFor="split-khata-input">Khata / Credit Portion (₹)</label>
                      <input
                        id="split-khata-input"
                        type="number"
                        step="0.01"
                        className="pos-input"
                        placeholder="0.00"
                        value={splitKhataRupees}
                        onChange={(e) => setSplitKhataRupees(e.target.value)}
                      />
                    </div>
                  )}
                </div>

                {splitCashPaise > 0 && (
                  <div style={{ marginTop: 10 }}>
                    <label className="pos-label" htmlFor="split-cash-tendered">
                      Physical Cash Tendered for Cash Portion (₹)
                    </label>
                    <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                      <input
                        id="split-cash-tendered"
                        type="number"
                        step="0.01"
                        className="pos-input"
                        value={cashTenderedRupees}
                        onChange={(e) => setCashTenderedRupees(e.target.value)}
                      />
                      <div style={{ minWidth: 140, fontSize: "0.85rem" }}>
                        Change:{" "}
                        <strong style={{ color: "#10b981" }}>
                          {formatRupees(Math.max(0, tenderedPaise - splitCashPaise))}
                        </strong>
                      </div>
                    </div>
                  </div>
                )}

                {/* Remaining unallocated counter */}
                <div
                  style={{
                    marginTop: 12,
                    padding: "8px 12px",
                    borderRadius: 6,
                    backgroundColor: splitRemainingPaise === 0 ? "rgba(16, 185, 129, 0.15)" : "rgba(239, 68, 68, 0.15)",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    fontSize: "0.85rem",
                  }}
                >
                  <span>
                    Allocated: <strong>{formatRupees(totalSplitAllocatedPaise)}</strong> /{" "}
                    {formatRupees(grandTotalPaise)}
                  </span>
                  <span
                    style={{
                      fontWeight: 700,
                      color: splitRemainingPaise === 0 ? "#10b981" : "#ef4444",
                    }}
                  >
                    {splitRemainingPaise === 0
                      ? "Fully Allocated ✓"
                      : `Remaining: ${formatRupees(splitRemainingPaise)}`}
                  </span>
                </div>
              </div>
            )}
          </div>

          <div className="pos-modal-footer" style={{ display: "flex", justifyContent: "space-between" }}>
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={isSubmitting}>
              Cancel [Esc]
            </button>
            <button
              type="submit"
              className="btn btn-success"
              style={{ fontSize: "1rem", padding: "8px 24px" }}
              disabled={isSubmitting || (paymentMode === "SPLIT" && splitRemainingPaise !== 0)}
            >
              {isSubmitting ? "Processing Sale..." : "Complete Sale & Print [Enter]"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
