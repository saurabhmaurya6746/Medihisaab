# MediHisaab — Licensing Security & Threat Model Guide

This document outlines the security architecture, cryptographic safeguards, and privacy controls implemented across the MediHisaab licensing ecosystem.

---

## 1. Zero-Knowledge Client Privacy Policy

The architecture strictly segregates client operational pharmacy data from vendor licensing metadata:

```
+------------------------------------+        +-----------------------------------+
|       OFFLINE CLIENT PHARMACY      |        |        VENDOR CLOUD SYSTEM        |
|                                    |        |                                   |
| - Medicine inventory batches       |        | - Client registration directory   |
| - Patient & Doctor records         |  NONE  | - Subscription plan catalog       |
| - Sale bills & Invoices            |  <==>  | - Manual payment records          |
| - Customer Khata ledgers           |        | - Issued Ed25519 license tokens   |
| - Local SQLite (pharmacy.db)       |        | - Managed PostgreSQL (Render)     |
+------------------------------------+        +-----------------------------------+
```

* **No Cloud Operational Telemetry:** The vendor does not collect patient prescriptions, medicine sales volumes, customer balances, or pharmacy margins.
* **Offline Sovereignty:** Pharmacy operations continue even under complete network blackout.

---

## 2. Infrastructure Segregation

The system is deployed into three strictly separated tiers:

### Tier 1: Client MediHisaab
* **Environment:** Client's local desktop or LAN network.
* **Data Store:** SQLite database (`%LOCALAPPDATA%\PharmacyApp\data\pharmacy.db`).
* **Cryptographic Role:** Holds only the **Ed25519 Public Key** to verify incoming license tokens offline.

### Tier 2: Public Download Portal
* **Environment:** Render Static Site (`pharmacy-pos-portal`).
* **Content:** Built installer (`MediHisaab-Setup-1.0.0.exe`), user manuals, hardware setup guides.
* **Security Rule:** **Strictly zero database files, zero client records, zero licenses, zero private keys.**

### Tier 3: Central Vendor Licensing Portal & API
* **Environment:** Render Web Service (`pharmacy-licensing-api`) + Managed PostgreSQL (`pharmacy-licensing-db`).
* **Security Controls:** Authenticated with short-lived JWT, role-based access control, IP rate limiting, and encrypted environment variables.

---

## 3. Cryptographic Key Management

### 3.1 Algorithm: Ed25519 (RFC 8032)
* High security (128-bit security level) with small 64-byte signatures and 32-byte keys.
* Deterministic signatures immune to side-channel timing attacks and poor random number generators.

### 3.2 Private Signing Key Protection
* **Server-Only Storage:** Stored strictly as a private environment variable:
  `LICENSE_PRIVATE_KEY_PEM`
* **Never Committed:** `publisher_keys/` and `.pem` files are excluded in `.gitignore`.
* **Zero Client Distribution:** The private key is never compiled into the client daemon executable or client installer.

### 3.3 Public Verification Key
* The 32-byte public key is embedded as a hex literal in the client daemon:
  `ba7a4f28067b0d4d4e7d90128c48f9316ba5c3069a0cb88fcc5a24b081b3632b`
* Any modification of the public key inside the compiled client application invalidates client licenses and fails checksum verification.

---

## 4. Vendor Authentication & Portal Defense

### 4.1 Password Security
* Passwords are never stored in plaintext.
* Hashed using **PBKDF2-SHA256** and **Bcrypt** adaptive key derivation algorithms.

### 4.2 Brute-Force Rate Limiting
* `/api/v1/auth/login` tracks failed attempts per client IP.
* Exceeding 5 failed attempts in 60 seconds triggers `HTTP 429 Too Many Requests`.
* Successful login clears the attempt counter.

### 4.3 Session Tokens
* Bearer tokens use HMAC-SHA256 (JWT) signed with a high-entropy secret (`JWT_SECRET_KEY`).
* Expiration set to 60 minutes for high security, requiring re-authentication.

### 4.4 Tamper-Evident Audit Logging
* All administrative state mutations (`CREATE_CLIENT`, `START_TRIAL`, `CREATE_PAID_SUBSCRIPTION`, `GENERATE_LICENSE`, `REVOKE_LICENSE`) append to an immutable `audit_events` log.
* **Automatic Credential Sanitization:** Sensitive fields (`password`, `password_hash`, `private_key`) are stripped from log metadata prior to persistence.
