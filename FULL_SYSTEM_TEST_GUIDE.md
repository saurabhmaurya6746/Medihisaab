# MediHisaab — Complete Hands-On System Test Guide

This guide is for testing every main menu, field, button, workflow, and safety rule in the MediHisaab application.

Use test records first. Do not use real medicines, invoices, customers, or financial data until the complete test passes.

## 1. Test preparation

### 1.1 Start the application

1. Start the daemon with `scripts\start-pharmacy.bat`.
2. Open `http://127.0.0.1:38291`.
3. Confirm the header shows **Daemon Live (WAL)**.
4. Log in with the ADMIN account.

### 1.2 Create a safety backup

1. Open **F9 — Compliance & Reports**.
2. Open **Disaster Recovery & Hot Backups**.
3. Click **Create Hot Backup**.
4. Confirm that a backup record appears with a healthy/valid status.
5. Keep the backup file. Do not delete it during testing.

### 1.3 Use these test records

Use names that are clearly test data:

| Record | Test value |
|---|---|
| Manufacturer | `TEST Manufacturer` |
| Supplier | `TEST Distributor` |
| Medicine | `TEST Paracetamol 500` |
| Medicine code | `TEST-PARA-500` |
| Barcode | `890000000001` |
| Customer | `TEST Customer` |
| Customer phone | `9000000001` |
| Purchase invoice | `TEST-PI-001` |

At every step, record **Pass** or **Fail**. If a failure occurs, take a screenshot and record the exact message.

## 2. Global header and navigation test

Confirm that the following elements are visible and functional:

- Store name
- `OFFLINE STATION` indicator
- `Daemon Live (WAL)` indicator
- Current operator name and role
- **Switch** button
- **Exit** button
- Horizontal menu tabs
- Bottom keyboard shortcut bar
- Station name and clock

Test the shortcuts:

| Shortcut | Expected result |
|---|---|
| `F1` | Opens Counter Sales & Billing |
| `F2` | Opens Medicines & Master Catalog |
| `F3` | Opens Suppliers & Stockists |
| `F4` | Opens Customer Khata |
| `F5` | Opens Customers Master |
| `F6` | Opens Purchases & Inwarding |
| `F7` | Opens Inventory & Expiry |
| `F8` | Opens Stock Audit |
| `F9` | Opens Compliance & Reports for ADMIN |
| `F10` | Shows logout confirmation |
| `F11` | Opens operator PIN switch |

If a shortcut does not work because the browser captures the function key, use the visible menu button and record the issue.

## 3. Medicines & Master Catalog — F2

### 3.1 List and search

1. Open **F2 — Medicines & Master Catalog**.
2. Confirm the medicine table loads.
3. Test the search box with:
   - brand name
   - generic salt
   - medicine code
   - barcode
4. Clear the search.
5. Test refresh.
6. Test pagination if more than one page exists.

Expected result: matching medicines appear and clearing the search restores the list.

### 3.2 Required-field validation

1. Click **+ Add Medicine** or press `Alt+N`.
2. Leave all fields empty.
3. Click **Create Medicine**.

Expected result: required-field errors appear and no record is created.

### 3.3 Create a medicine

Enter:

- Brand / Trade Name: `TEST Paracetamol 500`
- Generic Salt Composition: `Paracetamol 500 mg`
- Dosage Form: `TABLET`
- Strength: `500 mg`
- Pack Size: `10`
- Manufacturer: `TEST Manufacturer`
- Medicine Code: `TEST-PARA-500`
- Barcode: `890000000001`
- HSN Code: `3004`
- GST Tax Slab: `12%`
- Rack / Shelf Location: `TEST-A1`
- Minimum Stock Level: `20`
- Schedule H: off
- Schedule H1: off
- Narcotic: off

Click **Create Medicine**.

Expected result:

- Success message appears.
- The medicine appears in the list.
- The medicine is active.
- The saved values are displayed correctly.

### 3.4 Manufacturer quick-create

1. Open Add Medicine again.
2. Use **+ New** beside Manufacturer.
3. Enter a second test manufacturer.
4. Save it.
5. Confirm it becomes selectable in the medicine form.
6. Close the form without creating a duplicate medicine.

### 3.5 Edit and deactivate

1. Edit `TEST Paracetamol 500`.
2. Change rack location from `TEST-A1` to `TEST-A2`.
3. Save.
4. Search again and confirm the new rack location.
5. Test the deactivate confirmation but do not deactivate the medicine until all sales tests are complete.

Expected result: editing updates the record without creating a duplicate.

Important: adding a medicine does not add stock. Stock is created by posting a purchase invoice.

## 4. Suppliers & Stockists — F3

### 4.1 List and search

1. Open **F3 — Suppliers & Stockists**.
2. Test the search box using supplier name, GSTIN, phone, and license number.
3. Test clear, refresh, and pagination.

### 4.2 Validation

1. Click **+ Add Supplier** or press `Alt+N`.
2. Click **Create Supplier** without entering a name.

Expected result: supplier-name validation appears.

### 4.3 Create a supplier

Enter:

- Supplier / Distributor Firm Name: `TEST Distributor`
- GSTIN: a valid test-format GSTIN
- Credit Terms: `21` days
- Drug License 20B: `TEST-DL-20B`
- Drug License 21B: `TEST-DL-21B`
- Phone: `9000000002`
- Email: `test@example.com`
- Address: `TEST Warehouse`

Click **Create Supplier**.

Expected result: the supplier appears with zero payable balance.

### 4.4 Edit and deactivate

1. Edit the supplier phone or credit days.
2. Save and confirm the value changes.
3. Test the deactivate confirmation.

Do not deactivate the test supplier before completing the purchase tests.

## 5. Customers Master — F5

### 5.1 Create a customer

1. Open **F5 — Customers Master**.
2. Click **+ Add Customer**.
3. Test blank submission and confirm required validation.
4. Enter:

- Name: `TEST Customer`
- Phone: `9000000001`
- Address: `TEST Address`
- Default Doctor: `TEST Doctor`
- Credit Limit: `5000`

5. Save the customer.

Expected result: the customer appears in the list with zero balance.

### 5.2 Search and edit

1. Search by name.
2. Search by phone.
3. Edit the address or credit limit.
4. Save and verify the changed value.

## 6. Purchases & Inwarding — F6

### 6.1 New purchase draft

1. Open **F6 — Purchases & Inwarding**.
2. Click **New Inward Bill** or press `Alt+N`.
3. Select `TEST Distributor`.
4. Enter supplier invoice number `TEST-PI-001`.
5. Enter today's invoice date.
6. Add one line with:

- Medicine: `TEST Paracetamol 500`
- Batch: `TEST-BATCH-001`
- Expiry: a future expiry such as `12/27`
- Paid packs: `10`
- Free packs: `1`
- Pack size: `10`
- Purchase rate/PTR: `40.00`
- MRP: `50.00`
- Trade discount: `5%`
- GST: `12%`

Expected stock after posting: `110` tablets.

### 6.2 Test purchase validation

Test each of these before posting:

- missing supplier
- missing invoice number
- missing invoice date
- missing medicine
- missing batch number
- missing expiry
- invalid/past expiry
- zero or negative quantity
- invalid price

Expected result: the invoice cannot be saved or posted until invalid fields are corrected.

### 6.3 Save draft

1. Click **Save Draft** or press `Ctrl+S`.
2. Return to the invoice list.
3. Reopen the draft.

Expected result: the draft and all entered lines are preserved.

### 6.4 Post purchase

1. Click **Post Bill** or press `Ctrl+P`.
2. Confirm the posting dialog.

Expected result:

- Invoice status becomes `POSTED`.
- Stock is added.
- Supplier payable increases.
- The batch appears in inventory.
- The posted invoice cannot be edited normally.

### 6.5 Duplicate prevention

Try to create another purchase for the same supplier and invoice number `TEST-PI-001`.

Expected result: duplicate invoice submission is rejected.

## 7. Inventory & Expiry — F7

1. Open **F7 — Inventory & Expiry**.
2. Search for `TEST Paracetamol 500`.
3. Confirm the posted batch appears.
4. Confirm current stock is `110` tablets.
5. Confirm the future expiry date and supplier.
6. Test expiry filters:
   - Expired
   - Within 30 days
   - Within 60 days
   - Within 90 days
   - Within 180 days
7. Test search and pagination.
8. Open the supplier return dump.
9. Confirm batches are grouped by supplier.
10. Test print/preview if available.
11. Add a low-stock medicine to Want-Book.
12. Change Want-Book status from `PENDING` to `ORDERED` to `RECEIVED`.

Expected result: posted stock is visible and expiry/low-stock filters work.

## 8. Stock Audit — F8

1. Open **F8 — Stock Audit**.
2. Search for `TEST-BATCH-001`.
3. Confirm system quantity is `110`.
4. Enter physical quantity `108`.
5. Confirm delta is `-2`.
6. Select `BREAKAGE`.
7. Enter a note such as `Two test tablets damaged during audit`.
8. Submit the adjustment.

Expected result:

- Stock becomes `108`.
- An audit record is created.
- An inventory ledger entry is created.
- Operator and timestamp are recorded.

Test that a negative adjustment without notes is rejected.

## 9. Counter Sales & Billing — F1

1. Open **F1 — Counter Sales & Billing**.
2. Confirm the cart is empty.
3. Select `Walk-in Customer`.
4. Search `TEST Paracetamol 500`.
5. Select the FEFO batch.
6. Enter quantity `1` pack.
7. Click **Add** or press `Enter`.

Expected result: one line appears with batch, expiry, quantity, rate, GST, and total.

### 9.1 Billing field tests

Test:

- quantity change
- discount change
- deleting a line
- adding a second line
- clearing the cart
- medicine search by barcode
- medicine search by salt
- batch selection with `F2`
- substitute search with `F3`

### 9.2 Loose tablet test

For a 10-tablet strip with an MRP of ₹50:

1. Enter 4 loose tablets.
2. Add the item.

Expected result:

- Unit rate is calculated from strip MRP divided by pack size.
- Four fundamental units are deducted.
- Tax and total are calculated correctly.

### 9.3 Payment tests

Test separately:

- Cash with exact amount
- Cash with excess amount and change
- UPI
- Card
- Khata
- Split payment

Expected result: payment is accepted, invoice is created, stock is deducted, and receipt preview appears.

### 9.4 Hold and recall

1. Add an item to the cart.
2. Press `Ctrl+H`.
3. Confirm the bill is parked and the cart is cleared.
4. Press `Ctrl+R`.
5. Recall the held bill.

Expected result: the original cart returns without data loss.

### 9.5 Schedule H1 test

Use a separate test medicine marked as Schedule H1.

1. Add it to the bill.
2. Try to pay without patient/doctor information.
3. Confirm checkout is blocked.
4. Enter patient name/address and doctor information.
5. Complete checkout.

Expected result: the sale succeeds and the Schedule H1 record is created.

## 10. Customer Khata — F4

1. Open **F4 — Customer Khata**.
2. Search `TEST Customer`.
3. Confirm balance is shown.
4. Make a Khata sale from billing.
5. Return to Khata.
6. Confirm the balance increased.
7. Click **Deposit** or press `Ctrl+K`.
8. Enter a payment amount.
9. Save the deposit.

Expected result:

- The deposit reduces the balance.
- A ledger entry is created.
- A receipt/reference number is generated.
- Customer aging information updates.

Test exceeding the customer credit limit. Expected result: the sale is blocked.

## 11. Sales Returns

1. Open **Sales Returns**, or press `Ctrl+Shift+R`.
2. Search a completed test invoice.
3. Select one sold item.
4. Enter a valid return quantity.
5. Mark it resellable.
6. Select Cash refund.
7. Confirm the return.

Expected result:

- A credit note is generated.
- Inventory increases for the resellable item.
- The refund is recorded.

Test a second return exceeding the remaining sold quantity.

Expected result: the return is rejected.

Test a damaged/expired return.

Expected result: it is routed to Wastage and is not added back to sellable stock.

## 12. Purchase Returns

1. Open **Purchase Returns**, or press `Ctrl+Shift+P`.
2. Search `TEST-PI-001`.
3. Select the purchased batch.
4. Enter a valid return quantity.
5. Enter reason `Damaged in transit`.
6. Confirm.

Expected result:

- Stock decreases.
- A debit note is generated.
- Supplier payable decreases.
- Inventory ledger is updated.

Test a return larger than the received quantity. Expected result: rejection.

## 13. Wastage Register

1. Open **Wastage**, or press `Ctrl+Shift+W`.
2. Select the test batch.
3. Enter a quantity.
4. Select `BREAKAGE` or `EXPIRED`.
5. Enter notes.
6. Submit.

Expected result:

- Stock decreases.
- Cost impact is calculated.
- Wastage record is created.
- Inventory ledger is updated.

Test submitting a loss without required notes. Expected result: rejection.

## 14. Compliance, Reports, and Backup — F9

ADMIN users only should access this area.

### 14.1 Reports

Test each report:

- Schedule H1 register
- GSTR-1
- GSTR-2
- Sales register
- Purchase register

For each report:

1. Select a date range.
2. Load the report.
3. Confirm test transactions appear.
4. Export CSV.
5. Open the downloaded CSV and verify headers and totals.

### 14.2 Day-book

1. Set the opening float.
2. Complete one cash sale.
3. Complete one Khata deposit.
4. Open the live day-book.
5. Confirm expected cash equals:

```text
Opening Float + Cash Sales + Cash Deposits - Cash Refunds
```

6. Enter the physical drawer count.
7. Confirm the variance.
8. Close the day-book.

Expected result: the day becomes closed and cannot be changed normally.

### 14.3 Backup

1. Open **Disaster Recovery & Hot Backups**.
2. Enter backup notes.
3. Click **Create Hot Backup**.
4. Verify the backup.
5. Download or copy the `.pbk` file to external storage.

Expected result: the backup has a valid hash and healthy SQLite integrity status.

Do not test restore on the live database unless you have a separate verified backup and understand that restore replaces active data.

### 14.4 LAN settings

Only test this after standalone testing is complete.

1. Open LAN configuration.
2. Set LAN server mode.
3. Save settings.
4. Start the LAN server launcher.
5. Connect from another computer using the displayed IP address.
6. Verify login and a test sale from the second terminal.

Return to standalone mode after the test if LAN is not required.

## 15. Final acceptance checklist

Mark the project ready only when all required items pass:

- [ ] Application starts
- [ ] Health indicator is live
- [ ] Medicines can be created, searched, edited, and deactivated
- [ ] Suppliers can be created and searched
- [ ] Customers can be created and searched
- [ ] Purchase drafts save and reopen
- [ ] Posted purchases add stock and payable
- [ ] Duplicate purchases are rejected
- [ ] FEFO batch selection works
- [ ] Expired batches are blocked
- [ ] Cash billing works
- [ ] UPI billing works
- [ ] Card billing works
- [ ] Khata billing works
- [ ] Split payment works
- [ ] Loose tablet billing works
- [ ] Hold and recall works
- [ ] Schedule H1 validation works
- [ ] Inventory filters work
- [ ] Stock audit works
- [ ] Want-Book works
- [ ] Customer deposits work
- [ ] Sales returns work
- [ ] Purchase returns work
- [ ] Wastage works
- [ ] Reports load and export
- [ ] Day-book opening and closing work
- [ ] Backup creation works
- [ ] Backup verification works
- [ ] LAN test works, if required
- [ ] Physical printer tested, if available

## 16. Important safety rules

- Always test with records beginning with `TEST-`.
- Never delete the production database to solve a test problem.
- Take a backup before testing restore.
- Do not store the active SQLite database on OneDrive, Dropbox, or a network share.
- Do not post real purchases until supplier, medicine, expiry, MRP, GST, and quantity have been checked.
- Do not close the day-book until all daily transactions are complete.
- Do not use Stock Audit to correct ordinary sales or purchase mistakes; use returns or proper correction workflows.
