# MediHisaab — Central Licensing System & Supabase Architecture Guide

This guide details the architecture, workflows, operational procedures, security guarantees, and backup practices for the central software licensing and subscription system powered by **Supabase PostgreSQL**.

---

## 1. Architectural Overview & Strict Data Segregation

The MediHisaab ecosystem is divided into three completely decoupled components to protect client privacy, ensure 100% offline autonomy for pharmacies, and maintain centralized licensing control for the software publisher:

```mermaid
flowchart TD
    subgraph Publisher["Software Publisher (Apex Health)"]
        VendorUI["Vendor Licensing Portal (Web SPA)"]
        LicensingAPI["Central Licensing API (Render / FastAPI)"]
        SupabaseDB[("Supabase PostgreSQL\n(Clients, Plans, Licenses, Payments)")]
        PrivKey["Publisher Ed25519 Private Key\n(Env Secret: LICENSE_PRIVATE_KEY_PEM)"]
        
        VendorUI <-->|HTTPS Bearer JWT| LicensingAPI
        LicensingAPI <-->|SQLAlchemy / SSL| SupabaseDB
        LicensingAPI -->|Digitally Signs| PrivKey
    end

    subgraph Public["Public Download Portal (Render Static Site)"]
        Downloads["Software Installer (.msi / .exe)\nDocumentation & Release Notes"]
    end

    subgraph ClientStore["Client Pharmacy (100% Offline Autonomy)"]
        ClientPOS["MediHisaab Desktop Application"]
        LocalSQLite[("Local SQLite Database\n(%LOCALAPPDATA%\\PharmacyApp\\data\\pharmacy.db)")]
        PubKey["Embedded Ed25519 Public Key\n(ba7a4f28067b0d4d...)"]
        LicFile["Imported License Token\n(license.json)"]

        ClientPOS <--> LocalSQLite
        ClientPOS --> PubKey
        ClientPOS --> LicFile
    end

    LicensingAPI -.->|Vendor sends license.json via Email/WhatsApp| LicFile
    Downloads -.->|Client downloads once| ClientPOS
```

### Absolute Zero Operational Telemetry Guarantee

| Feature | Central Supabase PostgreSQL | Local Pharmacy SQLite (`pharmacy.db`) |
| :--- | :---: | :---: |
| **Client Business & Contact Details** |  Yes (Name, Owner, Phone, Address, GSTIN) |  Yes (Store Header Config) |
| **Subscription Plans & Expirations** |  Yes (Status, Start Date, Expiry Date, Grace) |  No (Evaluated from `license.json`) |
| **Manual Payment Receipts & UTRs** |  Yes (Vendor manual confirmations) |  No |
| **Issued License Records & Signatures** |  Yes (Audit copy of issued licenses) |  Yes (Only the local store's license) |
| **Vendor Staff Accounts & Roles** |  Yes (Owner, Admin, Support, Read-Only) |  No |
| **Medicine Catalog & Batch Stock** | ** NEVER (Strictly Prohibited)** |  Yes (Fully local) |
| **Sales Invoices & Daily Receipts** | ** NEVER (Strictly Prohibited)** |  Yes (Fully local) |
| **Purchase Invoices & Distributor Costs** | ** NEVER (Strictly Prohibited)** |  Yes (Fully local) |
| **Customer Khata Ledgers & Balances** | ** NEVER (Strictly Prohibited)** |  Yes (Fully local) |
| **Patient Details & Doctor Prescriptions** | ** NEVER (Strictly Prohibited)** |  Yes (Fully local) |

> [!IMPORTANT]
> **Data Privacy Guarantee:** Supabase PostgreSQL never receives, stores, or queries pharmacy business transactions, prescription data, medicine inventory, or cash drawer amounts. Client operational data resides exclusively on the client's workstation in SQLite.

---

## 2. Vendor Licensing Portal Workflows

The Vendor Licensing Portal provides 11 dedicated management screens accessible by vendor operators according to their RBAC role (`OWNER`, `ADMIN`, `SUPPORT`, `READ_ONLY`).

### Workflow A: New Client Registration & 15-Day Trial Issuance

1. **Register Client:**
   - In Vendor Portal, navigate to **Clients** tab and click **+ Register Client**.
   - Input business name (e.g. `Apollo Care Pharmacy`), owner name, contact phone, email, and address.
   - The system automatically allocates a unique identifier (e.g. `CL-1001`).
2. **Start Evaluation Trial:**
   - Click **Start Trial** next to the client record.
   - The trial duration defaults to **15 days** (as configured in vendor settings).
   - *Optional Override:* To give an extended evaluation (e.g., 30 or 45 days), type the custom duration into the **Trial Duration (Days)** field.
   - Click **Activate Trial**. A new trial subscription (`status: TRIALING`) is created.
3. **Issue Signed Trial License:**
   - Click **Issue License**.
   - Select edition: `TRIAL (Evaluation)`.
   - Workstation counter limit: e.g. `3 Counter(s)`.
   - Click **Generate & Sign License**. The Licensing API signs the canonical representation using the Ed25519 private key.
4. **Deliver License to Client:**
   - In the **Licenses** tab, click **Download .json** next to the newly created license.
   - Deliver the resulting `LIC-CL1001-XXXX.json` file to the pharmacy owner via email, WhatsApp, or USB.

---

### Workflow B: Manual Payment Confirmation & Paid Conversion

1. **Client Remits Payment:**
   - Pharmacy client transfers annual subscription fee via UPI QR code, NEFT/RTGS bank transfer, or cheque directly to the vendor's bank account.
2. **Vendor Records Payment:**
   - In Vendor Portal, navigate to **Trials** or **Subscriptions**.
   - Click **Convert to Paid** on the client's trial record.
   - Select the target commercial plan (e.g. `Annual Commercial Single Counter` or `Multi-Counter`).
   - Enter the payment reference / UTR number (e.g. `UPI/981248901234` or `NEFT/AXIS/10928374`).
   - Select payment method (`UPI`, `NEFT_RTGS`, `CHEQUE`, `CASH`).
   - Enter amount in paise (e.g. `1500000` for ₹15,000.00).
   - Click **Confirm & Convert**.
3. **Automated Conversion:**
   - A verified payment receipt (`status: CONFIRMED`) is saved in the `payments` table.
   - The client's subscription updates from `TRIALING` to `ACTIVE`, extending the expiry date by 365 days.
4. **Issue Commercial License:**
   - Click **Issue License** -> Edition: `COMMERCIAL`.
   - Deliver the new signed commercial license JSON file to the client.

---

### Workflow C: Annual Subscription Renewal

1. Client remits renewal payment prior to expiry.
2. In Vendor Portal **Subscriptions** tab, locate client's subscription and click **Renew**.
3. Enter renewal UTR reference and amount.
4. The system:
   - Records the confirmed payment receipt.
   - Extends `current_period_end` by 365 days from either current expiry or today.
   - Extends `grace_period_end` accordingly.
5. Vendor downloads and sends the renewed commercial license file.
6. Client imports renewed file without software reinstallation; all local data remains completely intact.

---

### Workflow D: Dynamic Configuration of Default Trial & Grace Periods

1. In Vendor Portal, navigate to **11. Settings**.
2. Update **Default Trial Duration (Days)**:
   - Change from `15` to any preferred integer (e.g. `21` or `30`).
3. Update **Default Grace Period (Days)**:
   - Configure grace period window (e.g. `7` or `14` days).
4. Click **Save System Settings**.
5. All future trials automatically inherit the updated duration unless overridden per-client.

---

## 3. Client POS License Import & Offline Enforcement

### Importing License in Offline MediHisaab

1. Log into MediHisaab as an **ADMIN** user.
2. In the top navigation bar, click the **Settings (Gear Icon)**.
3. Select the **License** tab.
4. Under **Import Client License File (.json)**, click **Choose File** and select the `.json` file provided by the vendor.
5. The POS daemon immediately:
   - Verifies the Ed25519 digital signature against the embedded public key `ba7a4f28067b0d4d4e7d90128c48f9316ba5c3069a0cb88fcc5a24b081b3632b`.
   - Rejects tampered files (wrong signature, altered terminal count, modified store name).
   - Persists the validated license to `%LOCALAPPDATA%\PharmacyApp\data\license.json`.
   - Renders live license status:
     - **Status Badge:** `EVALUATION TRIAL` (blue) or `ACTIVE` (green).
     - **Days Remaining:** Displays exact days remaining (e.g. `15 Days Left`).
     - **Counter Terminals:** Verified terminal limit.
     - **Expiry Date:** Exact expiration date.

### Expiration & Grace Period Behavior

- **During Active Period:** Full operational capabilities (sales, purchases, inventory, Khata, printing, LAN mode).
- **Expiration Approaching (<= 7 days):** Yellow alert banner indicates remaining days and prompts the owner to contact vendor support for renewal.
- **Grace Period (e.g. 7 days post-expiry):**
  - Status transitions to `GRACE PERIOD` (amber badge).
  - Amber warning banner: *"License expired on YYYY-MM-DD. In grace period (X days left). Please contact support to renew."*
  - Operations continue uninterrupted during grace period.
- **Post-Grace Period Expiration:**
  - Status transitions to `EXPIRED`.
  - Commercial billing functions are restricted.
  - **Local Data Is Never Deleted:** All historical sales, medicine catalogs, customer ledgers, and backup exports remain 100% accessible for read-only viewing and disaster-recovery export.
  - Database is **never locked or destroyed**.

---

## 4. Cryptographic Key Management & Security

### Key Roles

- **Ed25519 Private Key (`license_private_key.pem`):**
  - Held strictly by the software publisher on the secure Licensing API server.
  - Injected as environment variable `LICENSE_PRIVATE_KEY_PEM` on Render Web Service.
  - **Never** stored in Supabase database tables.
  - **Never** bundled in public installer builds or static websites.
- **Ed25519 Public Key (`ba7a4f28067b0d4d4e7d90128c48f9316ba5c3069a0cb88fcc5a24b081b3632b`):**
  - Embedded statically in the offline POS client binary.
  - Used by `evaluate_license()` to verify digital signatures offline.

---

## 5. Supabase Database Maintenance & Disaster Recovery

### Preventing Project Inactivity Pauses on Supabase Free Tier

Supabase Free Tier projects pause after 7 consecutive days without database requests.
To ensure the central licensing database remains permanently active:
1. **API Traffic:** The licensing API performs automated connection pooling and health checks against Supabase.
2. **Scheduled Keep-Alive (Cron Job):**
   A lightweight periodic ping can be scheduled via GitHub Actions, Render Cron Job, or an external uptime monitor (e.g. UptimeRobot or Cron-job.org) targeting `https://<licensing-api-domain>/health` every 48 hours.

### Manual Backup via `pg_dump`

To generate an encrypted snapshot of the central licensing database:

```bash
# Export full binary PostgreSQL dump
pg_dump "postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres" \
  -F c \
  -b \
  -v \
  -f "supabase_licensing_$(date +%Y%m%d).dump"
```

### Manual Backup via Supabase Web Console

1. Navigate to your Supabase Project Dashboard: `https://supabase.com/dashboard/project/<PROJECT_REF>`.
2. Go to **Settings** -> **Database**.
3. Under **Database Backups**, trigger a manual backup download or export SQL tables via the **Table Editor** (`Export to CSV` or `SQL Editor -> Download`).

### Disaster Recovery / Database Restoration

To restore the licensing database to a fresh Supabase project:

```bash
# Restore schema and records using pg_restore
pg_restore -h db.[NEW-PROJECT-REF].supabase.co \
  -U postgres \
  -d postgres \
  -v "supabase_licensing_YYYYMMDD.dump"
```

Or execute `services/licensing-api/migrations/001_supabase_schema.sql` directly inside the Supabase SQL Editor.
