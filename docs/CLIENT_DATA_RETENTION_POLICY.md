# MediHisaab — Client Data Retention & Privacy Policy

This document establishes the binding architectural policy regarding client data retention, offline persistence, and regulatory compliance for all deployments of MediHisaab.

---

## 1. Statement of Principle: Client Data Sovereignty

All operational records created within MediHisaab belong exclusively to the client pharmacy.
The software vendor, distributors, and cloud hosting infrastructure **neither own, store, transmit, nor have access to** client pharmacy operational records.

---

## 2. Local Database Retention Rules

### 2.1 Database Location
All pharmacy operations are stored in a standalone SQLite database at:
```
%LOCALAPPDATA%\PharmacyApp\data\pharmacy.db
```
Automated daily snapshots and manual backups are stored at:
```
%LOCALAPPDATA%\PharmacyApp\backups\
```

### 2.2 Preservation Across Updates & Upgrades
* The Windows Inno Setup installer explicitly preserves existing files in `%LOCALAPPDATA%\PharmacyApp\`.
* Application updates, patches, and re-installations **never** replace, overwrite, or delete `pharmacy.db`.
* Upgrades apply database migrations automatically in-place without data loss.

### 2.3 Uninstallation Safeguard
* Running the Windows Uninstaller removes application binaries, shortcuts, and registry keys.
* **The user database and backups are deliberately left intact** in `%LOCALAPPDATA%\PharmacyApp\` to prevent accidental data catastrophe.

---

## 3. Subscription Expiration & Business Continuity

Under no circumstances does MediHisaab erase, lock, or encrypt client operational records when a subscription lapses:

1. **Zero Data Purging:** Medicine records, batch numbers, purchase ledgers, sale invoices, and customer Khata ledgers remain 100% intact.
2. **Regulatory & Tax Access:** In the event of a subscription expiration, pharmacy owners retain read-only access to historical transaction ledgers, GST tax reports, and batch audit histories to comply with state drug control inspections and tax filings.
3. **No Remote Kill-Switch:** The software contains no remote command execution or remote database deletion capability. The software owner cannot remotely wipe or access a client's database.

---

## 4. Vendor Healthcare Privacy & Confidentiality Stance

* **Zero Telemetry on Patients:** No patient names, doctor prescriptions, phone numbers, or diagnostic details are ever collected by the software vendor.
* **Zero Commercial Surveillance:** The vendor does not collect retail pricing, profit margins, supplier discounts, or sales volumes.
* **Central Licensing Database Scope:** The central licensing database contains **only** client account contact details, subscription status, and issued Ed25519 license tokens.
