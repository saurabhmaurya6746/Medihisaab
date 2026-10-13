# MediHisaab — Billing, Blister Cutting, Returns & Wastage Guide

## 1. Counter POS Billing (F2)

### Searching & Selecting Medicines
1. Type brand name (e.g. `Crocin`, `Augmentin`), generic salt (e.g. `Paracetamol`), or scan the barcode.
2. The search results show:
   - Pack size (e.g., `10 tablets/strip`)
   - Rack location (e.g., `Rack A-2`)
   - FEFO recommended batch (Earliest Expiry First Out)
   - Available total stock
3. Press **Enter** to select the medicine and auto-populate the FEFO batch.

---

### Loose Tablet Blister Cutting
Pharmacies frequently cut blister foil strips to sell loose tablets:
- If a pack size is 10 tablets and MRP is `₹50.00` per strip:
- When the operator enters quantity `4` loose tablets:
  $$\text{Unit MRP} = \frac{₹50.00}{10} = ₹5.00 \text{ per tablet}$$
  $$\text{Line Total} = 4 \times ₹5.00 = ₹20.00$$
- Stock is deducted precisely by 4 fundamental units (tablets), maintaining 100% accurate remaining tablet count in the batch.

---

### Schedule H1 Drug Dispensing Compliance
When a Schedule H1 medicine is added to the bill:
1. The line item displays the red `[H1]` regulatory badge.
2. The checkout dialog requires:
   - Patient Full Name & Address
   - Prescribing Doctor Name
3. This information is immutably logged to the statutory **Schedule H1 Register** under Drugs & Cosmetics Rule 65(3)(h).

---

### Split-Tender Payment
MediHisaab supports split-tender checkout:
- Customer can pay partly in Cash (e.g. `₹200.00`) and the remainder via UPI QR (e.g. `₹350.00`).
- The bill records individual payment mode breakdowns and calculates change returned accurately.

---

## 2. Customer Khata Credit Sales & Deposits

### Credit Billing
- To bill on credit, search and select an existing registered customer.
- If the sale exceeds the customer's configured credit limit, the POS warns the operator and blocks the sale unless overridden by an authorized user.
- Credit sales increase the customer's outstanding balance atomically.

### Customer Cash Deposits (Ctrl+K)
- Regular customers can settle their credit ledger anytime.
- Press **Ctrl+K** from anywhere in the POS.
- Enter amount paid in cash or UPI.
- The balance is deducted immediately, an immutable ledger entry is written, and a payment receipt is printed.

---

## 3. Customer Sales Returns

### Return Process
1. Navigate to **Customer Returns (F4)**.
2. Enter the original sale invoice number (e.g. `INV-202610-0001`).
3. Select the item(s) being returned.
4. **Quantity Bounds Protection:** The system strictly prevents returning more units than were originally sold, minus any previously returned units.
5. Select the return condition:
   - **Resellable & Valid Expiry:** Units are automatically restocked into the original batch, increasing available inventory.
   - **Expired or Damaged:** Units are **NOT** restocked; the system automatically routes them to the **Wastage Register**.
6. Select refund mode: `CASH`, `UPI`, `CARD`, `KHATA` (credits customer balance), or `STORE_CREDIT`.
7. An atomic credit note is issued with an audit timestamp.

---

## 4. Supplier Purchase Returns & Debit Notes

1. Navigate to **Purchase Returns (F4)**.
2. Select distributor and original purchase invoice.
3. Enter returned quantity and reason (e.g. `Near-Expiry Return Dump` or `Damaged In Transit`).
4. Deducts batch inventory immediately.
5. Issues a Supplier Debit Note that atomically reduces the distributor's current payable balance.

---

## 5. Wastage Register

Used for accounting and write-off of unsellable drugs (breakages, damaged cold-chain stock, expired scraps):
1. In **Wastage Register (F4)**, click **Record Wastage**.
2. Select batch, quantity, and reason (`EXPIRED`, `BREAKAGE`, `DAMAGED`, `SCRAP`).
3. Enter explanatory operator notes.
4. Batch stock is decremented and an immutable audit record is logged with cost impact calculation.
