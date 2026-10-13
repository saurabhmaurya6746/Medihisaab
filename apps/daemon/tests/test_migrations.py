"""Tests for SQLite database engine, pragmas, schema migrations, and FTS5 search."""

from pharmacy_daemon.db.engine import DatabaseEngine
from pharmacy_daemon.db.migrations import run_migrations, get_applied_versions


def test_database_initialization_and_pragmas(test_engine: DatabaseEngine):
    """Verify database file creation, pragmas (WAL, foreign_keys, synchronous, busy_timeout)."""
    assert test_engine.db_path.exists()
    health = test_engine.get_health()

    assert health["status"] == "HEALTHY"
    assert health["journal_mode"] == "WAL"
    assert health["synchronous"] in ("NORMAL", 1)
    assert health["foreign_keys"] is True
    assert health["schema_version"] >= 5
    assert health["integrity"].upper() == "OK"


def test_migrations_idempotency(test_engine: DatabaseEngine):
    """Verify running migrations multiple times applies 0 additional migrations without error."""
    with test_engine.get_connection() as conn:
        applied_first = get_applied_versions(conn)
        assert 1 in applied_first

        # Second run should be a no-op
        second_run_count = run_migrations(conn)
        assert second_run_count == 0

        applied_second = get_applied_versions(conn)
        assert applied_first == applied_second


def test_required_initial_tables_exist(test_engine: DatabaseEngine):
    """Verify all 8 mandatory Milestone 1B-1 tables exist."""
    expected_tables = {
        "schema_migrations",
        "system_settings",
        "users",
        "manufacturers",
        "suppliers",
        "medicines",
        "customers",
        "fts_medicines",
    }

    with test_engine.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'shadow');")
        rows = cursor.fetchall()
        existing_tables = {row[0] for row in rows}

        for table in expected_tables:
            assert table in existing_tables, f"Table '{table}' missing from database!"


def test_fts5_medicines_trigger_synchronization(test_engine: DatabaseEngine):
    """Verify FTS5 virtual table automatically synchronizes on medicine insert and search."""
    with test_engine.get_connection() as conn:
        cursor = conn.cursor()

        # Insert a medicine row
        cursor.execute(
            """
            INSERT INTO medicines (brand_name, generic_salt, dosage_form, pack_size, hsn_code, gst_rate, min_stock_units, is_active, created_at, updated_at)
            VALUES ('Dolo 650', 'Paracetamol 650mg', 'TABLET', 15, '3004', 12.0, 10, 1, '2026-10-07T12:00:00Z', '2026-10-07T12:00:00Z');
            """
        )
        med_id = cursor.lastrowid

        # Search FTS5 by brand name
        cursor.execute("SELECT rowid, brand_name, generic_salt FROM fts_medicines WHERE fts_medicines MATCH 'Dolo*';")
        match_brand = cursor.fetchall()
        assert len(match_brand) == 1
        assert match_brand[0][0] == med_id
        assert match_brand[0][1] == "Dolo 650"

        # Search FTS5 by generic salt
        cursor.execute("SELECT rowid, brand_name, generic_salt FROM fts_medicines WHERE fts_medicines MATCH 'Paracetamol*';")
        match_salt = cursor.fetchall()
        assert len(match_salt) == 1
        assert match_salt[0][0] == med_id

        # Update medicine name and verify FTS sync
        cursor.execute(
            "UPDATE medicines SET brand_name = 'Dolo 650 Extra' WHERE id = ?;",
            (med_id,),
        )
        cursor.execute("SELECT rowid, brand_name FROM fts_medicines WHERE fts_medicines MATCH 'Extra*';")
        match_updated = cursor.fetchall()
        assert len(match_updated) == 1
        assert match_updated[0][1] == "Dolo 650 Extra"

        # Delete medicine and verify FTS removal
        cursor.execute("DELETE FROM medicines WHERE id = ?;", (med_id,))
        cursor.execute("SELECT rowid FROM fts_medicines WHERE fts_medicines MATCH 'Dolo*';")
        match_deleted = cursor.fetchall()
        assert len(match_deleted) == 0

        cursor.close()


def test_health_telemetry_endpoint(client):
    """Verify /api/v1/health returns system telemetry, uptime, and database health."""
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "HEALTHY"
    assert "version" in data
    assert "uptime_seconds" in data
    assert data["database"]["journal_mode"] == "WAL"
    assert data["database"]["foreign_keys"] is True
    assert data["database"]["integrity"].upper() == "OK"
