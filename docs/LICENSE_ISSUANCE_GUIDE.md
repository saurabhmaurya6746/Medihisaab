# MediHisaab — License Issuance & Import Guide

This guide details the cryptographic license architecture, issuance procedure for vendors, and the import procedure for pharmacy administrators.

---

## 1. Cryptographic Architecture (Ed25519)

MediHisaab uses **Ed25519 asymmetric digital signatures** (RFC 8032):
* **Vendor Private Key:** Stored strictly on the Central Licensing API server as a secure environment variable (`LICENSE_PRIVATE_KEY_PEM`). Never distributed to clients, never committed to git, never present in the public portal.
* **Embedded Public Key:** Embedded in the client daemon (`apps/daemon/src/pharmacy_daemon/security/license.py`):
  ```
  ba7a4f28067b0d4d4e7d90128c48f9316ba5c3069a0cb88fcc5a24b081b3632b
  ```
* **Offline Verification:** The client workstation verifies the digital signature mathematically using the public key. **Zero internet connection is required.**

---

## 2. License Token File Format (`license.json`)

A valid issued license is a standard UTF-8 JSON file containing:

```json
{
  "license_id": "LIC-CL1001-20261009-5A3B",
  "client_name": "Sunrise Chemist & Druggist",
  "terminal_count": 5,
  "activation_date": "2026-10-09",
  "expiry_date": "2027-10-23",
  "edition": "COMMERCIAL",
  "features": "ALL",
  "signature": "3a9f1b8c4d2e...[128 hex characters]..."
}
```

### Canonical Payload Construction
To sign and verify deterministically, fields are sorted alphabetically:
```
activation_date=<val>|client_name=<val>|edition=<val>|expiry_date=<val>|features=<val>|license_id=<val>|terminal_count=<val>
```

---

## 3. Vendor Issuance Procedure

1. Log into the **Vendor Licensing Portal** (`https://licensing.apexhealth.com/vendor`).
2. Go to **Licenses** $\rightarrow$ Click **+ Generate New License**.
3. Select the target client and verify:
   * **Terminal Limit:** e.g. `5` for a 5-counter LAN setup.
   * **Expiry Date:** Subscription end date plus 14-day grace window.
   * **Edition:** `COMMERCIAL` (or `TRIAL`).
4. Click **Generate & Sign License**.
5. Click **Download .json** to obtain `LIC-CL1001-20261009-5A3B.json`.
6. Send the downloaded `.json` file securely to the client pharmacy.

---

## 4. Client Import Procedure (MediHisaab)

1. Open **MediHisaab** on the server computer (`http://127.0.0.1:38291`).
2. Log in with an **ADMIN** user account.
3. Click the **Gear icon (Settings)** in the top navigation header.
4. Select the **License** section on the left sidebar.
5. In the **Import License File** card:
   * Click **Choose File** (or drag and drop).
   * Select the received `.json` license file.
   * Click **Import License File**.
6. The application performs instant offline cryptographic verification:
   * **Client Name:** Confirmed against file.
   * **License ID:** Displayed clearly.
   * **Terminal Count:** Maximum allowed counter computers.
   * **Expiry Date:** Validated against system clock.
   * **Edition:** `COMMERCIAL` or `TRIAL`.
   * **Status:** Displayed in calm green `ACTIVE`.

---

## 5. Security & Anti-Tampering Guarantee

Any unauthorized modification of the license file instantly breaks cryptographic validity:
* If a user modifies `"terminal_count": 10` (attempting to add counters without paying), the Ed25519 signature verification fails.
* If a user alters `"expiry_date": "2099-12-31"`, the Ed25519 signature verification fails.
* If a signature is invalid or tampered with, the system rejects the file with a clear error:
  `"Invalid license signature. File may have been tampered with or corrupted."`
* Previous valid licenses remain intact until an authentic signed license is imported.
