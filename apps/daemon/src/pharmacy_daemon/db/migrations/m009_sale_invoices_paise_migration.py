"""Migration 009: Migrate sale_invoices and sale_items to integer paise schema.

Rebuilds legacy sale_invoices and sale_items tables to the canonical schema,
mapping legacy REAL monetary columns to INTEGER paise while preserving all existing
invoices, lines, payments, and relations.
"""

from datetime import datetime, timezone
import logging
import sqlite3

logger = logging.getLogger("pharmacy_daemon.db.migrations.m009")

VERSION = 9
NAME = "009_sale_invoices_paise_migration"


def _table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?;", (table_name,))
    return cursor.fetchone() is not None


def _get_columns(cursor: sqlite3.Cursor, table_name: str) -> set[str]:
    cursor.execute(f"PRAGMA table_info({table_name});")
    return {row[1] for row in cursor.fetchall()}


def apply_migration(conn: sqlite3.Connection) -> None:
    """Safely migrate sale_invoices and sale_items to integer paise schema."""
    cursor = conn.cursor()
    now_str = datetime.now(timezone.utc).isoformat()

    fk_orig = 1
    try:
        cursor.execute("PRAGMA foreign_keys;")
        row = cursor.fetchone()
        fk_orig = row[0] if row else 1
        cursor.execute("PRAGMA foreign_keys = OFF;")
    except Exception:
        pass

    try:
        # -------------------------------------------------------------
        # 1. sale_invoices table migration
        # -------------------------------------------------------------
        if _table_exists(cursor, "sale_invoices"):
            si_cols = _get_columns(cursor, "sale_invoices")
            legacy_si_fields = {
                "subtotal_taxable",
                "total_cgst",
                "total_sgst",
                "total_igst",
                "round_off",
                "grand_total",
            }

            needs_migration = bool(legacy_si_fields.intersection(si_cols)) or ("subtotal_taxable_paise" not in si_cols)

            if needs_migration:
                logger.info("Rebuilding legacy sale_invoices table to integer-paise schema...")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sale_invoices_migrated (
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

                def _expr(paise_col: str, real_col: str, default: str = "0") -> str:
                    has_paise = paise_col in si_cols
                    has_real = real_col in si_cols
                    if has_paise and has_real:
                        return f"CASE WHEN COALESCE({paise_col}, 0) != 0 THEN {paise_col} WHEN {real_col} IS NOT NULL THEN CAST(ROUND(COALESCE({real_col}, 0.0) * 100) AS INTEGER) ELSE {default} END"
                    elif has_paise:
                        return f"COALESCE({paise_col}, {default})"
                    elif has_real:
                        return f"CAST(ROUND(COALESCE({real_col}, 0.0) * 100) AS INTEGER)"
                    else:
                        return default

                seq_expr = "COALESCE(sequence_number, id)" if "sequence_number" in si_cols else "id"
                cust_id_expr = "customer_id" if "customer_id" in si_cols else "NULL"
                cust_name_expr = "customer_name" if "customer_name" in si_cols else "NULL"
                cust_phone_expr = "customer_phone" if "customer_phone" in si_cols else "NULL"
                cust_gstin_expr = "customer_gstin" if "customer_gstin" in si_cols else "NULL"
                doc_name_expr = "doctor_name" if "doctor_name" in si_cols else "NULL"
                doc_addr_expr = "doctor_address" if "doctor_address" in si_cols else "NULL"

                subtotal_expr = _expr("subtotal_taxable_paise", "subtotal_taxable")
                cgst_expr = _expr("total_cgst_paise", "total_cgst")
                sgst_expr = _expr("total_sgst_paise", "total_sgst")
                igst_expr = _expr("total_igst_paise", "total_igst")
                discount_expr = _expr("discount_paise", "discount")
                round_off_expr = _expr("round_off_paise", "round_off")
                grand_total_expr = _expr("grand_total_paise", "grand_total")
                cash_tendered_expr = _expr("cash_tendered_paise", "cash_tendered")
                change_returned_expr = _expr("change_returned_paise", "change_returned")

                payment_mode_expr = "COALESCE(payment_mode, 'CASH')" if "payment_mode" in si_cols else "'CASH'"
                status_expr = "COALESCE(status, 'COMPLETED')" if "status" in si_cols else "'COMPLETED'"
                notes_expr = "notes" if "notes" in si_cols else "NULL"
                created_by_expr = "created_by" if "created_by" in si_cols else "NULL"
                created_at_expr = "created_at" if "created_at" in si_cols else f"'{now_str}'"
                updated_at_expr = f"COALESCE(updated_at, {created_at_expr})" if "updated_at" in si_cols else created_at_expr

                cursor.execute(f"""
                    INSERT INTO sale_invoices_migrated (
                        id, invoice_no, fiscal_year, sequence_number, customer_id,
                        customer_name, customer_phone, customer_gstin, doctor_name, doctor_address,
                        subtotal_taxable_paise, total_cgst_paise, total_sgst_paise, total_igst_paise,
                        discount_paise, round_off_paise, grand_total_paise, payment_mode,
                        cash_tendered_paise, change_returned_paise, status, notes,
                        created_by, created_at, updated_at
                    )
                    SELECT
                        id,
                        invoice_no,
                        fiscal_year,
                        {seq_expr},
                        {cust_id_expr},
                        {cust_name_expr},
                        {cust_phone_expr},
                        {cust_gstin_expr},
                        {doc_name_expr},
                        {doc_addr_expr},
                        {subtotal_expr},
                        {cgst_expr},
                        {sgst_expr},
                        {igst_expr},
                        {discount_expr},
                        {round_off_expr},
                        {grand_total_expr},
                        {payment_mode_expr},
                        {cash_tendered_expr},
                        {change_returned_expr},
                        {status_expr},
                        {notes_expr},
                        {created_by_expr},
                        {created_at_expr},
                        {updated_at_expr}
                    FROM sale_invoices;
                """)

                cursor.execute("DROP TABLE sale_invoices;")
                cursor.execute("ALTER TABLE sale_invoices_migrated RENAME TO sale_invoices;")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sale_invoices_invoice_no ON sale_invoices(invoice_no);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sale_invoices_created_at ON sale_invoices(created_at);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sale_invoices_customer_id ON sale_invoices(customer_id);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sale_invoices_gstin ON sale_invoices(customer_gstin);")
                logger.info("sale_invoices table migrated successfully.")

        # -------------------------------------------------------------
        # 2. sale_items table migration
        # -------------------------------------------------------------
        if _table_exists(cursor, "sale_items"):
            sit_cols = _get_columns(cursor, "sale_items")
            legacy_sit_fields = {
                "unit_mrp",
                "unit_rate",
                "taxable_amount",
                "cgst_amount",
                "sgst_amount",
                "total_amount",
            }

            needs_sit_migration = bool(legacy_sit_fields.intersection(sit_cols)) or ("unit_mrp_paise" not in sit_cols)

            if needs_sit_migration:
                logger.info("Rebuilding legacy sale_items table to integer-paise schema...")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sale_items_migrated (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sale_invoice_id INTEGER NOT NULL REFERENCES sale_invoices(id) ON DELETE CASCADE,
                        medicine_id INTEGER NOT NULL,
                        batch_id INTEGER NOT NULL,
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

                def _sit_expr(paise_col: str, real_col: str, default: str = "0") -> str:
                    has_paise = paise_col in sit_cols
                    has_real = real_col in sit_cols
                    if has_paise and has_real:
                        return f"CASE WHEN COALESCE({paise_col}, 0) != 0 THEN {paise_col} WHEN {real_col} IS NOT NULL THEN CAST(ROUND(COALESCE({real_col}, 0.0) * 100) AS INTEGER) ELSE {default} END"
                    elif has_paise:
                        return f"COALESCE({paise_col}, {default})"
                    elif has_real:
                        return f"CAST(ROUND(COALESCE({real_col}, 0.0) * 100) AS INTEGER)"
                    else:
                        return default

                has_med_batches = _table_exists(cursor, "medicine_batches")
                med_batches_tbl = "medicine_batches" if has_med_batches else ("batches" if _table_exists(cursor, "batches") else None)

                if "medicine_id" in sit_cols:
                    if med_batches_tbl:
                        med_id_expr = f"COALESCE(medicine_id, (SELECT medicine_id FROM {med_batches_tbl} WHERE id = sale_items.batch_id), 1)"
                    else:
                        med_id_expr = "COALESCE(medicine_id, 1)"
                else:
                    if med_batches_tbl:
                        med_id_expr = f"COALESCE((SELECT medicine_id FROM {med_batches_tbl} WHERE id = sale_items.batch_id), 1)"
                    else:
                        med_id_expr = "1"

                mrp_expr = _sit_expr("unit_mrp_paise", "unit_mrp")
                rate_expr = _sit_expr("unit_rate_paise", "unit_rate")
                disc_pct_expr = "COALESCE(discount_percent, 0.0)" if "discount_percent" in sit_cols else "0.0"
                taxable_expr = _sit_expr("taxable_amount_paise", "taxable_amount")
                gst_rate_expr = "COALESCE(gst_rate, 0.0)" if "gst_rate" in sit_cols else "0.0"
                cgst_expr = _sit_expr("cgst_amount_paise", "cgst_amount")
                sgst_expr = _sit_expr("sgst_amount_paise", "sgst_amount")
                total_expr = _sit_expr("total_amount_paise", "total_amount")
                created_at_expr = "created_at" if "created_at" in sit_cols else f"'{now_str}'"

                cursor.execute(f"""
                    INSERT INTO sale_items_migrated (
                        id, sale_invoice_id, medicine_id, batch_id, quantity_units,
                        unit_mrp_paise, unit_rate_paise, discount_percent, taxable_amount_paise,
                        gst_rate, cgst_amount_paise, sgst_amount_paise, total_amount_paise, created_at
                    )
                    SELECT
                        id,
                        sale_invoice_id,
                        {med_id_expr},
                        batch_id,
                        quantity_units,
                        {mrp_expr},
                        {rate_expr},
                        {disc_pct_expr},
                        {taxable_expr},
                        {gst_rate_expr},
                        {cgst_expr},
                        {sgst_expr},
                        {total_expr},
                        {created_at_expr}
                    FROM sale_items;
                """)

                cursor.execute("DROP TABLE sale_items;")
                cursor.execute("ALTER TABLE sale_items_migrated RENAME TO sale_items;")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sale_items_invoice_id ON sale_items(sale_invoice_id);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sale_items_batch_id ON sale_items(batch_id);")
                logger.info("sale_items table migrated successfully.")

    finally:
        if fk_orig:
            try:
                cursor.execute("PRAGMA foreign_keys = ON;")
            except Exception:
                pass


def apply(conn: sqlite3.Connection) -> None:
    """Entry point for migration runner."""
    apply_migration(conn)
