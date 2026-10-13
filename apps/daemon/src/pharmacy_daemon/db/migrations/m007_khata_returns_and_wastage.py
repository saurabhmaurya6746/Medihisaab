"""Migration 007: Customer Khata ledger, Sales Returns (Credit Notes), Purchase Returns (Debit Notes), and Wastage Register.

All monetary amounts are strictly modeled using integer paise.
"""

import sqlite3

VERSION = 7
NAME = "007_khata_returns_and_wastage"


def apply(conn: sqlite3.Connection) -> None:
    """Apply schema changes introducing Customer Khata, Sales Returns, Purchase Returns, and Wastage Register."""
    cursor = conn.cursor()

    # 1. khata_ledger (Append-only double-entry customer credit ledger)
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

    # 2. sales_returns (Customer sales credit notes)
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

    # 3. sales_return_items (Line item details of customer sales returns)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales_return_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sales_return_id INTEGER NOT NULL REFERENCES sales_returns(id) ON DELETE CASCADE,
            sale_item_id INTEGER NOT NULL REFERENCES sale_items(id),
            medicine_id INTEGER NOT NULL REFERENCES medicines(id),
            batch_id INTEGER NOT NULL REFERENCES medicine_batches(id),
            quantity_units INTEGER NOT NULL CHECK (quantity_units > 0),
            unit_rate_paise INTEGER NOT NULL CHECK (unit_rate_paise >= 0),
            taxable_amount_paise INTEGER NOT NULL DEFAULT 0 CHECK (taxable_amount_paise >= 0),
            gst_rate REAL NOT NULL DEFAULT 0.0 CHECK (gst_rate >= 0.0),
            cgst_amount_paise INTEGER NOT NULL DEFAULT 0 CHECK (cgst_amount_paise >= 0),
            sgst_amount_paise INTEGER NOT NULL DEFAULT 0 CHECK (sgst_amount_paise >= 0),
            total_amount_paise INTEGER NOT NULL CHECK (total_amount_paise >= 0),
            is_resellable INTEGER NOT NULL DEFAULT 1 CHECK (is_resellable IN (0, 1)),
            created_at TEXT NOT NULL
        );
    """)

    # 4. purchase_returns (Distributor debit notes)
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

    # 5. purchase_return_items (Line item details of distributor debit notes)
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
            taxable_amount_paise INTEGER NOT NULL DEFAULT 0 CHECK (taxable_amount_paise >= 0),
            gst_percentage REAL NOT NULL DEFAULT 0.0 CHECK (gst_percentage >= 0.0),
            tax_amount_paise INTEGER NOT NULL DEFAULT 0 CHECK (tax_amount_paise >= 0),
            line_total_paise INTEGER NOT NULL CHECK (line_total_paise >= 0),
            created_at TEXT NOT NULL
        );
    """)

    # 6. wastage_register (Wastage, damage, breakage, and expired stock write-offs)
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

    # 7. Indexes for performant lookups and foreign key joins
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_khata_ledger_customer ON khata_ledger(customer_id, created_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_khata_ledger_ref ON khata_ledger(reference_type, reference_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_khata_ledger_receipt ON khata_ledger(receipt_no);")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_returns_invoice ON sales_returns(sale_invoice_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_returns_customer ON sales_returns(customer_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_return_items_return ON sales_return_items(sales_return_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_return_items_sale_item ON sales_return_items(sale_item_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_return_items_batch ON sales_return_items(batch_id);")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_returns_invoice ON purchase_returns(purchase_invoice_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_returns_supplier ON purchase_returns(supplier_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_return_items_return ON purchase_return_items(purchase_return_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_return_items_line ON purchase_return_items(purchase_invoice_line_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_return_items_batch ON purchase_return_items(batch_id);")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_wastage_register_batch ON wastage_register(batch_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_wastage_register_medicine ON wastage_register(medicine_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_wastage_register_reason ON wastage_register(reason);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_wastage_register_created_at ON wastage_register(created_at);")

    cursor.close()
