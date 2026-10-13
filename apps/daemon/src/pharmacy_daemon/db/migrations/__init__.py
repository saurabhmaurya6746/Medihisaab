"""Idempotent database migration registry and runner with transactional safety."""

from datetime import datetime, timezone
import logging
import sqlite3

from . import m001_initial_schema
from . import m002_master_catalog_enhancements
from . import m003_purchases_inventory_and_batches
from . import m004_monetary_paise_hardening
from . import m005_sales_pos_and_compliance
from . import m006_inventory_expiry_and_want_book
from . import m007_khata_returns_and_wastage
from . import m008_compliance_backups_and_reconciliation

logger = logging.getLogger("pharmacy_daemon.db.migrations")

# Sequential migration catalog
MIGRATIONS = [
    m001_initial_schema,
    m002_master_catalog_enhancements,
    m003_purchases_inventory_and_batches,
    m004_monetary_paise_hardening,
    m005_sales_pos_and_compliance,
    m006_inventory_expiry_and_want_book,
    m007_khata_returns_and_wastage,
    m008_compliance_backups_and_reconciliation,
]


class MigrationConnectionProxy:
    """Connection proxy that executes multi-statement SQL scripts inside the active transaction

    without Python sqlite3 executescript auto-committing.
    """

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def cursor(self) -> sqlite3.Cursor:
        return self._conn.cursor()

    def execute(self, *args, **kwargs):
        return self._conn.execute(*args, **kwargs)

    def executemany(self, *args, **kwargs):
        return self._conn.executemany(*args, **kwargs)

    def executescript(self, script: str) -> None:
        statement = ""
        for line in script.splitlines():
            line_clean = line.strip()
            if not line_clean or line_clean.startswith("--"):
                continue
            statement += line + "\n"
            if sqlite3.complete_statement(statement):
                self._conn.execute(statement.strip())
                statement = ""
        if statement.strip():
            self._conn.execute(statement.strip())

    def __getattr__(self, name: str):
        return getattr(self._conn, name)


def ensure_migration_table(conn: sqlite3.Connection) -> None:
    """Ensure the schema_migrations tracker table exists."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        );
    """)
    cursor.close()


def get_applied_versions(conn: sqlite3.Connection) -> set[int]:
    """Retrieve all previously applied migration versions."""
    ensure_migration_table(conn)
    cursor = conn.cursor()
    cursor.execute("SELECT version FROM schema_migrations ORDER BY version ASC;")
    rows = cursor.fetchall()
    cursor.close()
    return {row[0] for row in rows}


def run_migrations(conn: sqlite3.Connection) -> int:
    """Apply all pending migrations idempotently inside discrete, rollback-safe transactions."""
    ensure_migration_table(conn)
    applied_versions = get_applied_versions(conn)
    newly_applied = 0

    for migration in MIGRATIONS:
        if migration.VERSION not in applied_versions:
            logger.info("Applying migration %03d (%s)...", migration.VERSION, migration.NAME)
            proxy = MigrationConnectionProxy(conn)
            conn.execute("BEGIN IMMEDIATE;")
            try:
                migration.apply(proxy)
                now_str = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?);",
                    (migration.VERSION, migration.NAME, now_str),
                )
                conn.execute("COMMIT;")
                newly_applied += 1
                logger.info("Migration %03d applied successfully.", migration.VERSION)
            except Exception as e:
                conn.execute("ROLLBACK;")
                logger.error("Migration %03d failed: %s. Rolled back.", migration.VERSION, e)
                raise

    return newly_applied
