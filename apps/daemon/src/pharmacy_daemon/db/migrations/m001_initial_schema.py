"""Migration 001: Foundational schema.

Tables:
- schema_migrations
- system_settings
- users
- manufacturers
- suppliers
- medicines
- customers
- fts_medicines (SQLite FTS5 virtual table + triggers)
"""

import sqlite3

VERSION = 1
NAME = "001_initial_schema"

UP_SQL = """
-- Schema migration tracker
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

-- Store metadata & key-value configuration
CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- User accounts and role-based permissions
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
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- Pharmaceutical manufacturers
CREATE TABLE IF NOT EXISTS manufacturers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    short_code TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_manufacturers_name ON manufacturers(name);

-- Stockists / Suppliers / Distributors
CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    gstin TEXT,
    dl_number_20b TEXT,
    dl_number_21b TEXT,
    phone TEXT,
    email TEXT,
    address TEXT,
    credit_days INTEGER NOT NULL DEFAULT 21,
    current_payable REAL NOT NULL DEFAULT 0.0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_suppliers_name ON suppliers(name);

-- Medicine master catalog
CREATE TABLE IF NOT EXISTS medicines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_name TEXT NOT NULL,
    generic_salt TEXT NOT NULL,
    dosage_form TEXT NOT NULL,
    pack_size INTEGER NOT NULL DEFAULT 1,
    manufacturer_id INTEGER REFERENCES manufacturers(id) ON DELETE SET NULL,
    hsn_code TEXT NOT NULL DEFAULT '3004',
    gst_rate REAL NOT NULL DEFAULT 12.0,
    is_schedule_h1 INTEGER NOT NULL DEFAULT 0,
    is_schedule_h INTEGER NOT NULL DEFAULT 1,
    is_narcotic INTEGER NOT NULL DEFAULT 0,
    min_stock_units INTEGER NOT NULL DEFAULT 10,
    rack_location TEXT,
    barcode TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_medicines_search ON medicines(brand_name, generic_salt);
CREATE INDEX IF NOT EXISTS idx_medicines_barcode ON medicines(barcode);

-- Customers and Patient Profiles
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT,
    address TEXT,
    default_doctor TEXT,
    credit_limit REAL NOT NULL DEFAULT 5000.0,
    current_balance REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);
CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name);

-- SQLite FTS5 Full-Text Search virtual table for medicines
CREATE VIRTUAL TABLE IF NOT EXISTS fts_medicines USING fts5(
    brand_name,
    generic_salt,
    content='medicines',
    content_rowid='id'
);

-- Auto-synchronization triggers for FTS5
CREATE TRIGGER IF NOT EXISTS trg_medicines_ai AFTER INSERT ON medicines BEGIN
    INSERT INTO fts_medicines(rowid, brand_name, generic_salt)
    VALUES (new.id, new.brand_name, new.generic_salt);
END;

CREATE TRIGGER IF NOT EXISTS trg_medicines_ad AFTER DELETE ON medicines BEGIN
    INSERT INTO fts_medicines(fts_medicines, rowid, brand_name, generic_salt)
    VALUES('delete', old.id, old.brand_name, old.generic_salt);
END;

CREATE TRIGGER IF NOT EXISTS trg_medicines_au AFTER UPDATE ON medicines BEGIN
    INSERT INTO fts_medicines(fts_medicines, rowid, brand_name, generic_salt)
    VALUES('delete', old.id, old.brand_name, old.generic_salt);
    INSERT INTO fts_medicines(rowid, brand_name, generic_salt)
    VALUES (new.id, new.brand_name, new.generic_salt);
END;
"""


def apply(conn: sqlite3.Connection) -> None:
    """Execute migration DDL inside connection."""
    conn.executescript(UP_SQL)
