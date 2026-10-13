"""Migration 005: Sales invoices, sale line items, Schedule H1 register, split payment allocations, and held bills.

All monetary values are strictly modeled using integer paise.
"""

import sqlite3

VERSION = 5
NAME = "005_sales_pos_and_compliance"


def apply(conn: sqlite3.Connection) -> None:
    """Apply schema changes introducing sales billing, Schedule H1, split payments, and held bills."""
    cursor = conn.cursor()

    # 1. sale_invoices (consecutive sequence by fiscal year, all money in paise)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sale_invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_no TEXT UNIQUE NOT NULL,
            fiscal_year TEXT NOT NULL,
            sequence_number INTEGER NOT NULL DEFAULT 1,
            customer_id INTEGER REFERENCES customers(id),
            customer_name TEXT,
            customer_phone TEXT,
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

    # 2. sale_items (fundamental units, pro-rata paise amounts)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sale_items (
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

    # 3. schedule_h1_records (immutable statutory dispensing register)
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

    # 4. sale_payments (payment ledger supporting split tender)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sale_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_invoice_id INTEGER NOT NULL REFERENCES sale_invoices(id) ON DELETE CASCADE,
            payment_mode TEXT NOT NULL CHECK (payment_mode IN ('CASH', 'UPI', 'CARD', 'KHATA')),
            amount_paise INTEGER NOT NULL CHECK (amount_paise > 0),
            reference_note TEXT,
            created_at TEXT NOT NULL
        );
    """)

    # 5. held_bills (parked counter transactions)
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
            subtotal_paise INTEGER NOT NULL DEFAULT 0 CHECK (subtotal_paise >= 0),
            total_tax_paise INTEGER NOT NULL DEFAULT 0 CHECK (total_tax_paise >= 0),
            grand_total_paise INTEGER NOT NULL DEFAULT 0 CHECK (grand_total_paise >= 0),
            notes TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)

    # Indexes for fast lookup and sequential counter queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sale_invoices_invoice_no ON sale_invoices(invoice_no);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sale_invoices_created_at ON sale_invoices(created_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sale_invoices_customer_id ON sale_invoices(customer_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sale_items_invoice_id ON sale_items(sale_invoice_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sale_items_batch_id ON sale_items(batch_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_schedule_h1_records_dispensed_date ON schedule_h1_records(dispensed_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sale_payments_invoice_id ON sale_payments(sale_invoice_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_held_bills_created_at ON held_bills(created_at);")

    cursor.close()
