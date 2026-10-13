"""Migration 004: Monetary data hardening - migrate SQLite REAL columns to integer paise.

Audited and migrated tables/columns:
- suppliers: current_payable -> current_payable_paise
- customers: credit_limit -> credit_limit_paise, current_balance -> current_balance_paise
- purchase_invoices: subtotal -> subtotal_paise, discount -> discount_paise, tax_amount -> tax_amount_paise, grand_total -> grand_total_paise
- purchase_invoice_lines: purchase_rate -> purchase_rate_paise, mrp -> mrp_paise, discount -> discount_paise, tax_amount -> tax_amount_paise, line_total -> line_total_paise
- medicine_batches: mrp -> mrp_paise, purchase_rate -> purchase_rate_paise
- supplier_payable_ledger: amount -> amount_paise, balance -> balance_paise
"""

import sqlite3

VERSION = 4
NAME = "004_monetary_paise_hardening"


def _get_columns(cursor: sqlite3.Cursor, table_name: str) -> set[str]:
    cursor.execute(f"PRAGMA table_info({table_name});")
    return {row[1] for row in cursor.fetchall()}


def apply(conn: sqlite3.Connection) -> None:
    """Migrate monetary columns from REAL to INTEGER paise and drop deprecated REAL columns."""
    cursor = conn.cursor()

    # 1. suppliers: current_payable -> current_payable_paise
    cols = _get_columns(cursor, "suppliers")
    if "current_payable_paise" not in cols:
        cursor.execute("ALTER TABLE suppliers ADD COLUMN current_payable_paise INTEGER NOT NULL DEFAULT 0 CHECK (current_payable_paise >= 0);")
    if "current_payable" in cols:
        cursor.execute("UPDATE suppliers SET current_payable_paise = CAST(ROUND(COALESCE(current_payable, 0.0) * 100) AS INTEGER);")
        cursor.execute("ALTER TABLE suppliers DROP COLUMN current_payable;")

    # 2. customers: credit_limit -> credit_limit_paise, current_balance -> current_balance_paise
    cols = _get_columns(cursor, "customers")
    if "credit_limit_paise" not in cols:
        cursor.execute("ALTER TABLE customers ADD COLUMN credit_limit_paise INTEGER NOT NULL DEFAULT 500000 CHECK (credit_limit_paise >= 0);")
    if "credit_limit" in cols:
        cursor.execute("UPDATE customers SET credit_limit_paise = CAST(ROUND(COALESCE(credit_limit, 5000.0) * 100) AS INTEGER);")
        cursor.execute("ALTER TABLE customers DROP COLUMN credit_limit;")

    cols = _get_columns(cursor, "customers")
    if "current_balance_paise" not in cols:
        cursor.execute("ALTER TABLE customers ADD COLUMN current_balance_paise INTEGER NOT NULL DEFAULT 0;")
    if "current_balance" in cols:
        cursor.execute("UPDATE customers SET current_balance_paise = CAST(ROUND(COALESCE(current_balance, 0.0) * 100) AS INTEGER);")
        cursor.execute("ALTER TABLE customers DROP COLUMN current_balance;")

    # 3. purchase_invoices: subtotal, discount, tax_amount, grand_total -> *_paise
    cols = _get_columns(cursor, "purchase_invoices")
    if "subtotal_paise" not in cols:
        cursor.execute("ALTER TABLE purchase_invoices ADD COLUMN subtotal_paise INTEGER NOT NULL DEFAULT 0 CHECK (subtotal_paise >= 0);")
    if "discount_paise" not in cols:
        cursor.execute("ALTER TABLE purchase_invoices ADD COLUMN discount_paise INTEGER NOT NULL DEFAULT 0 CHECK (discount_paise >= 0);")
    if "tax_amount_paise" not in cols:
        cursor.execute("ALTER TABLE purchase_invoices ADD COLUMN tax_amount_paise INTEGER NOT NULL DEFAULT 0 CHECK (tax_amount_paise >= 0);")
    if "grand_total_paise" not in cols:
        cursor.execute("ALTER TABLE purchase_invoices ADD COLUMN grand_total_paise INTEGER NOT NULL DEFAULT 0 CHECK (grand_total_paise >= 0);")

    if "subtotal" in cols:
        cursor.execute("""
            UPDATE purchase_invoices SET
                subtotal_paise = CAST(ROUND(COALESCE(subtotal, 0.0) * 100) AS INTEGER),
                discount_paise = CAST(ROUND(COALESCE(discount, 0.0) * 100) AS INTEGER),
                tax_amount_paise = CAST(ROUND(COALESCE(tax_amount, 0.0) * 100) AS INTEGER),
                grand_total_paise = CAST(ROUND(COALESCE(grand_total, 0.0) * 100) AS INTEGER);
        """)
        cursor.execute("ALTER TABLE purchase_invoices DROP COLUMN subtotal;")
        cursor.execute("ALTER TABLE purchase_invoices DROP COLUMN discount;")
        cursor.execute("ALTER TABLE purchase_invoices DROP COLUMN tax_amount;")
        cursor.execute("ALTER TABLE purchase_invoices DROP COLUMN grand_total;")

    # 4. purchase_invoice_lines: purchase_rate, mrp, discount, tax_amount, line_total -> *_paise
    cols = _get_columns(cursor, "purchase_invoice_lines")
    if "purchase_rate_paise" not in cols:
        cursor.execute("ALTER TABLE purchase_invoice_lines ADD COLUMN purchase_rate_paise INTEGER NOT NULL DEFAULT 0 CHECK (purchase_rate_paise >= 0);")
    if "mrp_paise" not in cols:
        cursor.execute("ALTER TABLE purchase_invoice_lines ADD COLUMN mrp_paise INTEGER NOT NULL DEFAULT 0 CHECK (mrp_paise >= 0);")
    if "discount_paise" not in cols:
        cursor.execute("ALTER TABLE purchase_invoice_lines ADD COLUMN discount_paise INTEGER NOT NULL DEFAULT 0 CHECK (discount_paise >= 0);")
    if "tax_amount_paise" not in cols:
        cursor.execute("ALTER TABLE purchase_invoice_lines ADD COLUMN tax_amount_paise INTEGER NOT NULL DEFAULT 0 CHECK (tax_amount_paise >= 0);")
    if "line_total_paise" not in cols:
        cursor.execute("ALTER TABLE purchase_invoice_lines ADD COLUMN line_total_paise INTEGER NOT NULL DEFAULT 0 CHECK (line_total_paise >= 0);")

    if "purchase_rate" in cols:
        cursor.execute("""
            UPDATE purchase_invoice_lines SET
                purchase_rate_paise = CAST(ROUND(COALESCE(purchase_rate, 0.0) * 100) AS INTEGER),
                mrp_paise = CAST(ROUND(COALESCE(mrp, 0.0) * 100) AS INTEGER),
                discount_paise = CAST(ROUND(COALESCE(discount, 0.0) * 100) AS INTEGER),
                tax_amount_paise = CAST(ROUND(COALESCE(tax_amount, 0.0) * 100) AS INTEGER),
                line_total_paise = CAST(ROUND(COALESCE(line_total, 0.0) * 100) AS INTEGER);
        """)
        cursor.execute("ALTER TABLE purchase_invoice_lines DROP COLUMN purchase_rate;")
        cursor.execute("ALTER TABLE purchase_invoice_lines DROP COLUMN mrp;")
        cursor.execute("ALTER TABLE purchase_invoice_lines DROP COLUMN discount;")
        cursor.execute("ALTER TABLE purchase_invoice_lines DROP COLUMN tax_amount;")
        cursor.execute("ALTER TABLE purchase_invoice_lines DROP COLUMN line_total;")

    # 5. medicine_batches: mrp, purchase_rate -> *_paise
    cols = _get_columns(cursor, "medicine_batches")
    if "mrp_paise" not in cols:
        cursor.execute("ALTER TABLE medicine_batches ADD COLUMN mrp_paise INTEGER NOT NULL DEFAULT 0 CHECK (mrp_paise >= 0);")
    if "purchase_rate_paise" not in cols:
        cursor.execute("ALTER TABLE medicine_batches ADD COLUMN purchase_rate_paise INTEGER NOT NULL DEFAULT 0 CHECK (purchase_rate_paise >= 0);")

    if "mrp" in cols:
        cursor.execute("""
            UPDATE medicine_batches SET
                mrp_paise = CAST(ROUND(COALESCE(mrp, 0.0) * 100) AS INTEGER),
                purchase_rate_paise = CAST(ROUND(COALESCE(purchase_rate, 0.0) * 100) AS INTEGER);
        """)
        cursor.execute("ALTER TABLE medicine_batches DROP COLUMN mrp;")
        cursor.execute("ALTER TABLE medicine_batches DROP COLUMN purchase_rate;")

    # 6. supplier_payable_ledger: amount, balance -> *_paise
    cols = _get_columns(cursor, "supplier_payable_ledger")
    if "amount_paise" not in cols:
        cursor.execute("ALTER TABLE supplier_payable_ledger ADD COLUMN amount_paise INTEGER NOT NULL DEFAULT 0 CHECK (amount_paise >= 0);")
    if "balance_paise" not in cols:
        cursor.execute("ALTER TABLE supplier_payable_ledger ADD COLUMN balance_paise INTEGER NOT NULL DEFAULT 0;")

    if "amount" in cols:
        cursor.execute("""
            UPDATE supplier_payable_ledger SET
                amount_paise = CAST(ROUND(COALESCE(amount, 0.0) * 100) AS INTEGER),
                balance_paise = CAST(ROUND(COALESCE(balance, 0.0) * 100) AS INTEGER);
        """)
        cursor.execute("ALTER TABLE supplier_payable_ledger DROP COLUMN amount;")
        cursor.execute("ALTER TABLE supplier_payable_ledger DROP COLUMN balance;")

    cursor.close()
