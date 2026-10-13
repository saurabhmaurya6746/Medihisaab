"""Migration 006: Stock adjustments, Want-Book, and expiry audit support.

Tables introduced:
- stock_adjustments: Append-only audit record of physical count adjustments with variance tracking and monetary loss estimation in paise.
- want_book: Reorder book and low-stock procurement workflow tracking (PENDING, ORDERED, RECEIVED).
"""

import sqlite3

VERSION = 6
NAME = "006_inventory_expiry_and_want_book"


def apply(conn: sqlite3.Connection) -> None:
    """Apply schema changes introducing stock adjustments, want-book, and expiry indices."""
    cursor = conn.cursor()

    # 1. stock_adjustments (physical audit discrepancies and scrap)
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

    # 2. want_book (procurement reorder ledger)
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

    # Indexes for stock_adjustments
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_adjustments_batch ON stock_adjustments(batch_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_adjustments_med ON stock_adjustments(medicine_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_adjustments_created_at ON stock_adjustments(created_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_adjustments_reason ON stock_adjustments(reason);")

    # Indexes for want_book
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_want_book_med ON want_book(medicine_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_want_book_status ON want_book(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_want_book_supplier ON want_book(supplier_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_want_book_created_at ON want_book(created_at);")

    # Composite performance indexes for expiry queries and low-stock detection
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_medicine_batches_active_stock_expiry ON medicine_batches(is_active, current_quantity, expiry_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_medicines_active_min_stock ON medicines(is_active, min_stock_units);")

    cursor.close()
