"""Authoritative SQLite database engine wrapper."""

import logging
from pathlib import Path
import sqlite3
from typing import Dict, Any

from .connection import create_connection
from .migrations import run_migrations, get_applied_versions

logger = logging.getLogger("pharmacy_daemon.db.engine")


class DatabaseEngine:
    """Manages SQLite database lifecycle, migrations, and health diagnostics."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._is_initialized = False

    def initialize(self) -> None:
        """Initialize database file, apply pragmas, and run pending migrations."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self.get_connection()
        try:
            run_migrations(conn)
            self._ensure_compatibility(conn)
        finally:
            conn.close()
        self._is_initialized = True
        logger.info("Authoritative SQLite engine initialized at %s", self.db_path)

    def _ensure_compatibility(self, conn: sqlite3.Connection) -> None:
        """Ensure backward compatibility for legacy databases missing foundational tables or columns."""
        from datetime import datetime, timezone

        cursor = conn.cursor()
        now_str = datetime.now(timezone.utc).isoformat()

        def table_exists(tbl: str) -> bool:
            cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?;", (tbl,))
            return cursor.fetchone() is not None

        def get_columns(tbl: str) -> set[str]:
            cursor.execute(f"PRAGMA table_info({tbl});")
            return {r[1] for r in cursor.fetchall()}

        # 1. users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                pin_hash TEXT,
                role TEXT NOT NULL CHECK (role IN ('ADMIN', 'PHARMACIST', 'CASHIER')),
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);")

        # 2. system_settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

        # 3. system_config table
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

        # 4. Migrate store settings from legacy app_settings if present
        if table_exists("app_settings"):
            cursor.execute("SELECT key, value, updated_at FROM app_settings;")
            app_rows = {r[0]: (r[1], r[2]) for r in cursor.fetchall()}

            mapping = {
                "store.name": ("store_name", "Store trading business name on invoices"),
                "store.address": ("store_address", "Pharmacy registered business address"),
                "store.gstin": ("store_gstin", "Pharmacy GSTIN for tax invoices and reports"),
                "store.dl_20": ("store_dl_number_20b", "Drug license form 20B"),
                "store.dl_21": ("store_dl_number_21b", "Drug license form 21B"),
                "store.state_code": ("store_state_code", "State jurisdiction code"),
            }

            for app_key, (target_key, desc) in mapping.items():
                if app_key in app_rows:
                    val, updated_at = app_rows[app_key]
                    cursor.execute("""
                        INSERT OR IGNORE INTO system_settings (key, value, updated_at)
                        VALUES (?, ?, ?);
                    """, (target_key, val, updated_at))
                    cursor.execute("""
                        INSERT OR IGNORE INTO system_config (key, value, description, is_secret, updated_at)
                        VALUES (?, ?, ?, 0, ?);
                    """, (target_key, val, desc, updated_at))

            dl20 = app_rows.get("store.dl_20", ("", ""))[0]
            dl21 = app_rows.get("store.dl_21", ("", ""))[0]
            combined_dl = " / ".join(filter(None, [dl20, dl21]))
            if combined_dl:
                cursor.execute("""
                    INSERT OR IGNORE INTO system_config (key, value, description, is_secret, updated_at)
                    VALUES ('store_dl_number', ?, 'Combined drug license numbers', 0, ?);
                """, (combined_dl, now_str))

        # 5. Synchronize store_name across system_config and system_settings (if customized or admin exists)
        cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users';")
        has_admin = False
        if cursor.fetchone() is not None:
            cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'ADMIN' AND is_active = 1;")
            has_admin = cursor.fetchone()[0] > 0

        cursor.execute("SELECT value FROM system_config WHERE key = 'store_name';")
        cfg_store = cursor.fetchone()
        cursor.execute("SELECT value FROM system_settings WHERE key = 'store_name';")
        set_store = cursor.fetchone()

        if cfg_store and not set_store and (has_admin or cfg_store[0].strip().lower() != "apex health pharmacy"):
            cursor.execute("""
                INSERT OR IGNORE INTO system_settings (key, value, updated_at)
                VALUES ('store_name', ?, ?);
            """, (cfg_store[0], now_str))
        elif set_store and not cfg_store:
            cursor.execute("""
                INSERT OR IGNORE INTO system_config (key, value, description, is_secret, updated_at)
                VALUES ('store_name', ?, 'Store trading business name on invoices', 0, ?);
            """, (set_store[0], now_str))

        # 6. Seed system_config defaults (store_name is configured during first-run setup or migrated from app_settings)
        default_configs = [
            ("server_mode", "STANDALONE", "Operational mode: STANDALONE or LAN_SERVER"),
            ("lan_host", "0.0.0.0", "LAN bind interface when running in LAN_SERVER mode"),
            ("lan_port", "38291", "HTTP port for the POS daemon"),
            ("backup_directory", "", "Custom backup archive storage path (empty for default)"),
            ("auto_backup_enabled", "true", "Whether daily automated backups are active"),
            ("store_gstin", "", "Pharmacy GSTIN for tax invoices and reports"),
            ("store_dl_number", "DL-20B-12345/21B-67890", "Pharmacy Drug License numbers"),
        ]
        for key, val, desc in default_configs:
            cursor.execute("""
                INSERT OR IGNORE INTO system_config (key, value, description, is_secret, updated_at)
                VALUES (?, ?, ?, 0, ?);
            """, (key, val, desc, now_str))

        # 7. Migrate legacy batches to medicine_batches if batches exists
        if table_exists("batches"):
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS medicine_batches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    medicine_id INTEGER NOT NULL REFERENCES medicines(id),
                    batch_number TEXT NOT NULL,
                    expiry_date TEXT NOT NULL,
                    mrp_paise INTEGER NOT NULL DEFAULT 0 CHECK (mrp_paise >= 0),
                    purchase_rate_paise INTEGER NOT NULL DEFAULT 0 CHECK (purchase_rate_paise >= 0),
                    pack_size INTEGER NOT NULL DEFAULT 1 CHECK (pack_size >= 1),
                    current_quantity INTEGER NOT NULL DEFAULT 0 CHECK (current_quantity >= 0),
                    reserved_quantity INTEGER NOT NULL DEFAULT 0 CHECK (reserved_quantity >= 0),
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    CONSTRAINT uq_medicine_batch UNIQUE (medicine_id, batch_number)
                );
            """)
            cursor.execute("""
                INSERT OR IGNORE INTO medicine_batches (
                    id, medicine_id, batch_number, expiry_date,
                    mrp_paise, purchase_rate_paise, pack_size,
                    current_quantity, reserved_quantity, is_active,
                    created_at, updated_at
                )
                SELECT
                    b.id, b.medicine_id, b.batch_number, b.expiry_date,
                    CAST(ROUND(COALESCE(b.mrp, 0.0) * 100) AS INTEGER),
                    CAST(ROUND(COALESCE(b.purchase_rate, 0.0) * 100) AS INTEGER),
                    COALESCE(m.pack_size, 1),
                    COALESCE(b.stock_units, 0),
                    0, 1,
                    b.created_at, b.updated_at
                FROM batches b
                LEFT JOIN medicines m ON m.id = b.medicine_id;
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_medicine_batches_med_exp ON medicine_batches(medicine_id, expiry_date);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_medicine_batches_number ON medicine_batches(batch_number);")

        # 8. Ensure other required system tables exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                medicine_id INTEGER NOT NULL REFERENCES medicines(id),
                batch_id INTEGER NOT NULL REFERENCES medicine_batches(id),
                transaction_type TEXT NOT NULL,
                quantity_change INTEGER NOT NULL,
                quantity_balance INTEGER NOT NULL CHECK (quantity_balance >= 0),
                reference_type TEXT NOT NULL,
                reference_id INTEGER,
                notes TEXT,
                user_id INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL
            );
        """)
        # Held bills
        if table_exists("held_bills"):
            hb_cols = get_columns("held_bills")
            if "hold_reference" not in hb_cols:
                cursor.execute("DROP TABLE IF EXISTS held_bills;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS held_bills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hold_reference TEXT UNIQUE NOT NULL,
                customer_id INTEGER REFERENCES customers(id),
                customer_name TEXT,
                customer_phone TEXT,
                doctor_name TEXT,
                doctor_address TEXT,
                items_json TEXT NOT NULL,
                subtotal_paise INTEGER NOT NULL DEFAULT 0,
                total_tax_paise INTEGER NOT NULL DEFAULT 0,
                grand_total_paise INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                created_by INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_held_bills_ref ON held_bills(hold_reference);")

        # Supplier payable ledger
        if table_exists("supplier_payable_ledger"):
            spl_cols = get_columns("supplier_payable_ledger")
            if "entry_type" not in spl_cols:
                cursor.execute("DROP TABLE IF EXISTS supplier_payable_ledger;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS supplier_payable_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
                reference_type TEXT NOT NULL DEFAULT 'PURCHASE_INVOICE',
                reference_id INTEGER,
                entry_type TEXT NOT NULL CHECK (entry_type IN ('DEBIT', 'CREDIT', 'INVOICE_POSTED', 'PAYMENT_OUT', 'PURCHASE_RETURN_DEBIT', 'ADJUSTMENT')),
                amount_paise INTEGER NOT NULL DEFAULT 0,
                balance_paise INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                user_id INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_supplier_payable_ledger_supplier ON supplier_payable_ledger(supplier_id);")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cash_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_date TEXT UNIQUE NOT NULL,
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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sale_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_invoice_id INTEGER NOT NULL REFERENCES sale_invoices(id) ON DELETE CASCADE,
                payment_mode TEXT NOT NULL CHECK (payment_mode IN ('CASH', 'UPI', 'CARD', 'SPLIT', 'KHATA')),
                amount_paise INTEGER NOT NULL CHECK (amount_paise >= 0),
                reference_number TEXT,
                reference_note TEXT,
                created_at TEXT NOT NULL
            );
        """)

        # 9. FTS5 full-text index
        if table_exists("medicines"):
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS fts_medicines USING fts5(
                    brand_name,
                    generic_salt,
                    content='medicines',
                    content_rowid='id'
                );
            """)
            cursor.execute("""
                INSERT INTO fts_medicines(rowid, brand_name, generic_salt)
                SELECT id, brand_name, generic_salt FROM medicines
                WHERE id NOT IN (SELECT rowid FROM fts_medicines);
            """)

        # 10. Check and add missing columns to existing tables
        if table_exists("customers"):
            c_cols = get_columns("customers")
            if "default_doctor" not in c_cols:
                cursor.execute("ALTER TABLE customers ADD COLUMN default_doctor TEXT;")
            if "gstin" not in c_cols:
                cursor.execute("ALTER TABLE customers ADD COLUMN gstin TEXT;")
            if "is_active" not in c_cols:
                cursor.execute("ALTER TABLE customers ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1;")
            if "credit_limit_paise" not in c_cols:
                cursor.execute("ALTER TABLE customers ADD COLUMN credit_limit_paise INTEGER NOT NULL DEFAULT 500000 CHECK (credit_limit_paise >= 0);")
                if "credit_limit" in c_cols:
                    cursor.execute("UPDATE customers SET credit_limit_paise = CAST(ROUND(COALESCE(credit_limit, 5000.0) * 100) AS INTEGER);")
            if "current_balance_paise" not in c_cols:
                cursor.execute("ALTER TABLE customers ADD COLUMN current_balance_paise INTEGER NOT NULL DEFAULT 0;")
                if "current_balance" in c_cols:
                    cursor.execute("UPDATE customers SET current_balance_paise = CAST(ROUND(COALESCE(current_balance, 0.0) * 100) AS INTEGER);")
            if "updated_at" not in c_cols:
                cursor.execute(f"ALTER TABLE customers ADD COLUMN updated_at TEXT NOT NULL DEFAULT '{now_str}';")

        if table_exists("suppliers"):
            s_cols = get_columns("suppliers")
            if "credit_days" not in s_cols:
                cursor.execute("ALTER TABLE suppliers ADD COLUMN credit_days INTEGER NOT NULL DEFAULT 21;")
            if "current_payable_paise" not in s_cols:
                cursor.execute("ALTER TABLE suppliers ADD COLUMN current_payable_paise INTEGER NOT NULL DEFAULT 0 CHECK (current_payable_paise >= 0);")
                if "current_payable" in s_cols:
                    cursor.execute("UPDATE suppliers SET current_payable_paise = CAST(ROUND(COALESCE(current_payable, 0.0) * 100) AS INTEGER);")

        if table_exists("sale_invoices"):
            si_cols = get_columns("sale_invoices")
            if "subtotal_taxable" in si_cols:
                logger.info("Upgrading legacy sale_invoices and sale_items schema to authoritative paise...")
                cursor.execute("PRAGMA foreign_keys = OFF;")
                cursor.execute("ALTER TABLE sale_invoices RENAME TO sale_invoices_old;")
                cursor.execute("""
                    CREATE TABLE sale_invoices (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        invoice_no TEXT UNIQUE NOT NULL,
                        fiscal_year TEXT NOT NULL,
                        sequence_number INTEGER NOT NULL DEFAULT 1,
                        customer_id INTEGER REFERENCES customers(id),
                        customer_name TEXT,
                        customer_phone TEXT,
                        customer_gstin TEXT,
                        doctor_name TEXT,
                        doctor_address TEXT,
                        subtotal_taxable_paise INTEGER NOT NULL DEFAULT 0 CHECK (subtotal_taxable_paise >= 0),
                        total_cgst_paise INTEGER NOT NULL DEFAULT 0 CHECK (total_cgst_paise >= 0),
                        total_sgst_paise INTEGER NOT NULL DEFAULT 0 CHECK (total_sgst_paise >= 0),
                        total_igst_paise INTEGER NOT NULL DEFAULT 0 CHECK (total_igst_paise >= 0),
                        discount_paise INTEGER NOT NULL DEFAULT 0 CHECK (discount_paise >= 0),
                        round_off_paise INTEGER NOT NULL DEFAULT 0,
                        grand_total_paise INTEGER NOT NULL DEFAULT 0 CHECK (grand_total_paise >= 0),
                        payment_mode TEXT NOT NULL CHECK (payment_mode IN ('CASH', 'UPI', 'CARD', 'KHATA', 'SPLIT')),
                        cash_tendered_paise INTEGER NOT NULL DEFAULT 0 CHECK (cash_tendered_paise >= 0),
                        change_returned_paise INTEGER NOT NULL DEFAULT 0 CHECK (change_returned_paise >= 0),
                        status TEXT NOT NULL DEFAULT 'COMPLETED' CHECK (status IN ('COMPLETED', 'CANCELLED')),
                        notes TEXT,
                        created_by INTEGER REFERENCES users(id),
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        CONSTRAINT uq_sale_invoice_sequence UNIQUE (fiscal_year, sequence_number)
                    );
                """)
                cursor.execute("""
                    INSERT INTO sale_invoices (
                        id, invoice_no, fiscal_year, sequence_number, customer_id,
                        customer_name, customer_phone, customer_gstin, doctor_name, doctor_address,
                        subtotal_taxable_paise, total_cgst_paise, total_sgst_paise, total_igst_paise,
                        discount_paise, round_off_paise, grand_total_paise, payment_mode,
                        cash_tendered_paise, change_returned_paise, status, notes,
                        created_by, created_at, updated_at
                    )
                    SELECT
                        id, invoice_no, fiscal_year, COALESCE(sequence_number, 1), customer_id,
                        customer_name, customer_phone, customer_gstin, doctor_name, doctor_address,
                        CASE WHEN subtotal_taxable_paise > 0 THEN subtotal_taxable_paise ELSE CAST(ROUND(COALESCE(subtotal_taxable, 0.0) * 100) AS INTEGER) END,
                        CASE WHEN total_cgst_paise > 0 THEN total_cgst_paise ELSE CAST(ROUND(COALESCE(total_cgst, 0.0) * 100) AS INTEGER) END,
                        CASE WHEN total_sgst_paise > 0 THEN total_sgst_paise ELSE CAST(ROUND(COALESCE(total_sgst, 0.0) * 100) AS INTEGER) END,
                        CASE WHEN total_igst_paise > 0 THEN total_igst_paise ELSE CAST(ROUND(COALESCE(total_igst, 0.0) * 100) AS INTEGER) END,
                        COALESCE(discount_paise, 0),
                        COALESCE(round_off_paise, 0),
                        CASE WHEN grand_total_paise > 0 THEN grand_total_paise ELSE CAST(ROUND(COALESCE(grand_total, 0.0) * 100) AS INTEGER) END,
                        COALESCE(payment_mode, 'CASH'),
                        COALESCE(cash_tendered_paise, 0),
                        COALESCE(change_returned_paise, 0),
                        COALESCE(status, 'COMPLETED'),
                        notes,
                        created_by,
                        created_at,
                        COALESCE(updated_at, created_at)
                    FROM sale_invoices_old;
                """)
                cursor.execute("DROP TABLE sale_invoices_old;")

                if table_exists("sale_items"):
                    cursor.execute("ALTER TABLE sale_items RENAME TO sale_items_old;")
                    cursor.execute("""
                        CREATE TABLE sale_items (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            sale_invoice_id INTEGER NOT NULL REFERENCES sale_invoices(id) ON DELETE CASCADE,
                            medicine_id INTEGER NOT NULL REFERENCES medicines(id),
                            batch_id INTEGER NOT NULL REFERENCES medicine_batches(id),
                            quantity_units INTEGER NOT NULL CHECK (quantity_units > 0),
                            unit_mrp_paise INTEGER NOT NULL CHECK (unit_mrp_paise >= 0),
                            unit_rate_paise INTEGER NOT NULL CHECK (unit_rate_paise >= 0),
                            discount_percent REAL NOT NULL DEFAULT 0.0 CHECK (discount_percent >= 0.0 AND discount_percent <= 100.0),
                            taxable_amount_paise INTEGER NOT NULL CHECK (taxable_amount_paise >= 0),
                            gst_rate REAL NOT NULL DEFAULT 0.0 CHECK (gst_rate >= 0.0),
                            cgst_amount_paise INTEGER NOT NULL CHECK (cgst_amount_paise >= 0),
                            sgst_amount_paise INTEGER NOT NULL CHECK (sgst_amount_paise >= 0),
                            total_amount_paise INTEGER NOT NULL CHECK (total_amount_paise >= 0),
                            created_at TEXT NOT NULL
                        );
                    """)
                    cursor.execute("""
                        INSERT INTO sale_items (
                            id, sale_invoice_id, medicine_id, batch_id, quantity_units,
                            unit_mrp_paise, unit_rate_paise, discount_percent,
                            taxable_amount_paise, gst_rate, cgst_amount_paise, sgst_amount_paise,
                            total_amount_paise, created_at
                        )
                        SELECT
                            sio.id,
                            sio.sale_invoice_id,
                            COALESCE(sio.medicine_id, mb.medicine_id, 1),
                            sio.batch_id,
                            sio.quantity_units,
                            CASE WHEN sio.unit_mrp_paise > 0 THEN sio.unit_mrp_paise ELSE CAST(ROUND(COALESCE(sio.unit_mrp, 0.0) * 100) AS INTEGER) END,
                            CASE WHEN sio.unit_rate_paise > 0 THEN sio.unit_rate_paise ELSE CAST(ROUND(COALESCE(sio.unit_rate, 0.0) * 100) AS INTEGER) END,
                            COALESCE(sio.discount_percent, 0.0),
                            CASE WHEN sio.taxable_amount_paise > 0 THEN sio.taxable_amount_paise ELSE CAST(ROUND(COALESCE(sio.taxable_amount, 0.0) * 100) AS INTEGER) END,
                            COALESCE(sio.gst_rate, 0.0),
                            CASE WHEN sio.cgst_amount_paise > 0 THEN sio.cgst_amount_paise ELSE CAST(ROUND(COALESCE(sio.cgst_amount, 0.0) * 100) AS INTEGER) END,
                            CASE WHEN sio.sgst_amount_paise > 0 THEN sio.sgst_amount_paise ELSE CAST(ROUND(COALESCE(sio.sgst_amount, 0.0) * 100) AS INTEGER) END,
                            CASE WHEN sio.total_amount_paise > 0 THEN sio.total_amount_paise ELSE CAST(ROUND(COALESCE(sio.total_amount, 0.0) * 100) AS INTEGER) END,
                            sio.created_at
                        FROM sale_items_old sio
                        LEFT JOIN medicine_batches mb ON mb.id = sio.batch_id;
                    """)
                    cursor.execute("DROP TABLE sale_items_old;")

                cursor.execute("PRAGMA foreign_keys = ON;")
            else:
                missing_si = [
                    ("customer_gstin", "TEXT"),
                    ("customer_name", "TEXT"),
                    ("customer_phone", "TEXT"),
                    ("notes", "TEXT"),
                    ("change_returned_paise", "INTEGER NOT NULL DEFAULT 0"),
                    ("subtotal_taxable_paise", "INTEGER NOT NULL DEFAULT 0"),
                    ("total_cgst_paise", "INTEGER NOT NULL DEFAULT 0"),
                    ("total_sgst_paise", "INTEGER NOT NULL DEFAULT 0"),
                    ("total_igst_paise", "INTEGER NOT NULL DEFAULT 0"),
                    ("round_off_paise", "INTEGER NOT NULL DEFAULT 0"),
                    ("grand_total_paise", "INTEGER NOT NULL DEFAULT 0"),
                    ("cash_tendered_paise", "INTEGER NOT NULL DEFAULT 0"),
                    ("discount_paise", "INTEGER NOT NULL DEFAULT 0"),
                    ("sequence_number", "INTEGER NOT NULL DEFAULT 1"),
                    ("created_by", "INTEGER"),
                    ("updated_at", f"TEXT NOT NULL DEFAULT '{now_str}'"),
                ]
                for col_name, col_def in missing_si:
                    if col_name not in si_cols:
                        cursor.execute(f"ALTER TABLE sale_invoices ADD COLUMN {col_name} {col_def};")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sale_invoices_no ON sale_invoices(invoice_no);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sale_invoices_fy ON sale_invoices(fiscal_year);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sale_invoices_customer ON sale_invoices(customer_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sale_invoices_created_at ON sale_invoices(created_at);")

        if table_exists("sale_items"):
            sit_cols = get_columns("sale_items")
            missing_sit = [
                ("medicine_id", "INTEGER"),
                ("unit_mrp_paise", "INTEGER NOT NULL DEFAULT 0"),
                ("unit_rate_paise", "INTEGER NOT NULL DEFAULT 0"),
                ("taxable_amount_paise", "INTEGER NOT NULL DEFAULT 0"),
                ("cgst_amount_paise", "INTEGER NOT NULL DEFAULT 0"),
                ("sgst_amount_paise", "INTEGER NOT NULL DEFAULT 0"),
                ("total_amount_paise", "INTEGER NOT NULL DEFAULT 0"),
                ("created_at", f"TEXT NOT NULL DEFAULT '{now_str}'"),
            ]
            for col_name, col_def in missing_sit:
                if col_name not in sit_cols:
                    cursor.execute(f"ALTER TABLE sale_items ADD COLUMN {col_name} {col_def};")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sale_items_invoice ON sale_items(sale_invoice_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sale_items_batch ON sale_items(batch_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sale_items_medicine ON sale_items(medicine_id);")

        # 11. medicines table: ensure medicine_code and strength exist
        if table_exists("medicines"):
            med_cols = get_columns("medicines")
            if "medicine_code" not in med_cols:
                cursor.execute("ALTER TABLE medicines ADD COLUMN medicine_code TEXT;")
                cursor.execute("UPDATE medicines SET medicine_code = 'MED-' || printf('%05d', id) WHERE medicine_code IS NULL;")
            if "strength" not in med_cols:
                cursor.execute("ALTER TABLE medicines ADD COLUMN strength TEXT;")

        # 12. manufacturers table: ensure is_active and updated_at exist
        if table_exists("manufacturers"):
            mfg_cols = get_columns("manufacturers")
            if "is_active" not in mfg_cols:
                cursor.execute("ALTER TABLE manufacturers ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1;")
            if "updated_at" not in mfg_cols:
                cursor.execute(f"ALTER TABLE manufacturers ADD COLUMN updated_at TEXT NOT NULL DEFAULT '{now_str}';")

        # 13. purchase_invoices table: ensure modern columns exist
        if table_exists("purchase_invoices"):
            pi_cols = get_columns("purchase_invoices")
            pi_missing = [
                ("notes", "TEXT"),
                ("created_by", "INTEGER REFERENCES users(id)"),
                ("posted_at", "TEXT"),
                ("updated_at", f"TEXT NOT NULL DEFAULT '{now_str}'"),
                ("entry_date", f"TEXT NOT NULL DEFAULT '{now_str}'"),
                ("status", "TEXT NOT NULL DEFAULT 'DRAFT'"),
                ("subtotal_paise", "INTEGER NOT NULL DEFAULT 0"),
                ("discount_paise", "INTEGER NOT NULL DEFAULT 0"),
                ("tax_amount_paise", "INTEGER NOT NULL DEFAULT 0"),
                ("grand_total_paise", "INTEGER NOT NULL DEFAULT 0"),
            ]
            for col_name, col_def in pi_missing:
                if col_name not in pi_cols:
                    cursor.execute(f"ALTER TABLE purchase_invoices ADD COLUMN {col_name} {col_def};")

        # 14. purchase_invoice_lines table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchase_invoice_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                purchase_invoice_id INTEGER NOT NULL REFERENCES purchase_invoices(id) ON DELETE CASCADE,
                medicine_id INTEGER NOT NULL REFERENCES medicines(id),
                batch_number TEXT NOT NULL,
                expiry_date TEXT NOT NULL,
                pack_size INTEGER NOT NULL DEFAULT 1 CHECK (pack_size >= 1),
                paid_quantity INTEGER NOT NULL CHECK (paid_quantity >= 0),
                free_quantity INTEGER NOT NULL DEFAULT 0 CHECK (free_quantity >= 0),
                total_received_quantity INTEGER NOT NULL CHECK (total_received_quantity >= 0),
                purchase_rate_paise INTEGER NOT NULL DEFAULT 0 CHECK (purchase_rate_paise >= 0),
                mrp_paise INTEGER NOT NULL DEFAULT 0 CHECK (mrp_paise >= 0),
                discount_paise INTEGER NOT NULL DEFAULT 0 CHECK (discount_paise >= 0),
                gst_percentage REAL NOT NULL DEFAULT 0.0 CHECK (gst_percentage >= 0.0),
                tax_amount_paise INTEGER NOT NULL DEFAULT 0 CHECK (tax_amount_paise >= 0),
                line_total_paise INTEGER NOT NULL DEFAULT 0 CHECK (line_total_paise >= 0),
                created_at TEXT NOT NULL
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_invoice_lines_invoice ON purchase_invoice_lines(purchase_invoice_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_invoice_lines_med_batch ON purchase_invoice_lines(medicine_id, batch_number);")

        # 15. backup_manifests table upgrade & backward compatibility
        if table_exists("backup_manifests"):
            bm_cols = get_columns("backup_manifests")
            if "created_by" not in bm_cols or "filename" not in bm_cols:
                logger.info("Migrating legacy backup_manifests schema...")
                cursor.execute("ALTER TABLE backup_manifests RENAME TO backup_manifests_legacy_v0;")
                cursor.execute("""
                    CREATE TABLE backup_manifests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        filename TEXT UNIQUE NOT NULL,
                        filepath TEXT NOT NULL,
                        file_size_bytes INTEGER NOT NULL CHECK (file_size_bytes >= 0),
                        sha256_hash TEXT NOT NULL,
                        backup_type TEXT NOT NULL DEFAULT 'MANUAL' CHECK (backup_type IN ('MANUAL', 'AUTOMATED', 'PRE_RESTORE_SAFETY')),
                        status TEXT NOT NULL DEFAULT 'VALID' CHECK (status IN ('VALID', 'CORRUPT', 'RESTORED')),
                        schema_version INTEGER NOT NULL DEFAULT 8,
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
                leg_cols = get_columns("backup_manifests_legacy_v0")
                if "archive_filename" in leg_cols:
                    cursor.execute("""
                        INSERT OR IGNORE INTO backup_manifests (
                            filename, filepath, file_size_bytes, sha256_hash,
                            backup_type, status, schema_version,
                            invoice_count, medicine_count, revenue_total_paise,
                            khata_balance_paise, created_at, verified_at
                        )
                        SELECT
                            archive_filename,
                            archive_filename,
                            COALESCE(archive_size_bytes, 0),
                            COALESCE(sha256_hash, ''),
                            'MANUAL',
                            CASE WHEN status = 'VERIFIED' THEN 'VALID' ELSE COALESCE(status, 'VALID') END,
                            8,
                            COALESCE(invoices_count, 0),
                            COALESCE(items_count, 0),
                            CAST(ROUND(COALESCE(total_revenue, 0.0) * 100) AS INTEGER),
                            CAST(ROUND(COALESCE(khata_balance_sum, 0.0) * 100) AS INTEGER),
                            created_at,
                            created_at
                        FROM backup_manifests_legacy_v0;
                    """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backup_manifests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT UNIQUE NOT NULL,
                    filepath TEXT NOT NULL,
                    file_size_bytes INTEGER NOT NULL CHECK (file_size_bytes >= 0),
                    sha256_hash TEXT NOT NULL,
                    backup_type TEXT NOT NULL DEFAULT 'MANUAL' CHECK (backup_type IN ('MANUAL', 'AUTOMATED', 'PRE_RESTORE_SAFETY')),
                    status TEXT NOT NULL DEFAULT 'VALID' CHECK (status IN ('VALID', 'CORRUPT', 'RESTORED')),
                    schema_version INTEGER NOT NULL DEFAULT 8,
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
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_backup_manifests_type ON backup_manifests(backup_type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_backup_manifests_status ON backup_manifests(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_backup_manifests_created ON backup_manifests(created_at);")

        # 16. want_book table
        if table_exists("want_book"):
            wb_cols = get_columns("want_book")
            if "requested_quantity_packs" not in wb_cols:
                cursor.execute("DROP TABLE IF EXISTS want_book;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS want_book (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                medicine_id INTEGER NOT NULL REFERENCES medicines(id),
                requested_quantity_packs INTEGER NOT NULL CHECK (requested_quantity_packs > 0),
                current_stock_units INTEGER NOT NULL DEFAULT 0 CHECK (current_stock_units >= 0),
                min_stock_units INTEGER NOT NULL DEFAULT 0 CHECK (min_stock_units >= 0),
                status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'ORDERED', 'RECEIVED')),
                supplier_id INTEGER REFERENCES suppliers(id),
                notes TEXT,
                requested_by INTEGER REFERENCES users(id),
                ordered_at TEXT,
                received_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_want_book_med ON want_book(medicine_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_want_book_status ON want_book(status);")

        # 17. stock_adjustments table
        if table_exists("stock_adjustments"):
            sa_cols = get_columns("stock_adjustments")
            if "delta_quantity" not in sa_cols:
                cursor.execute("DROP TABLE IF EXISTS stock_adjustments;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_adjustments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                adjustment_number TEXT UNIQUE NOT NULL,
                batch_id INTEGER NOT NULL REFERENCES medicine_batches(id),
                medicine_id INTEGER NOT NULL REFERENCES medicines(id),
                system_quantity INTEGER NOT NULL CHECK (system_quantity >= 0),
                physical_quantity INTEGER NOT NULL CHECK (physical_quantity >= 0),
                delta_quantity INTEGER NOT NULL,
                reason TEXT NOT NULL CHECK (reason IN ('BREAKAGE', 'THEFT', 'AUDIT_CORRECTION', 'EXPIRED_SCRAP')),
                estimated_loss_paise INTEGER NOT NULL DEFAULT 0 CHECK (estimated_loss_paise >= 0),
                notes TEXT,
                user_id INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL,
                CONSTRAINT chk_delta CHECK (delta_quantity = physical_quantity - system_quantity)
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_adjustments_batch ON stock_adjustments(batch_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_adjustments_med ON stock_adjustments(medicine_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_adjustments_created_at ON stock_adjustments(created_at);")

        # 18. wastage_register table
        if table_exists("wastage_register"):
            wr_cols = get_columns("wastage_register")
            if "cost_impact_paise" not in wr_cols or "reference_no" not in wr_cols:
                cursor.execute("DROP TABLE IF EXISTS wastage_register;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wastage_register (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference_no TEXT UNIQUE NOT NULL,
                batch_id INTEGER NOT NULL REFERENCES medicine_batches(id),
                medicine_id INTEGER NOT NULL REFERENCES medicines(id),
                quantity_units INTEGER NOT NULL CHECK (quantity_units > 0),
                reason TEXT NOT NULL CHECK (reason IN ('EXPIRED', 'BREAKAGE', 'DAMAGED', 'WASTAGE', 'OTHER')),
                cost_impact_paise INTEGER NOT NULL CHECK (cost_impact_paise >= 0),
                notes TEXT,
                reference_type TEXT,
                reference_id INTEGER,
                created_by INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wastage_register_batch ON wastage_register(batch_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wastage_register_medicine ON wastage_register(medicine_id);")

        # 19. khata_ledger table
        if table_exists("khata_ledger"):
            kl_cols = get_columns("khata_ledger")
            if "amount_paise" not in kl_cols or "entry_type" not in kl_cols:
                cursor.execute("DROP TABLE IF EXISTS khata_ledger;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS khata_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL REFERENCES customers(id),
                transaction_type TEXT NOT NULL CHECK (transaction_type IN ('SALE_CREDIT', 'PAYMENT', 'RETURN_REFUND', 'ADJUSTMENT')),
                entry_type TEXT NOT NULL CHECK (entry_type IN ('DEBIT', 'CREDIT')),
                amount_paise INTEGER NOT NULL CHECK (amount_paise > 0),
                balance_paise INTEGER NOT NULL,
                payment_mode TEXT CHECK (payment_mode IN ('CASH', 'UPI', 'CARD', 'BANK_TRANSFER', 'CHEQUE')),
                reference_type TEXT NOT NULL,
                reference_id INTEGER,
                receipt_no TEXT,
                notes TEXT,
                user_id INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_khata_ledger_customer ON khata_ledger(customer_id, created_at);")

        # 20. purchase_returns & purchase_return_items tables
        if table_exists("purchase_returns"):
            pr_cols = get_columns("purchase_returns")
            if "total_amount_paise" not in pr_cols:
                cursor.execute("DROP TABLE IF EXISTS purchase_return_items;")
                cursor.execute("DROP TABLE IF EXISTS purchase_returns;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchase_returns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                debit_note_number TEXT UNIQUE NOT NULL,
                purchase_invoice_id INTEGER NOT NULL REFERENCES purchase_invoices(id),
                supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
                subtotal_taxable_paise INTEGER NOT NULL DEFAULT 0 CHECK (subtotal_taxable_paise >= 0),
                total_tax_paise INTEGER NOT NULL DEFAULT 0 CHECK (total_tax_paise >= 0),
                total_amount_paise INTEGER NOT NULL CHECK (total_amount_paise >= 0),
                reason TEXT NOT NULL,
                notes TEXT,
                created_by INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchase_return_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                purchase_return_id INTEGER NOT NULL REFERENCES purchase_returns(id) ON DELETE CASCADE,
                purchase_invoice_line_id INTEGER NOT NULL REFERENCES purchase_invoice_lines(id),
                medicine_id INTEGER NOT NULL REFERENCES medicines(id),
                batch_id INTEGER NOT NULL REFERENCES medicine_batches(id),
                return_packs INTEGER NOT NULL DEFAULT 0 CHECK (return_packs >= 0),
                return_units INTEGER NOT NULL CHECK (return_units > 0),
                purchase_rate_paise INTEGER NOT NULL CHECK (purchase_rate_paise >= 0),
                taxable_amount_paise INTEGER NOT NULL CHECK (taxable_amount_paise >= 0),
                gst_percentage REAL NOT NULL DEFAULT 0.0 CHECK (gst_percentage >= 0.0),
                tax_amount_paise INTEGER NOT NULL DEFAULT 0 CHECK (tax_amount_paise >= 0),
                line_total_paise INTEGER NOT NULL CHECK (line_total_paise >= 0),
                created_at TEXT NOT NULL
            );
        """)

        # 21. sales_returns & sales_return_items tables
        if table_exists("sales_returns"):
            sr_cols = get_columns("sales_returns")
            if "refund_amount_paise" not in sr_cols:
                cursor.execute("DROP TABLE IF EXISTS sales_return_items;")
                cursor.execute("DROP TABLE IF EXISTS sales_returns;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sales_returns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                return_number TEXT UNIQUE NOT NULL,
                sale_invoice_id INTEGER NOT NULL REFERENCES sale_invoices(id),
                customer_id INTEGER REFERENCES customers(id),
                customer_name TEXT,
                refund_mode TEXT NOT NULL CHECK (refund_mode IN ('CASH', 'UPI', 'CARD', 'KHATA', 'STORE_CREDIT')),
                subtotal_taxable_paise INTEGER NOT NULL DEFAULT 0 CHECK (subtotal_taxable_paise >= 0),
                total_cgst_paise INTEGER NOT NULL DEFAULT 0 CHECK (total_cgst_paise >= 0),
                total_sgst_paise INTEGER NOT NULL DEFAULT 0 CHECK (total_sgst_paise >= 0),
                total_igst_paise INTEGER NOT NULL DEFAULT 0 CHECK (total_igst_paise >= 0),
                refund_amount_paise INTEGER NOT NULL CHECK (refund_amount_paise >= 0),
                reason TEXT NOT NULL,
                notes TEXT,
                created_by INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sales_return_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sales_return_id INTEGER NOT NULL REFERENCES sales_returns(id) ON DELETE CASCADE,
                sale_item_id INTEGER NOT NULL REFERENCES sale_items(id),
                medicine_id INTEGER NOT NULL REFERENCES medicines(id),
                batch_id INTEGER NOT NULL REFERENCES medicine_batches(id),
                quantity_units INTEGER NOT NULL CHECK (quantity_units > 0),
                unit_rate_paise INTEGER NOT NULL CHECK (unit_rate_paise >= 0),
                taxable_amount_paise INTEGER NOT NULL CHECK (taxable_amount_paise >= 0),
                gst_rate REAL NOT NULL DEFAULT 0.0 CHECK (gst_rate >= 0.0),
                cgst_amount_paise INTEGER NOT NULL DEFAULT 0 CHECK (cgst_amount_paise >= 0),
                sgst_amount_paise INTEGER NOT NULL DEFAULT 0 CHECK (sgst_amount_paise >= 0),
                total_amount_paise INTEGER NOT NULL CHECK (total_amount_paise >= 0),
                is_resellable INTEGER NOT NULL DEFAULT 1 CHECK (is_resellable IN (0, 1)),
                created_at TEXT NOT NULL
            );
        """)

        # 22. sale_payments and schedule_h1_records columns
        if table_exists("sale_payments"):
            sp_cols = get_columns("sale_payments")
            if "reference_note" not in sp_cols:
                cursor.execute("ALTER TABLE sale_payments ADD COLUMN reference_note TEXT;")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schedule_h1_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_item_id INTEGER UNIQUE NOT NULL REFERENCES sale_items(id) ON DELETE CASCADE,
                patient_name TEXT NOT NULL,
                patient_address TEXT NOT NULL,
                doctor_name TEXT NOT NULL,
                doctor_address TEXT,
                medicine_name TEXT NOT NULL,
                batch_number TEXT NOT NULL,
                quantity_units INTEGER NOT NULL CHECK (quantity_units > 0),
                dispensed_date TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        if table_exists("schedule_h1_records"):
            sh1_cols = get_columns("schedule_h1_records")
            if "created_at" not in sh1_cols:
                cursor.execute(f"ALTER TABLE schedule_h1_records ADD COLUMN created_at TEXT NOT NULL DEFAULT '{now_str}';")

        conn.commit()
        cursor.close()

    def get_connection(self) -> sqlite3.Connection:
        """Create and return an active connection with enforced WAL pragmas."""
        return create_connection(self.db_path)

    def get_health(self) -> Dict[str, Any]:
        """Perform real-time engine health and integrity check."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("PRAGMA journal_mode;")
            journal_mode = cursor.fetchone()[0]

            cursor.execute("PRAGMA synchronous;")
            synchronous = cursor.fetchone()[0]

            cursor.execute("PRAGMA foreign_keys;")
            foreign_keys = bool(cursor.fetchone()[0])

            cursor.execute("PRAGMA integrity_check;")
            integrity_row = cursor.fetchone()
            integrity = integrity_row[0] if integrity_row else "UNKNOWN"

            applied = get_applied_versions(conn)
            schema_version = max(applied) if applied else 0

            cursor.close()
            conn.close()

            db_size_kb = (
                round(self.db_path.stat().st_size / 1024, 2)
                if self.db_path.exists()
                else 0.0
            )
            wal_file = self.db_path.with_name(self.db_path.name + "-wal")
            wal_size_kb = (
                round(wal_file.stat().st_size / 1024, 2)
                if wal_file.exists()
                else 0.0
            )

            is_healthy = integrity.upper() == "OK"

            return {
                "status": "HEALTHY" if is_healthy else "DEGRADED",
                "journal_mode": journal_mode.upper(),
                "synchronous": synchronous,
                "foreign_keys": foreign_keys,
                "integrity": integrity,
                "schema_version": schema_version,
                "path": str(self.db_path),
                "size_kb": db_size_kb,
                "wal_size_kb": wal_size_kb,
            }
        except Exception as e:
            logger.error("Database health check failed: %s", e)
            return {
                "status": "UNHEALTHY",
                "path": str(self.db_path),
                "error": str(e),
            }
