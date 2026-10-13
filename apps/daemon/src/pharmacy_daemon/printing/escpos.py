"""ESC/POS 80mm thermal receipt generator for retail pharmacy counter sales.

Produces standard byte streams compatible with Epson, TVS, Citizen, and generic 80mm ESC/POS printers.
"""

from typing import Any, Dict


def generate_escpos_receipt(invoice: Dict[str, Any], store_info: Dict[str, Any] | None = None) -> bytes:
    """Generate 80mm (48-character column) ESC/POS raw bytes for a sale invoice."""
    store = store_info or {}
    store_name = store.get("store_name", "APEX HEALTH PHARMACY")
    store_address = store.get("address", "Main Market, Station Road")
    store_phone = store.get("phone", "+91 98765 43210")
    store_gstin = store.get("gstin", "27AAPFU0938N1ZV")
    store_dl = store.get("dl_number", "DL-20B/21B-89745")

    buf = bytearray()

    # Hardware Init
    buf.extend(b"\x1b@")  # Initialize printer
    buf.extend(b"\x1bt\x00")  # Character code table: PC437 (USA: Standard Europe)

    # 1. Header (Centered, Bold)
    buf.extend(b"\x1ba\x01")  # Center align
    buf.extend(b"\x1bE\x01")  # Bold on
    buf.extend(f"{store_name}\n".encode("ascii", "replace"))
    buf.extend(b"\x1bE\x00")  # Bold off
    buf.extend(f"{store_address}\n".encode("ascii", "replace"))
    buf.extend(f"Ph: {store_phone}\n".encode("ascii", "replace"))
    if store_gstin:
        buf.extend(f"GSTIN: {store_gstin}\n".encode("ascii", "replace"))
    if store_dl:
        buf.extend(f"D.L. No: {store_dl}\n".encode("ascii", "replace"))

    buf.extend(b"\x1ba\x00")  # Left align
    buf.extend(b"------------------------------------------------\n")
    buf.extend(b"\x1bE\x01")
    buf.extend(b"             RETAIL TAX INVOICE                 \n")
    buf.extend(b"\x1bE\x00")
    buf.extend(b"------------------------------------------------\n")

    # 2. Invoice Metadata
    inv_no = invoice.get("invoice_no", "")
    created_at = invoice.get("created_at", "")[:19].replace("T", " ")
    creator = invoice.get("creator_name") or "Operator"
    buf.extend(f"Inv No: {inv_no:<20} Dt: {created_at}\n".encode("ascii", "replace"))
    buf.extend(f"Billed By: {creator}\n".encode("ascii", "replace"))

    cust_name = invoice.get("customer_name")
    cust_phone = invoice.get("customer_phone")
    if cust_name:
        cust_str = f"Patient/Cust: {cust_name}"
        if cust_phone:
            cust_str += f" ({cust_phone})"
        buf.extend(f"{cust_str}\n".encode("ascii", "replace"))

    doc_name = invoice.get("doctor_name")
    if doc_name:
        buf.extend(f"Dr: {doc_name}\n".encode("ascii", "replace"))

    buf.extend(b"------------------------------------------------\n")
    # Table Header (48 cols: Item: 22, Qty: 6, Rate: 10, Total: 10)
    buf.extend(b"Item                  Batch    Qty   Rate  Total\n")
    buf.extend(b"------------------------------------------------\n")

    # 3. Line Items
    items = invoice.get("items", [])
    has_schedule_h1 = False

    for it in items:
        med_name = (it.get("medicine_name") or "Item")[:20]
        batch = (it.get("batch_number") or "")[:8]
        qty = it.get("quantity_units", 0)
        rate_paise = it.get("unit_rate_paise", 0)
        total_paise = it.get("total_amount_paise", 0)
        rate_rs = f"{rate_paise / 100:.2f}"
        tot_rs = f"{total_paise / 100:.2f}"

        # Line 1: Name and batch
        buf.extend(f"{med_name:<21} {batch:<8} {qty:>4} {rate_rs:>6} {tot_rs:>7}\n".encode("ascii", "replace"))

        # Extra line if Schedule H1
        if it.get("is_schedule_h1"):
            has_schedule_h1 = True
            buf.extend(b"  [SCHEDULE H1 WARNING: DISPENSED ON RX]\n")

    buf.extend(b"------------------------------------------------\n")

    # 4. Tax and Totals
    subtotal_rs = f"{invoice.get('subtotal_taxable_paise', 0) / 100:.2f}"
    cgst_rs = f"{invoice.get('total_cgst_paise', 0) / 100:.2f}"
    sgst_rs = f"{invoice.get('total_sgst_paise', 0) / 100:.2f}"
    round_off_rs = f"{invoice.get('round_off_paise', 0) / 100:.2f}"
    grand_rs = f"{invoice.get('grand_total_paise', 0) / 100:.2f}"

    buf.extend(f"Subtotal Taxable:                  Rs. {subtotal_rs:>9}\n".encode("ascii", "replace"))
    buf.extend(f"CGST:                              Rs. {cgst_rs:>9}\n".encode("ascii", "replace"))
    buf.extend(f"SGST:                              Rs. {sgst_rs:>9}\n".encode("ascii", "replace"))
    if invoice.get("round_off_paise", 0) != 0:
        buf.extend(f"Round Off:                         Rs. {round_off_rs:>9}\n".encode("ascii", "replace"))

    buf.extend(b"------------------------------------------------\n")
    buf.extend(b"\x1bE\x01")  # Bold on
    buf.extend(f"GRAND TOTAL:                       Rs. {grand_rs:>9}\n".encode("ascii", "replace"))
    buf.extend(b"\x1bE\x00")  # Bold off
    buf.extend(b"------------------------------------------------\n")

    # 5. Payment details
    pmode = invoice.get("payment_mode", "CASH")
    buf.extend(f"Payment Mode: {pmode}\n".encode("ascii", "replace"))
    if pmode in ("CASH", "SPLIT"):
        tendered_rs = f"{invoice.get('cash_tendered_paise', 0) / 100:.2f}"
        change_rs = f"{invoice.get('change_returned_paise', 0) / 100:.2f}"
        buf.extend(f"Cash Tendered: Rs. {tendered_rs:<10} Change: Rs. {change_rs}\n".encode("ascii", "replace"))

    # Payments breakdown if split
    payments = invoice.get("payments", [])
    if payments and len(payments) > 1:
        buf.extend(b"Split Allocations:\n")
        for p in payments:
            buf.extend(f"  {p.get('payment_mode')}: Rs. {p.get('amount_paise', 0) / 100:.2f}\n".encode("ascii", "replace"))

    buf.extend(b"------------------------------------------------\n")
    # 6. Footer
    buf.extend(b"\x1ba\x01")  # Center
    if has_schedule_h1:
        buf.extend(b"* Contains Schedule H1 Drug(s) *\n")
    buf.extend(b"Thank You! Wish You Speedy Recovery!\n")
    buf.extend(b"Goods once sold will be exchanged per store policy\n")

    # Cash drawer kick pulse: Pin 2 (standard RJ11 pulse 50ms)
    buf.extend(b"\x1bp\x00\x19\xfa")

    # Feed and cut paper
    buf.extend(b"\n\n\n")
    buf.extend(b"\x1dV\x41\x03")  # Partial cut with feed

    return bytes(buf)
