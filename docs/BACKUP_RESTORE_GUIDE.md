# MediHisaab — Disaster Recovery, Hot Backups & Restore Guide

## 1. Overview & Hot Backup Architecture

MediHisaab employs an enterprise-grade disaster recovery architecture specifically tailored for retail pharmacy operations:

- **Zero Counter Interruption:** Backups use SQLite's native online snapshot mechanisms (`VACUUM INTO` / `sqlite3.backup`). Active counter billing, sales checkouts, and customer lookups continue simultaneously without locking the database.
- **Self-Contained Packages (`.pbk`):** Backups are packaged into compressed, tamper-evident archives containing:
  - A clean transactional snapshot of `pharmacy.db`
  - A SHA-256 cryptographic manifest verifying data integrity
  - System metadata (schema version, invoice counts, medicine counts, total revenue, Khata balances, and creation timestamp)
- **Automatic Integrity Verification:** Prior to archiving, the daemon validates the snapshot against SQLite `PRAGMA integrity_check`.

---

## 2. Default Backup Locations

Backups are saved locally in the user's application data folder:
```
%LOCALAPPDATA%\PharmacyApp\backups\
```

A sample backup filename follows this standardized naming format:
```
pharmacy_backup_20261008_163000_v008.pbk
```

> [!TIP]
> Administrators can configure a custom backup directory (e.g. an external USB flash drive or secondary internal hard drive) in **Settings / Store Profile (F9)**.

---

## 3. Creating a Hot Backup

### Method A: Admin Web Interface (F9)
1. Log in with an **ADMIN** user profile.
2. Open **Disaster Recovery & Hot Backups (F9)**.
3. In the **Backup Notes** field, enter a description (e.g., *"Pre-fiscal audit snapshot"*).
4. Click **Create Hot Backup**.
5. The system captures the database state, compresses it, verifies its SHA-256 hash, and logs the manifest in seconds.
6. Click the **Download** button to download a copy of the `.pbk` archive to an external USB drive.

---

### Method B: Automated Nightly / Shift Closing
When closing the cash drawer at the end of the day via the Day-Book module, the system automatically registers the session and can trigger automated hot backups.

---

## 4. Verifying Backup Archives

To verify that an existing backup archive has not suffered file corruption or bit rot:
1. Navigate to **Disaster Recovery & Hot Backups (F9)**.
2. In the Backups list, find the target backup record.
3. Click **Verify Integrity**.
4. The system computes a fresh SHA-256 checksum over the file, compares it against the recorded manifest, unpacks the inner database into temporary storage, and executes `PRAGMA integrity_check`.
5. Displays a green badge `[VERIFIED: HEALTHY]` or alerts the administrator if corruption is detected.

---

## 5. Clean-Machine Disaster Recovery & Safe Restore

In the event of hardware failure, disk crash, or migration to a new computer:

### Step 1: Install MediHisaab on the New Machine
Install the application using `MediHisaab-Setup-1.0.0.exe` and complete the initial setup.

### Step 2: Stage & Inspect the Backup Archive
1. Open **Disaster Recovery (F9)**.
2. Click **Upload Backup File to Restore** and select your `.pbk` archive.
3. The system unpacks the archive into an isolated staging sandbox and presents the **Inspect & Confirm Restore Modal**:
   - Backup creation timestamp
   - Schema version compatibility
   - Recorded invoice count and total revenue
   - Khata customer balance sum
   - SQLite integrity status

### Step 3: Mandatory Pre-Restore Safety Snapshot
Before overwriting the active database, MediHisaab automatically takes a **PRE_RESTORE_SAFETY** snapshot of the current state. If a restore was executed by mistake, the previous state can be restored immediately.

### Step 4: Atomic Database Replacement
1. Click **Yes, Restore Database**.
2. The daemon replaces the active database atomically and checkpoints SQLite WAL logs (`PRAGMA wal_checkpoint(TRUNCATE)`).
3. The interface refreshes immediately, presenting the fully restored store data.
