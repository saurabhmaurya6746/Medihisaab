# MediHisaab — First-Run Setup & Initialization Guide

## 1. Overview

When MediHisaab is launched for the first time on a new computer or with a blank database, the system automatically detects that no active license or administrative user exists and presents a streamlined **Two-Step First-Run Wizard**:

1. **Step 1: License & Account Onboarding:** Activate your free trial automatically, sign in to an existing pharmacy client account, or import a signed `.json` license file.
2. **Step 2: Local Store Administrator Setup:** Create local master administrator credentials, rapid-switch cashier PIN, and store receipt header profile.

Until both steps are completed:
- All POS billing, inventory, purchasing, and reporting endpoints remain securely locked.
- No default or backdoor credentials exist in the codebase.
- Central client account credentials (licensing portal) remain conceptually separate from local staff/pharmacist accounts.

---

## 2. Step-by-Step Initialization Walkthrough

### Launch Application
Start `start-pharmacy.bat` or navigate to:
```
http://127.0.0.1:38291
```

---

### Step 1 of 2: License & Account Onboarding
The first screen offers three clear paths:

#### Option A: Create Pharmacy Account / Start Free Trial
Fill in minimal store registration details:
1. **Pharmacy / Store Name:** Full trade name of your pharmacy.
2. **Owner / Contact Person:** Pharmacist or proprietor name.
3. **Email Address & Mobile Phone:** Used for client identity and renewal alerts (normalized server-side).
4. **Password:** Minimum 8 characters.
5. **Regulatory Identifiers (Optional):** GSTIN and Drug License numbers (explained clearly as required only for printed receipts and tax registers).

Click **Start Free Trial Now**. The desktop app securely communicates with the Central Licensing API over HTTPS:
* The server creates your client record and issues a cryptographically signed Ed25519 trial license (using vendor-configured duration, e.g. 15, 10, or 4 days).
* The local daemon immediately validates the Ed25519 signature and activates the license locally **without requiring manual file import**.
* The wizard advances seamlessly to Step 2 with store name and contact prefilled.

#### Option B: I Already Have an Account / Sign In
If you already registered your pharmacy or are re-installing:
* Enter your registered email and password.
* The system fetches your active signed commercial/trial license from the server and activates it locally.

#### Option C: Import a Signed License File (.json)
If internet access is unavailable during installation:
* Click **Select .json License File** to load a license provided by your vendor representative.
* The local daemon verifies the cryptographic Ed25519 signature offline and activates the license immediately.

---

### Step 2 of 2: Create Local Store Administrator
Next, configure the local credentials and store profile used for daily dispensing and staff management:

1. **Admin Username:** Administrative operator login (e.g., `admin`). Minimum 3 characters.
2. **Full Name:** Registered pharmacist or store manager name.
3. **Password & Confirmation:** Strong local password (minimum 8 characters).
4. **Quick-Switch 4-Digit PIN:** Rapid operator switching between cashier and pharmacist without typing full passwords during busy counter shifts.
5. **Store Profile & Address:** Physical store address, phone number, GSTIN, and Drug License numbers to print on 80mm thermal receipts and A4 tax invoices.

Click **Complete Setup & Launch POS**.

---

### Step 3: Cryptographic Seeding & Operational Launch
Upon submission, the daemon atomically:
1. Hashes the local administrator password with cryptographic salt and PBKDF2/bcrypt.
2. Hashes the 4-digit PIN.
3. Inserts the root `ADMIN` user into the local database (`pharmacy.db`).
4. Generates a unique 256-bit JWT signing secret into `%LOCALAPPDATA%\PharmacyApp\secret.key`.
5. Seeds initial system configuration.
6. Issues a secure session token and opens the POS dispensing dashboard with the remaining trial/subscription countdown displayed prominently.

---

### Step 4: Post-Setup Staff Account Creation (Optional)
Once logged in as Administrator, navigate to **Settings $\rightarrow$ Users (F9)** to create secondary counter staff:
- **Pharmacist Role:** Can inward purchases, edit inventory, verify Schedule H1 prescriptions, and perform stock audits.
- **Cashier Role:** Restricted strictly to POS counter checkout, customer deposits, and basic returns. Cannot view purchase costs, CA tax packs, or administrative settings.

