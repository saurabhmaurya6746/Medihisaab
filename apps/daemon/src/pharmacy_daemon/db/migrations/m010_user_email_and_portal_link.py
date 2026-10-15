"""Migration 010: Add email column to users table and portal link metadata.

Enables pharmacy owners and staff to authenticate with their email address,
linking central MediHisaab portal accounts with local POS installations while
preserving all existing accounts, passwords, invoices, and data.
"""

import logging
import sqlite3

logger = logging.getLogger("pharmacy_daemon.db.migrations.m010")

VERSION = 10
NAME = "010_user_email_and_portal_link"


def _get_columns(cursor: sqlite3.Cursor, table_name: str) -> set:
    cursor.execute(f"PRAGMA table_info({table_name});")
    return {row[1] for row in cursor.fetchall()}


def apply_migration(conn: sqlite3.Connection) -> None:
    """Apply migration to add email column and index on users table."""
    cursor = conn.cursor()

    # 1. Add email column to users if not present
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users';")
    if cursor.fetchone():
        cols = _get_columns(cursor, "users")
        if "email" not in cols:
            logger.info("Adding email column to users table...")
            cursor.execute("ALTER TABLE users ADD COLUMN email TEXT;")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")

    # 2. Ensure system_config table has key index
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='system_config';")
    if cursor.fetchone():
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_system_config_key ON system_config(key);")

    cursor.close()


def apply(proxy) -> None:
    """Entry point for migration runner."""
    apply_migration(proxy)
