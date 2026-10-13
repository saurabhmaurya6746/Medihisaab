# MediHisaab — Vendor Licensing Portal User Guide

This guide describes the operations and workflows available to the software owner and authorized vendor personnel in the **Central Vendor Licensing Portal**.

---

## 1. Overview & Architecture

The Central Vendor Licensing Portal is a dedicated management console used exclusively by the software owner to manage client pharmacy accounts, commercial subscription plans, payment receipts, Ed25519 digital license issuance, and system audits.

### Key Separation of Concerns
* **Vendor Database:** Central PostgreSQL database managed on Render (or SQLite in local development). Contains **only** client registration records, plans, subscriptions, and issued license metadata.
* **Public Portal:** Strictly static site providing installer downloads and public documentation. Zero client records or private keys are hosted here.
* **Client MediHisaab:** Runs 100% offline at each pharmacy. The client's operational data (inventory, billing, customer Khata) resides **only** on the pharmacy's local workstation in SQLite.

---

## 2. Access & Authentication

### 2.1 Portal URLs
* **Production URL:** `https://licensing-api.apexhealth.com/vendor` (or Render web service URL)
* **Local Development:** `http://localhost:8000/` or `http://localhost:8000/vendor`

### 2.2 Default Administrator Credentials
* **Email:** `owner@apexhealth.local`
* **Default Password:** `OwnerSecurePass2026!`
* **Role:** `OWNER`

> [!CAUTION]
> Immediately change the default password after deploying to production.

### 2.3 Role-Based Access Control (RBAC)
| Role | Capabilities |
| :--- | :--- |
| **OWNER** | Full system control: user management, plans, licensing, clients, manual payments, audit logs. |
| **ADMIN** | Client registration, subscription activation, license generation, revocation, payments, audit access. |
| **SUPPORT** | View clients, subscriptions, issue trials, view licenses. Cannot alter commercial plans or access audit logs. |
| **READ_ONLY** | Read-only inspection of client directory and subscriptions. |

---

## 3. Operations & Workflows

### 3.1 Dashboard
The dashboard surfaces live key performance indicators (KPIs):
* **Total Clients:** Count of registered retail and wholesale pharmacies.
* **Active Subscriptions:** Pharmacies currently under valid commercial coverage.
* **Trial Clients:** Pharmacies currently under the 15-day evaluation period.
* **Expiring Soon (14d):** Subscriptions reaching renewal within 14 days.
* **Expired / Grace:** Accounts currently past due or under the grace period.
* **Recent Licenses:** Quick table of the latest cryptographically signed licenses with direct download actions.

### 3.2 Client Registration
1. Navigate to the **Clients** tab.
2. Click **+ Register Client**.
3. Fill in required business details:
   * **Business / Pharmacy Name** (e.g. *Metro Life Chemist*)
   * **Owner / Proprietor Name** (e.g. *Ramesh K. Sharma*)
   * **Phone Number** (e.g. *+91 98765 43210*)
   * **Email Address** (e.g. *contact@metrolife.example*)
   * **Shop Address, City, State, PIN**
   * *(Optional)* GSTIN, Retail Drug License Number, Wholesale Drug License Number.
4. Click **Save Client**. The system automatically generates a sequential client code (e.g. `CL-1001`).

### 3.3 Starting an Evaluation Trial
1. From the **Clients** list or the client profile, click **Trial**.
2. Confirm the 15-day evaluation window (or override with custom duration).
3. The system creates a trial subscription with a 7-day grace period.

### 3.4 Creating a Paid Subscription & Recording Payments
1. Navigate to **Subscriptions** or open a client record.
2. Select the plan:
   * *Monthly Standard Commercial (Up to 2 Workstations)*
   * *Single Counter Standard (1 Workstation)*
   * *Multi-Counter LAN Commercial (Up to 5 Workstations)*
   * *Enterprise Pharmacy Suite (Up to 20 Workstations)*
3. Record the payment reference:
   * **Payment Method:** UPI QR, Bank NEFT/RTGS, Cheque, or Cash.
   * **Reference / UTR:** e.g. `UPI/ICICI/981249012`
   * **Amount:** Confirmed price in paise (e.g. ₹6,000.00 = `600000`).
4. Click **Confirm Payment**. The subscription status transitions immediately to `ACTIVE`.

### 3.5 Issuing an Ed25519 Cryptographic License
1. Open the **Licenses** tab or click **License** next to an active client.
2. Enter the parameters:
   * **Client ID:** Target pharmacy.
   * **Terminal Counter Limit:** Maximum concurrent LAN billing counters allowed (1 to 50).
   * **Activation Date:** Defaults to today.
   * **Expiry Date:** Defaults to subscription end date (+ grace period).
   * **Edition:** `COMMERCIAL` or `TRIAL`.
3. Click **Generate & Sign License**.
4. The service signs the canonical license payload using the server's private Ed25519 key.
5. Click **Download .json** to retrieve the secure token file (e.g. `LIC-CL1001-20261009-A4F1.json`).
6. Deliver this JSON file to the pharmacy client via secure email or messaging.

### 3.6 Revoking a License
If a client terminates their contract or requests a license cancellation:
1. Navigate to **Licenses**.
2. Locate the license and click **Revoke**.
3. Confirm the revocation. The license is flagged as revoked with an immutable audit entry.

### 3.7 Auditing & Compliance
Authorized `OWNER` and `ADMIN` users can inspect `/api/v1/audit` for tamper-evident activity records. All actions (logins, client creation, payment receipts, license issuance, revocations) are logged with user ID, IP address, and sanitized metadata (passwords and private keys are never recorded).
