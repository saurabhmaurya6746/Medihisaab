"""Printable A4/A5 laser invoice template generator with GST Rule 46 compliance."""

import html
from typing import Any, Dict


def generate_laser_invoice_html(invoice: Dict[str, Any], store_info: Dict[str, Any] | None = None, page_size: str = "A4") -> str:
    """Generate high-contrast, professional A4/A5 tax invoice HTML for laser printing or PDF export."""
    store = store_info or {}
    store_name = html.escape(store.get("store_name", "APEX HEALTH PHARMACY"))
    store_address = html.escape(store.get("address", "Main Market, Station Road"))
    store_phone = html.escape(store.get("phone", "+91 98765 43210"))
    store_gstin = html.escape(store.get("gstin", "27AAPFU0938N1ZV"))
    store_dl = html.escape(store.get("dl_number", "DL-20B/21B-89745"))

    inv_no = html.escape(invoice.get("invoice_no", ""))
    created_at = html.escape(invoice.get("created_at", "")[:19].replace("T", " "))
    creator = html.escape(invoice.get("creator_name") or "Operator")
    cust_name = html.escape(invoice.get("customer_name") or "Walk-in Customer")
    cust_phone = html.escape(invoice.get("customer_phone") or "—")
    cust_addr = html.escape(invoice.get("customer_address") or "—")
    doc_name = html.escape(invoice.get("doctor_name") or "Self / None")
    pmode = html.escape(invoice.get("payment_mode", "CASH"))

    items = invoice.get("items", [])

    lines_html = []
    gst_slabs: Dict[float, Dict[str, int]] = {}

    for idx, it in enumerate(items, 1):
        mname = html.escape(it.get("medicine_name") or "Medicine")
        batch = html.escape(it.get("batch_number") or "—")
        exp = html.escape(it.get("expiry_date") or "—")
        qty = it.get("quantity_units", 0)
        pack_size = it.get("pack_size", 1)
        mrp_rs = f"{it.get('unit_mrp_paise', 0) / 100:.2f}"
        rate_rs = f"{it.get('unit_rate_paise', 0) / 100:.2f}"
        disc_pct = it.get("discount_percent", 0.0)
        taxable_rs = f"{it.get('taxable_amount_paise', 0) / 100:.2f}"
        gst_r = it.get("gst_rate", 0.0)
        cgst_rs = f"{it.get('cgst_amount_paise', 0) / 100:.2f}"
        sgst_rs = f"{it.get('sgst_amount_paise', 0) / 100:.2f}"
        tot_rs = f"{it.get('total_amount_paise', 0) / 100:.2f}"
        h1_badge = "<span style='color:#dc2626; font-weight:bold;'>[H1]</span> " if it.get("is_schedule_h1") else ""

        # Slabs summary accumulation
        slab = gst_slabs.setdefault(gst_r, {"taxable": 0, "cgst": 0, "sgst": 0, "total": 0})
        slab["taxable"] += it.get("taxable_amount_paise", 0)
        slab["cgst"] += it.get("cgst_amount_paise", 0)
        slab["sgst"] += it.get("sgst_amount_paise", 0)
        slab["total"] += it.get("total_amount_paise", 0)

        lines_html.append(f"""
        <tr>
            <td style="text-align:center;">{idx}</td>
            <td>{h1_badge}{mname}</td>
            <td style="font-family:monospace;">{batch}</td>
            <td style="text-align:center;">{exp}</td>
            <td style="text-align:right;">{qty}</td>
            <td style="text-align:right;">{mrp_rs}</td>
            <td style="text-align:right;">{rate_rs}</td>
            <td style="text-align:right;">{disc_pct:.1f}%</td>
            <td style="text-align:right;">{taxable_rs}</td>
            <td style="text-align:center;">{gst_r:.1f}%</td>
            <td style="text-align:right;">{cgst_rs}</td>
            <td style="text-align:right;">{sgst_rs}</td>
            <td style="text-align:right; font-weight:bold;">{tot_rs}</td>
        </tr>
        """)

    gst_table_html = []
    for rate, s in sorted(gst_slabs.items()):
        gst_table_html.append(f"""
        <tr>
            <td style="text-align:center;">{rate:.1f}%</td>
            <td style="text-align:right;">Rs. {s['taxable']/100:.2f}</td>
            <td style="text-align:right;">Rs. {s['cgst']/100:.2f}</td>
            <td style="text-align:right;">Rs. {s['sgst']/100:.2f}</td>
            <td style="text-align:right;">Rs. {(s['cgst'] + s['sgst'])/100:.2f}</td>
        </tr>
        """)

    subtotal_rs = f"{invoice.get('subtotal_taxable_paise', 0) / 100:.2f}"
    cgst_rs = f"{invoice.get('total_cgst_paise', 0) / 100:.2f}"
    sgst_rs = f"{invoice.get('total_sgst_paise', 0) / 100:.2f}"
    round_off_rs = f"{invoice.get('round_off_paise', 0) / 100:.2f}"
    grand_rs = f"{invoice.get('grand_total_paise', 0) / 100:.2f}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Tax Invoice - {inv_no}</title>
<style>
    @page {{
        size: {page_size};
        margin: 10mm;
    }}
    body {{
        font-family: Arial, sans-serif;
        font-size: 11px;
        color: #111827;
        margin: 0;
        padding: 10px;
    }}
    .invoice-card {{
        border: 1px solid #1f2937;
        padding: 12px;
    }}
    .header-table {{
        width: 100%;
        border-bottom: 2px solid #111827;
        margin-bottom: 8px;
        padding-bottom: 6px;
    }}
    .store-name {{
        font-size: 18px;
        font-weight: bold;
        letter-spacing: 0.5px;
    }}
    .meta-table {{
        width: 100%;
        margin-bottom: 10px;
        font-size: 11px;
    }}
    .meta-table td {{
        padding: 2px 4px;
        vertical-align: top;
    }}
    .items-table {{
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 10px;
    }}
    .items-table th, .items-table td {{
        border: 1px solid #d1d5db;
        padding: 4px 6px;
        font-size: 10px;
    }}
    .items-table th {{
        background: #f3f4f6;
        text-align: left;
        font-weight: 600;
    }}
    .summary-grid {{
        display: flex;
        justify-content: space-between;
        margin-top: 8px;
    }}
    .gst-table {{
        border-collapse: collapse;
        font-size: 10px;
    }}
    .gst-table th, .gst-table td {{
        border: 1px solid #d1d5db;
        padding: 3px 6px;
    }}
    .gst-table th {{
        background: #f9fafb;
    }}
    .totals-box {{
        width: 260px;
        font-size: 11px;
        margin-left: auto;
    }}
    .totals-box table {{
        width: 100%;
    }}
    .totals-box td {{
        padding: 2px 4px;
    }}
    .grand-total {{
        font-size: 14px;
        font-weight: bold;
        border-top: 1px solid #111827;
        border-bottom: 1px solid #111827;
    }}
    .footer-note {{
        margin-top: 15px;
        font-size: 9px;
        color: #4b5563;
        border-top: 1px solid #e5e7eb;
        padding-top: 4px;
        display: flex;
        justify-content: space-between;
    }}
</style>
</head>
<body>
<div class="invoice-card">
    <table class="header-table">
        <tr>
            <td style="width:65%;">
                <div class="store-name">{store_name}</div>
                <div>{store_address} | Phone: {store_phone}</div>
                <div><strong>GSTIN:</strong> {store_gstin} | <strong>D.L. No:</strong> {store_dl}</div>
            </td>
            <td style="text-align:right; width:35%;">
                <div style="font-size:14px; font-weight:bold; color:#1e40af;">TAX INVOICE</div>
                <div>(Under CGST Rule 46)</div>
                <div style="font-size:12px; margin-top:4px;"><strong>Invoice No:</strong> {inv_no}</div>
                <div><strong>Date:</strong> {created_at}</div>
            </td>
        </tr>
    </table>

    <table class="meta-table">
        <tr>
            <td style="width:50%;">
                <strong>Billed To:</strong> {cust_name}<br>
                <strong>Phone:</strong> {cust_phone} | <strong>Address:</strong> {cust_addr}
            </td>
            <td style="width:50%; text-align:right;">
                <strong>Doctor:</strong> {doc_name}<br>
                <strong>Payment Mode:</strong> {pmode} | <strong>Cashier:</strong> {creator}
            </td>
        </tr>
    </table>

    <table class="items-table">
        <thead>
            <tr>
                <th style="width:25px; text-align:center;">#</th>
                <th>Medicine / Item Description</th>
                <th>Batch</th>
                <th style="text-align:center;">Exp</th>
                <th style="text-align:right;">Qty</th>
                <th style="text-align:right;">MRP</th>
                <th style="text-align:right;">Rate</th>
                <th style="text-align:right;">Disc%</th>
                <th style="text-align:right;">Taxable</th>
                <th style="text-align:center;">GST</th>
                <th style="text-align:right;">CGST</th>
                <th style="text-align:right;">SGST</th>
                <th style="text-align:right;">Amount</th>
            </tr>
        </thead>
        <tbody>
            {"".join(lines_html)}
        </tbody>
    </table>

    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
        <div>
            <div style="font-weight:bold; margin-bottom:4px; font-size:10px;">GST Slab Summary:</div>
            <table class="gst-table">
                <thead>
                    <tr>
                        <th>Rate</th>
                        <th>Taxable Amt</th>
                        <th>CGST</th>
                        <th>SGST</th>
                        <th>Total Tax</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(gst_table_html)}
                </tbody>
            </table>
        </div>

        <div class="totals-box">
            <table>
                <tr>
                    <td>Subtotal (Taxable):</td>
                    <td style="text-align:right;">Rs. {subtotal_rs}</td>
                </tr>
                <tr>
                    <td>Total CGST:</td>
                    <td style="text-align:right;">Rs. {cgst_rs}</td>
                </tr>
                <tr>
                    <td>Total SGST:</td>
                    <td style="text-align:right;">Rs. {sgst_rs}</td>
                </tr>
                <tr>
                    <td>Round Off:</td>
                    <td style="text-align:right;">Rs. {round_off_rs}</td>
                </tr>
                <tr class="grand-total">
                    <td>GRAND TOTAL:</td>
                    <td style="text-align:right;">Rs. {grand_rs}</td>
                </tr>
            </table>
        </div>
    </div>

    <div class="footer-note">
        <div>
            * Schedule H1 medicines dispensed strictly under supervision of Registered Pharmacist.<br>
            * Computer generated invoice. No signature required.
        </div>
        <div style="text-align:right; width:200px; margin-top:15px; border-top:1px dashed #4b5563; padding-top:2px;">
            Authorized Signatory / Pharmacist
        </div>
    </div>
</div>
</body>
</html>
"""
