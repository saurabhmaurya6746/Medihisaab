# MediHisaab — Daily Operator & Keyboard Shortcut Guide

## 1. Global Keyboard Navigation Map

MediHisaab is designed for 100% keyboard-driven counter operations modeled after MARG ERP:

| Hotkey | Action / View | Role Allowed | Purpose |
| :--- | :--- | :--- | :--- |
| **F2** | **Counter POS Billing** | All | Main sales checkout, item search, blister cutting, payment |
| **F3** | **Purchase Inwarding Grid** | Pharmacist, Admin | Tabular inwarding of distributor invoices, trade discounts, schemes |
| **F4** | **Customer Khata & Returns** | All | Khata ledgers, customer credit balances, sales/purchase returns, wastage |
| **F5** | **Inventory & Expiry Control** | Pharmacist, Admin | Near-expiry batches, FEFO stock list, supplier dump lists |
| **F6** | **Want-Book & Stock Audits** | Pharmacist, Admin | Low-stock items, supplier reorder requests, physical audit corrections |
| **F9** | **Compliance & System Admin** | Admin | Schedule H1, GSTR-1/2, Day-Book reconciliation, hot backups, LAN config |
| **Ctrl+P** | **Quick PIN Switch** | All | Instant operator shift change without password re-entry |
| **Ctrl+H** | **Hold / Recall Bill** | All | Park current customer bill to attend urgent customer, then recall |
| **Ctrl+K** | **Quick Khata Deposit** | All | Rapid cash deposit popup for customer credit balance clearance |
| **Ctrl+W** | **Quick Want-Book Capture** | All | Add out-of-stock requested medicine to want-book during active billing |
| **Enter** | **Advance Field / Accept** | All | Moves focus across tabular input cells |
| **Escape** | **Cancel / Close Modal** | All | Closes open dialog or clears active search query |

---

## 2. Daily Shift Workflow

### Morning Routine: Setting Opening Float
1. Operator arrives at the billing counter and launches MediHisaab.
2. If changing shift, press **Ctrl+P** to switch to your operator PIN.
3. The administrator or lead cashier opens **Day-Book & Cash Drawer (F9)**.
4. In the **Opening Float** field, enter the initial physical cash in the drawer (e.g., `₹500.00` in change coins/notes).
5. Click **Set Opening Float**.
6. The system sets today's initial drawer baseline. All sales and deposits accumulate on top of this float.

---

### Mid-Day Routine: High-Volume Billing
1. Counter operators bill walk-in and regular customers using **F2**.
2. If an out-of-stock drug is requested by a patient:
   - Press **Ctrl+W** to instantly open the Quick Want-Book modal.
   - Enter requested quantity and doctor notes.
   - Press Enter to queue the drug for the evening purchase order.
3. If a regular customer arrives to pay an outstanding Khata credit balance:
   - Press **Ctrl+K**.
   - Search customer by phone number.
   - Enter cash amount received.
   - Press Enter to credit their account and print an instant thermal receipt.
4. If a customer needs to fetch more cash or a prescription:
   - Press **Ctrl+H** to Hold the bill.
   - Serve the next waiting patient.
   - Press **Ctrl+H** again to Recall the held bill.

---

### Evening Routine: Day-Book Balancing & Drawer Sealing
1. At the end of the business day, open **Day-Book (F9)**.
2. The screen displays the live reconciliation formula:
   $$\text{Expected Drawer Cash} = \text{Opening Float} + \text{Cash Sales} + \text{Khata Deposits} - \text{Cash Refunds}$$
3. Count the physical cash in the cash drawer (currency notes and coins).
4. Enter the physical amount in **Physical Drawer Count**.
5. The system immediately calculates the variance:
   - `₹0.00`: Drawer Balanced.
   - Negative: Shortage.
   - Positive: Excess.
6. Enter closing notes (e.g. *"Verified by Shift Manager Sharma"*).
7. Click **Confirm & Close Day-Book**.
8. The day's financial books are permanently sealed. The date becomes immutable, preventing accidental or retroactive tampering.
