"""Migration 002: Master catalog enhancements and unique indices.

Enhancements:
- customers: add is_active and updated_at
- manufacturers: add is_active and updated_at, unique index on short_code
- medicines: add medicine_code and strength, unique index on medicine_code and barcode
- suppliers: unique partial indices on gstin, dl_number_20b, dl_number_21b
- fts_medicines: upgraded to index brand_name, generic_salt, medicine_code, and barcode
"""

import sqlite3

VERSION = 2
NAME = "002_master_catalog_enhancements"

UP_SQL = """
-- 1. Customers: active tracking and timestamp
ALTER TABLE customers ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1;
ALTER TABLE customers ADD COLUMN updated_at TEXT;

-- 2. Manufacturers: active tracking and timestamp
ALTER TABLE manufacturers ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1;
ALTER TABLE manufacturers ADD COLUMN updated_at TEXT;

-- Unique partial index on manufacturer short_code
CREATE UNIQUE INDEX IF NOT EXISTS uq_manufacturers_short_code 
ON manufacturers(short_code) 
WHERE short_code IS NOT NULL AND short_code != '';

-- 3. Medicines: item code/SKU and strength specifications
ALTER TABLE medicines ADD COLUMN medicine_code TEXT;
ALTER TABLE medicines ADD COLUMN strength TEXT;

-- Unique partial indices for medicine_code and barcode
CREATE UNIQUE INDEX IF NOT EXISTS uq_medicines_code 
ON medicines(medicine_code) 
WHERE medicine_code IS NOT NULL AND medicine_code != '';

CREATE UNIQUE INDEX IF NOT EXISTS uq_medicines_barcode 
ON medicines(barcode) 
WHERE barcode IS NOT NULL AND barcode != '';

-- 4. Suppliers: Unique partial indices for statutory compliance
CREATE UNIQUE INDEX IF NOT EXISTS uq_suppliers_gstin 
ON suppliers(gstin) 
WHERE gstin IS NOT NULL AND gstin != '';

CREATE UNIQUE INDEX IF NOT EXISTS uq_suppliers_dl_20b 
ON suppliers(dl_number_20b) 
WHERE dl_number_20b IS NOT NULL AND dl_number_20b != '';

CREATE UNIQUE INDEX IF NOT EXISTS uq_suppliers_dl_21b 
ON suppliers(dl_number_21b) 
WHERE dl_number_21b IS NOT NULL AND dl_number_21b != '';

-- 5. Upgrade FTS5 virtual table and synchronization triggers
DROP TRIGGER IF EXISTS trg_medicines_ai;
DROP TRIGGER IF EXISTS trg_medicines_ad;
DROP TRIGGER IF EXISTS trg_medicines_au;
DROP TABLE IF EXISTS fts_medicines;

CREATE VIRTUAL TABLE IF NOT EXISTS fts_medicines USING fts5(
    brand_name,
    generic_salt,
    medicine_code,
    barcode,
    content='medicines',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS trg_medicines_ai AFTER INSERT ON medicines BEGIN
    INSERT INTO fts_medicines(rowid, brand_name, generic_salt, medicine_code, barcode)
    VALUES (new.id, new.brand_name, new.generic_salt, new.medicine_code, new.barcode);
END;

CREATE TRIGGER IF NOT EXISTS trg_medicines_ad AFTER DELETE ON medicines BEGIN
    INSERT INTO fts_medicines(fts_medicines, rowid, brand_name, generic_salt, medicine_code, barcode)
    VALUES('delete', old.id, old.brand_name, old.generic_salt, old.medicine_code, old.barcode);
END;

CREATE TRIGGER IF NOT EXISTS trg_medicines_au AFTER UPDATE ON medicines BEGIN
    INSERT INTO fts_medicines(fts_medicines, rowid, brand_name, generic_salt, medicine_code, barcode)
    VALUES('delete', old.id, old.brand_name, old.generic_salt, old.medicine_code, old.barcode);
    INSERT INTO fts_medicines(rowid, brand_name, generic_salt, medicine_code, barcode)
    VALUES (new.id, new.brand_name, new.generic_salt, new.medicine_code, new.barcode);
END;

-- Populate existing medicines into newly structured FTS5 table
INSERT INTO fts_medicines(rowid, brand_name, generic_salt, medicine_code, barcode)
SELECT id, brand_name, generic_salt, medicine_code, barcode FROM medicines;
"""


def apply(conn: sqlite3.Connection) -> None:
    """Execute migration 002 DDL."""
    conn.executescript(UP_SQL)
