import React, { useState, useEffect, useRef } from "react";
import type { Customer, CustomerDepositReceipt, KhataPaymentMode } from "@pharmacy/api-contracts";
import { formatRupees, rupeesToPaise } from "@pharmacy/api-contracts";
import * as mastersApi from "../../api/masters";
import * as khataApi from "../../api/khata";

interface QuickCustomerDepositModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialCustomer?: Customer | null;
  onSuccess?: (receipt: CustomerDepositReceipt) => void;
}

export const QuickCustomerDepositModal: React.FC<QuickCustomerDepositModalProps> = ({
  isOpen,
  onClose,
  initialCustomer,
  onSuccess,
}) => {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(initialCustomer || null);
  const [balanceInfo, setBalanceInfo] = useState<khataApi.CustomerBalanceInfo | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [depositAmountRupees, setDepositAmountRupees] = useState<string>("");
  const [paymentMode, setPaymentMode] = useState<KhataPaymentMode>("CASH");
  const [notes, setNotes] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<CustomerDepositReceipt | null>(null);

  const searchInputRef = useRef<HTMLInputElement>(null);
  const amountInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setError(null);
      setReceipt(null);
      setDepositAmountRupees("");
      setNotes("");
      setPaymentMode("CASH");

      if (initialCustomer) {
        setSelectedCustomer(initialCustomer);
        setSearchQuery(initialCustomer.name);
        loadCustomerBalance(initialCustomer.id);
        setTimeout(() => amountInputRef.current?.focus(), 100);
      } else {
        setSelectedCustomer(null);
        setBalanceInfo(null);
        setSearchQuery("");
        setTimeout(() => searchInputRef.current?.focus(), 100);
      }
    }
  }, [isOpen, initialCustomer]);

  // Customer search
  useEffect(() => {
    if (!isOpen || selectedCustomer !== null) return;
    if (searchQuery.trim().length >= 2) {
      const timer = setTimeout(() => {
        mastersApi
          .listCustomers({ query: searchQuery.trim(), page_size: 10, is_active: true })
          .then((res) => setCustomers(res.items))
          .catch((err) => console.error("Failed to search customers:", err));
      }, 200);
      return () => clearTimeout(timer);
    } else {
      setCustomers([]);
    }
  }, [searchQuery, isOpen, selectedCustomer]);

  const loadCustomerBalance = async (customerId: number) => {
    try {
      const bal = await khataApi.getCustomerBalance(customerId);
      setBalanceInfo(bal);
    } catch (err: any) {
      console.error("Failed to load customer balance:", err);
    }
  };

  const handleSelectCustomer = (c: Customer) => {
    setSelectedCustomer(c);
    setSearchQuery(c.name);
    setCustomers([]);
    loadCustomerBalance(c.id);
    setTimeout(() => amountInputRef.current?.focus(), 50);
  };

  const handleClearCustomer = () => {
    setSelectedCustomer(null);
    setBalanceInfo(null);
    setSearchQuery("");
    setTimeout(() => searchInputRef.current?.focus(), 50);
  };

  if (!isOpen) return null;

  const depositPaise = rupeesToPaise(depositAmountRupees);
  const currentBalPaise = balanceInfo ? balanceInfo.current_balance_paise : selectedCustomer ? selectedCustomer.current_balance_paise : 0;
  const newBalPaise = currentBalPaise - depositPaise;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCustomer) {
      setError("Please select a customer first.");
      return;
    }
    if (depositPaise <= 0) {
      setError("Deposit amount must be greater than zero.");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      const rec = await khataApi.recordCustomerDeposit(selectedCustomer.id, {
        amount_paise: depositPaise,
        payment_mode: paymentMode,
        notes: notes.trim() || undefined,
      });
      setReceipt(rec);
      if (onSuccess) {
        onSuccess(rec);
      }
    } catch (err: any) {
      setError(err?.message || "Failed to record customer deposit.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-xl max-w-lg w-full shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="bg-slate-800 px-6 py-4 border-b border-slate-700 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <span className="text-xl">💳</span>
            <h2 className="text-lg font-bold text-white">
              {receipt ? "Deposit Receipt Voucher" : "Quick Customer Deposit (Ctrl+K)"}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white transition text-xl font-bold"
          >
            &times;
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[80vh]">
          {error && (
            <div className="mb-4 bg-red-950/80 border border-red-500/50 text-red-200 px-4 py-3 rounded-lg text-sm">
              {error}
            </div>
          )}

          {receipt ? (
            /* Receipt View */
            <div className="space-y-4">
              <div className="p-5 bg-slate-950 rounded-lg border border-slate-800 font-mono text-sm leading-relaxed text-slate-300">
                <div className="text-center font-bold text-white text-base border-b border-dashed border-slate-700 pb-2 mb-3">
                  KHATA DEPOSIT RECEIPT
                  <div className="text-xs text-emerald-400 font-normal">#{receipt.receipt_no}</div>
                </div>

                <div className="flex justify-between py-1">
                  <span>Customer:</span>
                  <span className="font-semibold text-white">{receipt.customer_name}</span>
                </div>
                {receipt.customer_phone && (
                  <div className="flex justify-between py-1">
                    <span>Phone:</span>
                    <span>{receipt.customer_phone}</span>
                  </div>
                )}
                <div className="flex justify-between py-1">
                  <span>Date/Time:</span>
                  <span>{new Date(receipt.created_at).toLocaleString()}</span>
                </div>
                <div className="flex justify-between py-1">
                  <span>Payment Mode:</span>
                  <span className="font-semibold text-emerald-400">{receipt.payment_mode}</span>
                </div>

                <div className="border-t border-dashed border-slate-700 my-3"></div>

                <div className="flex justify-between py-1 text-slate-400">
                  <span>Previous Balance:</span>
                  <span>₹{formatRupees(receipt.previous_balance_paise)}</span>
                </div>
                <div className="flex justify-between py-1 text-emerald-300 font-bold text-base">
                  <span>Amount Deposited:</span>
                  <span>₹{formatRupees(receipt.amount_paise)}</span>
                </div>
                <div className="flex justify-between py-1 font-bold text-white text-base">
                  <span>Remaining Balance:</span>
                  <span className={receipt.new_balance_paise > 0 ? "text-amber-400" : "text-emerald-400"}>
                    ₹{formatRupees(receipt.new_balance_paise)}
                  </span>
                </div>

                {receipt.notes && (
                  <div className="mt-2 text-xs text-slate-400 border-t border-slate-800 pt-2">
                    Ref/Notes: {receipt.notes}
                  </div>
                )}
                {receipt.operator_name && (
                  <div className="mt-1 text-xs text-slate-500">
                    Cashier/Operator: {receipt.operator_name}
                  </div>
                )}
              </div>

              <div className="flex gap-3 justify-end pt-2">
                <button
                  type="button"
                  onClick={handlePrint}
                  className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium text-sm transition"
                >
                  Print Voucher
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg font-medium text-sm transition"
                >
                  Done (Esc)
                </button>
              </div>
            </div>
          ) : (
            /* Deposit Form */
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Customer Selector */}
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1">
                  Customer
                </label>
                {selectedCustomer ? (
                  <div className="p-3 bg-slate-800 border border-slate-700 rounded-lg flex justify-between items-center">
                    <div>
                      <div className="font-semibold text-white">{selectedCustomer.name}</div>
                      <div className="text-xs text-slate-400">{selectedCustomer.phone || "No phone"}</div>
                    </div>
                    <button
                      type="button"
                      onClick={handleClearCustomer}
                      className="text-xs text-slate-400 hover:text-red-400 transition underline"
                    >
                      Change
                    </button>
                  </div>
                ) : (
                  <div className="relative">
                    <input
                      ref={searchInputRef}
                      type="text"
                      className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500 text-sm"
                      placeholder="Type customer name or phone to search..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                    />
                    {customers.length > 0 && (
                      <div className="absolute left-0 right-0 top-full mt-1 bg-slate-800 border border-slate-700 rounded-lg shadow-xl z-20 max-h-48 overflow-y-auto">
                        {customers.map((c) => (
                          <div
                            key={c.id}
                            onClick={() => handleSelectCustomer(c)}
                            className="px-3 py-2 hover:bg-slate-700 cursor-pointer text-sm flex justify-between items-center border-b border-slate-700/50 last:border-0"
                          >
                            <div>
                              <div className="font-medium text-white">{c.name}</div>
                              <div className="text-xs text-slate-400">{c.phone || "No phone"}</div>
                            </div>
                            <div className="text-right">
                              <div className="text-xs text-amber-400 font-mono">
                                ₹{formatRupees(c.current_balance_paise)}
                              </div>
                              <div className="text-[10px] text-slate-500">Balance</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Outstanding Balance Banner */}
              {selectedCustomer && (
                <div className="grid grid-cols-2 gap-3 p-3 bg-slate-950 rounded-lg border border-slate-800 text-sm">
                  <div>
                    <div className="text-xs text-slate-400">Current Outstanding:</div>
                    <div className="text-base font-bold text-amber-400 font-mono">
                      ₹{formatRupees(currentBalPaise)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-400">Credit Limit:</div>
                    <div className="text-base font-bold text-slate-200 font-mono">
                      ₹{formatRupees(balanceInfo?.credit_limit_paise ?? selectedCustomer.credit_limit_paise)}
                    </div>
                  </div>
                </div>
              )}

              {/* Deposit Amount */}
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1">
                  Deposit Amount (₹) *
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-2 text-slate-400 font-bold">₹</span>
                  <input
                    ref={amountInputRef}
                    type="number"
                    step="0.01"
                    min="1"
                    placeholder="0.00"
                    required
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg pl-8 pr-3 py-2 text-white font-mono text-lg font-bold focus:outline-none focus:border-emerald-500"
                    value={depositAmountRupees}
                    onChange={(e) => setDepositAmountRupees(e.target.value)}
                  />
                </div>
              </div>

              {/* Payment Mode */}
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1">
                  Payment Mode *
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {(["CASH", "UPI", "CARD", "BANK_TRANSFER", "CHEQUE"] as KhataPaymentMode[]).map((mode) => (
                    <button
                      key={mode}
                      type="button"
                      onClick={() => setPaymentMode(mode)}
                      className={`px-3 py-2 rounded-lg text-xs font-bold transition border ${
                        paymentMode === mode
                          ? "bg-emerald-600/30 border-emerald-500 text-emerald-300"
                          : "bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700"
                      }`}
                    >
                      {mode}
                    </button>
                  ))}
                </div>
              </div>

              {/* Balance Preview */}
              {selectedCustomer && depositPaise > 0 && (
                <div className="p-3 bg-emerald-950/40 border border-emerald-800/50 rounded-lg flex justify-between items-center text-sm">
                  <span className="text-emerald-300">New Balance after Deposit:</span>
                  <span className="font-mono font-bold text-base text-emerald-400">
                    ₹{formatRupees(newBalPaise)}
                  </span>
                </div>
              )}

              {/* Notes */}
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1">
                  Reference / Notes (optional)
                </label>
                <input
                  type="text"
                  placeholder="e.g. UTR / Cheque # / Cash handed by customer"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500 text-sm"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
              </div>

              {/* Buttons */}
              <div className="flex gap-3 justify-end pt-3">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm transition"
                >
                  Cancel (Esc)
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || !selectedCustomer || depositPaise <= 0}
                  className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold rounded-lg text-sm transition flex items-center gap-2 shadow-lg shadow-emerald-950"
                >
                  {isSubmitting ? "Recording..." : "Record Deposit (Enter)"}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
