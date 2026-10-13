# Pharmacy Daemon

Native local background daemon and API service for the Offline Pharmacy Management System.

## Architectural Overview

- **Runtime**: Python 3.12+ (FastAPI / Starlette)
- **Database**: Embedded SQLite 3.45+ running in Write-Ahead Logging (`WAL`) mode with `synchronous = NORMAL` and `busy_timeout = 10000ms`.
- **Search**: SQLite `FTS5` full-text search index for sub-millisecond medicine search across 20,000+ SKUs.
- **Monetary Precision**: Pure integer paise (`*_paise`) arithmetic eliminating floating-point drift.
- **Authentication**: Stateless HMAC-SHA256 JWT tokens, bcrypt password hashing, and SHA-256 PIN hashing with Role-Based Access Control (`ADMIN`, `PHARMACIST`, `CASHIER`).

## Launching the Daemon

```bash
# Set PYTHONPATH to daemon src directory:
set PYTHONPATH=apps/daemon/src;%PYTHONPATH%

# Run daemon module:
python -m pharmacy_daemon
```

Or execute the Windows launcher script:
```cmd
scripts\start-backend.bat
```

## Running Automated Tests

```bash
python -m pytest apps/daemon/tests
```
