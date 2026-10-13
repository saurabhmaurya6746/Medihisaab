"""Migration 003: Purchase inwarding, medicine batches, inventory ledger, and supplier payable accruals."""

import sqlite3

VERSION = 3
NAME = "003_purchases_inventory_and_batches"


def apply(conn: sqlite3.Connection) -> None:
    """Apply schema changes introducing purchases, batches, inventory ledger, and payables."""
    cursor = conn.cursor()

    # 1. purchase_invoices
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS purchase_invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
            supplier_invoice_number TEXT NOT NULL,
            invoice_date TEXT NOT NULL,
            entry_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'POSTED', 'CANCELLED')),
            subtotal REAL NOT NULL DEFAULT 0.0,
            discount REAL NOT NULL DEFAULT 0.0,
            tax_amount REAL NOT NULL DEFAULT 0.0,
            grand_total REAL NOT NULL DEFAULT 0.0,
            payment_status TEXT NOT NULL DEFAULT 'UNPAID' CHECK (payment_status IN ('PAID', 'UNPAID', 'PARTIAL')),
            notes TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL,
            posted_at TEXT,
            updated_at TEXT NOT NULL,
            CONSTRAINT uq_supplier_invoice UNIQUE (supplier_id, supplier_invoice_number)
        );
    """)

    # 2. purchase_invoice_lines
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
            purchase_rate REAL NOT NULL CHECK (purchase_rate >= 0.0),
            mrp REAL NOT NULL CHECK (mrp >= 0.0),
            discount REAL NOT NULL DEFAULT 0.0 CHECK (discount >= 0.0),
            gst_percentage REAL NOT NULL DEFAULT 0.0 CHECK (gst_percentage >= 0.0),
            tax_amount REAL NOT NULL DEFAULT 0.0,
            line_total REAL NOT NULL CHECK (line_total >= 0.0),
            created_at TEXT NOT NULL
        );
    """)

    # 3. medicine_batches (integer base units for current_quantity, non-negative constraint)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS medicine_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_id INTEGER NOT NULL REFERENCES medicines(id),
            batch_number TEXT NOT NULL,
            expiry_date TEXT NOT NULL,
            mrp REAL NOT NULL CHECK (mrp >= 0.0),
            purchase_rate REAL NOT NULL CHECK (purchase_rate >= 0.0),
            pack_size INTEGER NOT NULL DEFAULT 1 CHECK (pack_size >= 1),
            current_quantity INTEGER NOT NULL DEFAULT 0 CHECK (current_quantity >= 0),
            reserved_quantity INTEGER NOT NULL DEFAULT 0 CHECK (reserved_quantity >= 0),
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            CONSTRAINT uq_medicine_batch UNIQUE (medicine_id, batch_number)
        );
    """)

    # 4. inventory_ledger
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_id INTEGER NOT NULL REFERENCES medicines(id),
            batch_id INTEGER NOT NULL REFERENCES medicine_batches(id),
            transaction_type TEXT NOT NULL CHECK (transaction_type IN ('PURCHASE_INWARD', 'SALE_DISPENSE', 'ADJUSTMENT', 'PURCHASE_RETURN', 'SALE_RETURN')),
            quantity_change INTEGER NOT NULL,
            quantity_balance INTEGER NOT NULL CHECK (quantity_balance >= 0),
            reference_type TEXT NOT NULL,
            reference_id INTEGER,
            notes TEXT,
            user_id INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL
        );
    """)

    # 5. supplier_payable_ledger
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS supplier_payable_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
            reference_type TEXT NOT NULL DEFAULT 'PURCHASE_INVOICE',
            reference_id INTEGER,
            entry_type TEXT NOT NULL CHECK (entry_type IN ('DEBIT', 'CREDIT')),
            amount REAL NOT NULL CHECK (amount >= 0.0),
            balance REAL NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL
        );
    """)

    # 6. Performance and FEFO Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_invoices_supplier ON purchase_invoices(supplier_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_invoices_status ON purchase_invoices(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_invoices_date ON purchase_invoices(invoice_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_invoice_lines_invoice ON purchase_invoice_lines(purchase_invoice_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_invoice_lines_medicine ON purchase_invoice_lines(medicine_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_medicine_batches_med_batch ON medicine_batches(medicine_id, batch_number);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_medicine_batches_fefo ON medicine_batches(medicine_id, is_active, current_quantity, expiry_date ASC);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_medicine_batches_expiry ON medicine_batches(expiry_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventory_ledger_med ON inventory_ledger(medicine_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventory_ledger_batch ON inventory_ledger(batch_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventory_ledger_ref ON inventory_ledger(reference_type, reference_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_supplier_payable_ledger_supplier ON supplier_payable_ledger(supplier_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_supplier_payable_ledger_ref ON supplier_payable_ledger(reference_type, reference_id);")

    cursor.close()
