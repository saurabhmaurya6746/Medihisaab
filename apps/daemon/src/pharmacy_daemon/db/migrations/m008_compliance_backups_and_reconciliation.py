"""Migration 008: Compliance reports, backup manifests, system configuration, and cash session reconciliation.

Entities introduced:
1. backup_manifests: Audit ledger of hot SQLite backups, hashes, and verification metadata
2. system_config: Persistent operational settings (server mode, LAN host/port, backup directory)
3. cash_sessions: Day-book cash reconciliation, drawer counts, variance tracking, and closed-day immutability
4. export_audit_logs: Compliance and statutory export generation tracking
5. customers: add gstin for B2B invoice generation
6. sale_invoices: add customer_gstin for GSTR-1 B2B/B2C separation
"""

from datetime import datetime, timezone
import sqlite3

VERSION = 8
NAME = "008_compliance_backups_and_reconciliation"


def _get_columns(cursor: sqlite3.Cursor, table_name: str) -> set[str]:
    cursor.execute(f"PRAGMA table_info({table_name});")
    return {row[1] for row in cursor.fetchall()}


def apply(conn: sqlite3.Connection) -> None:
    """Apply migration 008 schema changes."""
    cursor = conn.cursor()
    now_str = datetime.now(timezone.utc).isoformat()

    # 1. backup_manifests (Audit records of database backups)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS backup_manifests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE NOT NULL,
            filepath TEXT NOT NULL,
            file_size_bytes INTEGER NOT NULL CHECK (file_size_bytes >= 0),
            sha256_hash TEXT NOT NULL,
            backup_type TEXT NOT NULL DEFAULT 'MANUAL' CHECK (backup_type IN ('MANUAL', 'AUTOMATED', 'PRE_RESTORE_SAFETY')),
            status TEXT NOT NULL DEFAULT 'VALID' CHECK (status IN ('VALID', 'CORRUPT', 'RESTORED')),
            schema_version INTEGER NOT NULL,
            invoice_count INTEGER NOT NULL DEFAULT 0 CHECK (invoice_count >= 0),
            medicine_count INTEGER NOT NULL DEFAULT 0 CHECK (medicine_count >= 0),
            revenue_total_paise INTEGER NOT NULL DEFAULT 0 CHECK (revenue_total_paise >= 0),
            khata_balance_paise INTEGER NOT NULL DEFAULT 0,
            notes TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL,
            verified_at TEXT
        );
    """)

    # 2. system_config (Key-value system administration configuration)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            description TEXT,
            is_secret INTEGER NOT NULL DEFAULT 0 CHECK (is_secret IN (0, 1)),
            updated_by INTEGER REFERENCES users(id),
            updated_at TEXT NOT NULL
        );
    """)

    # Seed default configuration keys if not present
    default_configs = [
        ("server_mode", "STANDALONE", "Operational mode: STANDALONE or LAN_SERVER"),
        ("lan_host", "0.0.0.0", "LAN bind interface when running in LAN_SERVER mode"),
        ("lan_port", "38291", "HTTP port for the POS daemon"),
        ("backup_directory", "", "Custom backup archive storage path (empty for default)"),
        ("auto_backup_enabled", "true", "Whether daily automated backups are active"),
        ("store_name", "Apex Health Pharmacy", "Store trading business name on invoices"),
        ("store_gstin", "", "Pharmacy GSTIN for tax invoices and reports"),
        ("store_dl_number", "DL-20B-12345/21B-67890", "Pharmacy Drug License numbers"),
    ]
    for key, val, desc in default_configs:
        cursor.execute("""
            INSERT OR IGNORE INTO system_config (key, value, description, is_secret, updated_at)
            VALUES (?, ?, ?, 0, ?);
        """, (key, val, desc, now_str))

    # 3. cash_sessions (Day-book opening float, cash totals, actual count, variance)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cash_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date TEXT UNIQUE NOT NULL, -- Format YYYY-MM-DD
            opening_float_paise INTEGER NOT NULL DEFAULT 0 CHECK (opening_float_paise >= 0),
            cash_sales_paise INTEGER NOT NULL DEFAULT 0 CHECK (cash_sales_paise >= 0),
            cash_deposits_paise INTEGER NOT NULL DEFAULT 0 CHECK (cash_deposits_paise >= 0),
            cash_refunds_paise INTEGER NOT NULL DEFAULT 0 CHECK (cash_refunds_paise >= 0),
            expected_cash_paise INTEGER NOT NULL DEFAULT 0,
            actual_cash_paise INTEGER,
            variance_paise INTEGER,
            status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED')),
            closed_by INTEGER REFERENCES users(id),
            closed_at TEXT,
            notes TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)

    # 4. export_audit_logs (Compliance and tax pack export audit ledger)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS export_audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_type TEXT NOT NULL,
            format TEXT NOT NULL DEFAULT 'CSV',
            filter_params TEXT,
            row_count INTEGER NOT NULL DEFAULT 0 CHECK (row_count >= 0),
            file_name TEXT,
            generated_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL
        );
    """)

    # 5. Extend customers: add gstin for B2B buyers
    cust_cols = _get_columns(cursor, "customers")
    if "gstin" not in cust_cols:
        cursor.execute("ALTER TABLE customers ADD COLUMN gstin TEXT;")

    # 6. Extend sale_invoices: add customer_gstin for GSTR-1 classification
    inv_cols = _get_columns(cursor, "sale_invoices")
    if "customer_gstin" not in inv_cols:
        cursor.execute("ALTER TABLE sale_invoices ADD COLUMN customer_gstin TEXT;")

    # 7. Performance and audit indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_backup_manifests_created ON backup_manifests(created_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_backup_manifests_type ON backup_manifests(backup_type);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cash_sessions_date ON cash_sessions(session_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cash_sessions_status ON cash_sessions(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_export_audit_logs_type ON export_audit_logs(report_type, created_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sale_invoices_gstin ON sale_invoices(customer_gstin);")
