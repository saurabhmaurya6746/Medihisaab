# MediHisaab — Security & Administrator Hardening Guide

## 1. Role-Based Access Control (RBAC) Matrix

MediHisaab enforces strict role boundaries across all API endpoints and user interfaces:

| Capability / Resource | Cashier | Pharmacist | Admin |
| :--- | :---: | :---: | :---: |
| POS Counter Billing & Fast Search (F2) | Yes | Yes | Yes |
| Loose Tablet Blister Cutting | Yes | Yes | Yes |
| Hold / Recall Bills (Ctrl+H) | Yes | Yes | Yes |
| Customer Khata Deposits (Ctrl+K) | Yes | Yes | Yes |
| Customer Sales Returns (Resellable) | Yes | Yes | Yes |
| Quick Want-Book Capture (Ctrl+W) | Yes | Yes | Yes |
| Purchase Inwarding Grid (F3) | No | Yes | Yes |
| View Supplier Purchase Rates (PTR) / Margins | No | Yes | Yes |
| Inventory Adjustments & Stock Audits (F6) | No | Yes | Yes |
| Near-Expiry Return Dumps (F5) | No | Yes | Yes |
| Wastage Register Write-offs | No | Yes | Yes |
| Schedule H1 Regulatory Export | No | No | Yes |
| GSTR-1 & GSTR-2 CA Tax Pack Exports | No | No | Yes |
| Sales & Purchase Full Registers | No | No | Yes |
| Day-Book Physical Drawer Closing & Variance | No | No | Yes |
| Hot Backup Creation & Download | No | No | Yes |
| Database Disaster Recovery & Restore | No | No | Yes |
| Store Profile, GSTIN, DL Numbers, Server Mode | No | No | Yes |
| User Account Management & PIN Re-assignment | No | No | Yes |

---

## 2. Cryptographic Secret Management

- **Location:** The authentication JWT secret is stored at `%LOCALAPPDATA%\PharmacyApp\secret.key`.
- **Generation:** Uses Python's `secrets.token_hex(32)` providing 256 bits of cryptographic entropy.
- **Protection:** Stored under the current Windows user's `%LOCALAPPDATA%` directory, inheriting Windows NTFS user ACLs. Other non-administrative Windows accounts on the same machine cannot read this file.
- **Rotation:** If the secret key needs rotation, delete `secret.key` and restart the daemon. All active sessions are immediately invalidated, requiring staff to log in with their passwords.

---

## 3. LAN CORS & Network Boundary Hardening

To allow counter terminals while blocking unauthorized web applications:
- **CORS Allowed Origins:** Restricts web clients to:
  - `http://127.0.0.1:38291`, `http://localhost:38291`
  - Private RFC 1918 IPv4 address ranges:
    - `192.168.0.0/16`
    - `10.0.0.0/8`
    - `172.16.0.0/12`
- Requests originating from public domains, external internet IPs, or cloud domains are rejected at the CORS middleware layer.

---

## 4. Log Hygiene & Error Sanitization

- **Credential Redaction:** Passwords, PINs, and full JWT tokens are never written to disk logs or printed to standard console output.
- **Error Masks:** In production mode, database internal exceptions and Python tracebacks are masked by FastAPI exception handlers. Consumers receive structured JSON envelopes:
  ```json
  {
    "success": false,
    "detail": "Descriptive safe error message",
    "error": {
      "code": "BAD_REQUEST",
      "message": "Descriptive safe error message",
      "timestamp": "2026-10-08T16:50:00Z"
    }
  }
  ```
- **Auditing:** All statutory exports, database restorations, and day-book closures record the operator user ID and timestamp in dedicated immutable audit tables.
