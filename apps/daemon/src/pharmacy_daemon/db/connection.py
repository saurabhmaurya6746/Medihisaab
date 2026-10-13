"""SQLite connection management and pragma enforcement."""

import logging
from pathlib import Path
import sqlite3
from typing import Generator

logger = logging.getLogger("pharmacy_daemon.db")


def apply_pragmas(conn: sqlite3.Connection) -> None:
    """Enforce WAL mode, foreign keys, synchronous normal, and busy timeout pragmas."""
    cursor = conn.cursor()
    # 1. Write-Ahead Logging for high concurrency and non-blocking reads
    cursor.execute("PRAGMA journal_mode = WAL;")
    # 2. Referential integrity
    cursor.execute("PRAGMA foreign_keys = ON;")
    # 3. Synchronous NORMAL balances durability with write velocity
    cursor.execute("PRAGMA synchronous = NORMAL;")
    # 4. Busy timeout of 10,000ms prevents SQLITE_BUSY under sudden write spikes
    cursor.execute("PRAGMA busy_timeout = 10000;")
    cursor.close()


def create_connection(db_path: Path) -> sqlite3.Connection:
    """Create a new SQLite connection with configured pragmas and row factory."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        str(db_path),
        timeout=10.0,
        check_same_thread=False,
        isolation_level=None,  # Autocommit mode by default; explicit transactions with BEGIN
    )
    conn.row_factory = sqlite3.Row
    apply_pragmas(conn)
    return conn
