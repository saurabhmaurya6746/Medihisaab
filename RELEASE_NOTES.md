# MediHisaab — Release Notes (v1.0.0)

**Release Date:** October 2026  
**Platform:** Windows 10 / Windows 11 (64-bit)  
**Architecture:** Offline-First Retail Pharmacy Management System & POS (MARG ERP Alternative)

---

## 1. Release Highlights

MediHisaab v1.0.0 delivers a high-speed, keyboard-driven, offline-first pharmacy retail management system designed to replace legacy systems like MARG ERP. The software combines the speed and pharmaceutical business logic of classic ERPs with a modern React web interface, strict SQLite WAL transaction integrity, and pure integer paise financial accounting.

---

## 2. Milestone Deliverables Summary

### Milestone 1: Core Foundation & Master Catalogs
- Multi-user authentication with Role-Based Access Control (`ADMIN`, `PHARMACIST`, `CASHIER`).
- Quick 4-digit operator PIN switching for counter shift changes.
- Fast full-text search (SQLite FTS5) across medicine catalog (brand name, generic salt, dosage form, rack location, barcode).
- 15-character GSTIN format validation and Drug License number tracking.

### Milestone 2: Purchase Inwarding Grid (MARG Logic)
- High-speed keyboard tabular purchase inwarding grid (**F3**).
- Trade discount (TD%) and free schemes ($10+1$, $100+15$, half scheme, full scheme).
- Exact landed cost per fundamental unit calculation without floating-point error.
- Non-inventory charge support (freight, cold-chain handling).
- Atomic batch creation and distributor accounts payable ledger tracking.

### Milestone 3: Counter Billing POS & Blister Cutting
- Sub-second counter billing interface (**F2**).
- Automated First-Expiry-First-Out (FEFO) batch allocation.
- Loose tablet blister cutting: sell partial strips with exact unit-MRP pricing.
- Bill hold and recall (**Ctrl+H**) for multi-customer queues.
- Split-tender checkout (Cash + UPI + Card + Khata Credit).
- Decoupled 80mm ESC/POS thermal receipt printing and A4/A5 laser tax invoices.

### Milestone 4: Inventory Control, Expiry & Want-Book
- Near-expiry dashboard with thresholds: Expired, 30 days, 60 days, 90 days, 180 days (**F5**).
- Distributor near-expiry return dump generator.
- Strict expired drug billing lockout: expired batches can never be added to sales bills.
- Physical stock audit reconciliation with delta tracking and non-negative stock enforcement (**F6**).
- Low-stock detection and quick want-book capture (**Ctrl+W**).

### Milestone 5: Customer Khata, Returns & Wastage
- Append-only customer credit ledger (Khata) with aging buckets (0–30, 31–60, 60+ days) (**F4**).
- Quick Khata cash deposit shortcut (**Ctrl+K**).
- Customer sales returns linked to original invoices with maximum returnable bounds checking.
- Resellable restocking vs. non-resellable automatic diversion to the Wastage Register.
- Supplier purchase returns with automatic distributor debit note generation.

### Milestone 6: Statutory Reports, Disaster Recovery & LAN Activation
- Rule 65(3)(h) Schedule H1 drug dispensing register with CSV export (**F9**).
- GSTR-1 outward tax pack: Table 4A (B2B), Table 7 (B2C), Table 12 (HSN), and Table 13 (document sequences).
- GSTR-2 inward purchase register grouped by distributor GSTIN.
- End-of-day Day-Book cash drawer balancing with live expected cash math and closed-day immutability.
- Automated hot SQLite backups (`VACUUM INTO`) packaged into compressed `.pbk` archives with SHA-256 manifests.
- 1-Click clean-machine disaster recovery with mandatory pre-restore safety snapshot.
- Multi-counter LAN activation (`0.0.0.0:38291`) supporting secondary counter terminals inside web browsers.

---

## 3. Production Hardening & Packaging Deliverables

- **Single-Port Architecture:** In production, the FastAPI daemon directly mounts and serves the pre-built web frontend assets at `/`. A single process on port `38291` powers both the backend REST API and the frontend UI.
- **Inno Setup Installer:** Provided in `installer/pharmacy-pos-installer.iss`. Configured with data preservation logic that protects `%LOCALAPPDATA%\PharmacyApp\data\pharmacy.db` across upgrades and uninstalls.
- **Hardware Diagnostic Suite:** Added `scripts/test-hardware.bat` and `POST /api/v1/system/hardware/test-printer` supporting USB ESC/POS, TCP Network (port 9100), RJ11 drawer pulse, laser invoice, and offline simulation logging.
- **Launchers:** Added `scripts/start-pharmacy.bat` (1-click app launcher), `scripts/start-lan-server.bat` (LAN server launcher), and `scripts/package-release.bat` (release packager).

---

## 4. Hardware & Physical Environment Disclosures

Before deploying to live retail pharmacy store counters, the following on-site checks must be conducted:

1. **Physical ESC/POS Thermal Printer:** Software ESC/POS byte rendering and spooler decoupling have been verified. On-site verification on physical USB hardware is required to test paper cutter alignment and paper feed distance.
2. **Cash Drawer Solenoid Voltage:** Verify whether the cash drawer uses a 12V or 24V solenoid (Epson TM-T82 uses 24V Pin 2).
3. **Windows Firewall on Multi-PC LAN:** When activating LAN mode, execute the Windows Defender Firewall allow command on the server machine to allow inward TCP traffic on port `38291`.
4. **Barcode Scanner Carriage Return:** Ensure USB barcode scanners have their factory default Enter (`[CR]`) suffix enabled.

---

## 5. Automated Verification Results

- **Backend Pytest Suite:** 96/96 tests passed (100% green)
- **TypeScript Contract Typing:** Exit Code 0 (clean)
- **Node Contract Unit Tests:** 6/6 tests passed (paise arithmetic verified)
- **Web Production Build:** Built cleanly with Vite (Exit Code 0)
