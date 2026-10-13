import React from "react";
import type { SaleInvoice } from "@pharmacy/api-contracts";
import { formatRupees } from "@pharmacy/api-contracts";
import * as salesApi from "../../api/sales";

interface InvoiceReceiptModalProps {
  isOpen: boolean;
  onClose: () => void;
  invoice: SaleInvoice | null;
  onNewBill: () => void;
}

export const InvoiceReceiptModal: React.FC<InvoiceReceiptModalProps> = ({
  isOpen,
  onClose,
  invoice,
  onNewBill,
}) => {
  if (!isOpen || !invoice) return null;

  const handlePrintThermal = async () => {
    try {
      await salesApi.printInvoice(invoice.id, { printer_type: "thermal" });
      alert("Receipt dispatched to ESC/POS thermal printer queue.");
    } catch (err: any) {
      alert(`Print request: ${err.message || "Decoupled print buffer recorded."}`);
    }
  };

  const handlePrintLaser = () => {
    const printWindow = window.open(`/api/v1/sales/invoices/${invoice.id}/html`, "_blank");
    if (printWindow) {
      printWindow.focus();
    }
  };

  return (
    <div className="pos-modal-overlay">
      <div className="pos-modal-card" style={{ maxWidth: 580 }}>
        <div className="pos-modal-header" style={{ backgroundColor: "rgba(16, 185, 129, 0.15)", borderBottom: "1px solid rgba(16, 185, 129, 0.3)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ color: "#10b981", fontSize: "1.4rem" }}>&#10003;</span>
            <h3 style={{ color: "#10b981" }}>Sale Committed — {invoice.invoice_no}</h3>
          </div>
          <button type="button" className="pos-modal-close" onClick={onClose}>
            &times;
          </button>
        </div>

        <div className="pos-modal-body" style={{ maxHeight: 420, overflowY: "auto" }}>
          {/* Summary Box */}
          <div
            style={{
              padding: 14,
              backgroundColor: "var(--bg-secondary, #0f172a)",
              borderRadius: 6,
              border: "1px solid var(--border-color)",
              marginBottom: 14,
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 8,
              fontSize: "0.85rem",
            }}
          >
            <div>
              <div style={{ color: "var(--text-dim)" }}>Invoice Date & Time</div>
              <strong>{invoice.created_at.slice(0, 19).replace("T", " ")}</strong>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ color: "var(--text-dim)" }}>Grand Total</div>
              <strong style={{ fontSize: "1.2rem", color: "#10b981" }}>
                {formatRupees(invoice.grand_total_paise)}
              </strong>
            </div>
            <div>
              <div style={{ color: "var(--text-dim)" }}>Customer</div>
              <span>{invoice.customer_name || "Walk-in Customer"}</span>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ color: "var(--text-dim)" }}>Payment Mode</div>
              <span className="badge badge-success">{invoice.payment_mode}</span>
            </div>
            {invoice.payment_mode === "CASH" && (
              <>
                <div>
                  <div style={{ color: "var(--text-dim)" }}>Cash Tendered</div>
                  <span>{formatRupees(invoice.cash_tendered_paise)}</span>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ color: "var(--text-dim)" }}>Change Returned</div>
                  <strong style={{ color: "#38bdf8" }}>{formatRupees(invoice.change_returned_paise)}</strong>
                </div>
              </>
            )}
          </div>

          {/* Item details */}
          <div style={{ fontSize: "0.82rem", fontWeight: 600, marginBottom: 6 }}>Billed Items ({invoice.items.length}):</div>
          <table className="pos-table" style={{ width: "100%", fontSize: "0.8rem", marginBottom: 14 }}>
            <thead>
              <tr>
                <th>Item</th>
                <th>Batch</th>
                <th style={{ textAlign: "right" }}>Qty</th>
                <th style={{ textAlign: "right" }}>Rate</th>
                <th style={{ textAlign: "right" }}>Total</th>
              </tr>
            </thead>
            <tbody>
              {invoice.items.map((it) => (
                <tr key={it.id}>
                  <td>
                    {it.medicine_name}
                    {it.is_schedule_h1 && <span className="badge badge-danger" style={{ marginLeft: 4, fontSize: "0.6rem" }}>H1</span>}
                  </td>
                  <td style={{ fontFamily: "monospace" }}>{it.batch_number}</td>
                  <td style={{ textAlign: "right" }}>{it.quantity_units}</td>
                  <td style={{ textAlign: "right" }}>{formatRupees(it.unit_rate_paise)}</td>
                  <td style={{ textAlign: "right", fontWeight: 600 }}>{formatRupees(it.total_amount_paise)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="pos-modal-footer" style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
          <div style={{ display: "flex", gap: 8 }}>
            <button type="button" className="btn btn-secondary" onClick={handlePrintThermal}>
              Print Thermal (80mm)
            </button>
            <button type="button" className="btn btn-secondary" onClick={handlePrintLaser}>
              Print Laser (A4)
            </button>
          </div>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              onClose();
              onNewBill();
            }}
          >
            New Bill [F1]
          </button>
        </div>
      </div>
    </div>
  );
};
