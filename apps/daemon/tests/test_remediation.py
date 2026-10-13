"""Automated tests for pre-sales remediation pass.

Covers:
1. Concurrency safety of first-run setup (atomic BEGIN IMMEDIATE locking, exactly one winner).
2. Concurrency safety of purchase posting (status recheck inside transaction, prevents double posting).
3. Inactive medicine rejection in purchase entry (create & update).
4. Pack size validation against medicine master in purchase entry (create & update).
5. Transactional migration execution with rollback on failure and clean retry.
6. Repository hygiene checks: start-backend.bat, README.md, .gitignore secret.key.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import pytest
from fastapi.testclient import TestClient

from pharmacy_daemon.app import create_app
from pharmacy_daemon.config import DaemonConfig
from pharmacy_daemon.db.migrations import (
    MIGRATIONS,
    MigrationConnectionProxy,
    ensure_migration_table,
    get_applied_versions,
    run_migrations,
)


# ==============================================================================
# 1. CONCURRENCY TESTS
# ==============================================================================

def test_concurrent_first_run_setup(tmp_path: Path):
    """Test concurrent first-run setup requests: exactly 1 succeeds, others get 400."""
    app_dir = tmp_path / "AppSetupRace"
    data_dir = app_dir / "data"
    db_path = data_dir / "pharmacy.db"
    log_dir = app_dir / "logs"

    config = DaemonConfig(
        app_dir=app_dir,
        data_dir=data_dir,
        db_path=db_path,
        log_dir=log_dir,
        host="127.0.0.1",
        port=38299,
        jwt_secret_key="concurrency_secret_test_key_12345",
        jwt_algorithm="HS256",
        access_token_expire_minutes=60,
    )
    config.ensure_directories()
    app = create_app(config)

    with TestClient(app) as client:
        setup_payload = {
            "username": "race_admin",
            "full_name": "Race Admin User",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "pin": "1234",
            "store_name": "Atomic Pharmacy",
        }

        # Concurrently send 5 setup requests
        def attempt_setup(thread_id: int):
            return client.post("/api/v1/auth/first-run-setup", json=setup_payload)

        with ThreadPoolExecutor(max_workers=5) as executor:
            responses = list(executor.map(attempt_setup, range(5)))

        status_codes = [r.status_code for r in responses]
        assert status_codes.count(201) == 1, f"Expected exactly one 201 Created, got: {status_codes}"
        assert status_codes.count(400) == 4, f"Expected 4 400 Bad Request, got: {status_codes}"

        success_response = [r for r in responses if r.status_code == 201][0]
        assert "access_token" in success_response.json()

        for failure_response in [r for r in responses if r.status_code == 400]:
            assert "already initialized" in failure_response.json()["detail"].lower()

        # Database verification: exactly 1 admin user and 1 profile
        with config.db_path.open():
            pass  # Ensure DB file exists
        engine = app.state.db_engine
        with engine.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'ADMIN';")
            assert cursor.fetchone()[0] == 1
            cursor.execute("SELECT COUNT(*) FROM system_settings WHERE key = 'store_name';")
            assert cursor.fetchone()[0] == 1


def test_concurrent_purchase_posting(client: TestClient):
    """Test concurrent purchase invoice posting requests: exactly 1 succeeds, others get 400."""
    # 1. Setup admin
    setup_payload = {
        "username": "post_race_admin",
        "full_name": "Posting Race Admin",
        "password": "Password123!",
        "confirm_password": "Password123!",
        "pin": "2222",
        "store_name": "Concurrency Pharma",
    }
    setup_res = client.post("/api/v1/auth/first-run-setup", json=setup_payload)
    assert setup_res.status_code == 201
    auth_header = {"Authorization": f"Bearer {setup_res.json()['access_token']}"}

    # 2. Create supplier & medicine (pack_size = 10)
    sup_res = client.post(
        "/api/v1/masters/suppliers",
        json={"name": "Race Supplier", "credit_days": 30},
        headers=auth_header,
    )
    assert sup_res.status_code == 201
    supplier_id = sup_res.json()["data"]["id"]

    med_res = client.post(
        "/api/v1/masters/medicines",
        json={
            "brand_name": "Atomic Cillin 500",
            "generic_salt": "Amoxicillin",
            "dosage_form": "CAPSULE",
            "pack_size": 10,
            "gst_rate": 12.0,
        },
        headers=auth_header,
    )
    assert med_res.status_code == 201
    medicine_id = med_res.json()["data"]["id"]

    # 3. Create draft purchase invoice with 10 paid packs (100 units)
    inv_res = client.post(
        "/api/v1/purchases",
        json={
            "supplier_id": supplier_id,
            "supplier_invoice_number": "RACE-INV-001",
            "invoice_date": "2026-10-08",
            "lines": [
                {
                    "medicine_id": medicine_id,
                    "batch_number": "RACE-B01",
                    "expiry_date": "2028-12-31",
                    "pack_size": 10,
                    "paid_quantity": 10,
                    "purchase_rate_paise": 5000,
                    "mrp_paise": 8000,
                    "discount_paise": 0,
                    "gst_percentage": 12.0,
                }
            ],
        },
        headers=auth_header,
    )
    assert inv_res.status_code == 201
    invoice_id = inv_res.json()["data"]["id"]

    # 4. Concurrently attempt posting the same invoice 5 times
    def attempt_post(worker_id: int):
        return client.post(f"/api/v1/purchases/{invoice_id}/post", headers=auth_header)

    with ThreadPoolExecutor(max_workers=5) as executor:
        responses = list(executor.map(attempt_post, range(5)))

    status_codes = [r.status_code for r in responses]
    assert status_codes.count(200) == 1, f"Expected exactly one 200 OK, got: {status_codes}"
    assert status_codes.count(400) == 4, f"Expected 4 400 Bad Request, got: {status_codes}"

    for r in responses:
        if r.status_code == 400:
            assert "already posted" in r.json()["detail"].lower()

    # 5. Verify database integrity: stock inwarded exactly once, ledger has exactly 1 entry
    engine = client.app.state.db_engine
    with engine.get_connection() as conn:
        cursor = conn.cursor()
        # Verify batch quantity = 10 packs * 10 pack_size = 100 units
        cursor.execute("SELECT current_quantity FROM medicine_batches WHERE medicine_id = ?;", (medicine_id,))
        batches = cursor.fetchall()
        assert len(batches) == 1
        assert batches[0][0] == 100

        # Verify inventory ledger has exactly 1 entry for this purchase
        cursor.execute(
            "SELECT COUNT(*) FROM inventory_ledger WHERE reference_id = ? AND transaction_type = 'PURCHASE_INWARD';",
            (invoice_id,),
        )
        assert cursor.fetchone()[0] == 1

        # Verify supplier payable ledger has exactly 1 entry for this invoice
        cursor.execute(
            "SELECT COUNT(*) FROM supplier_payable_ledger WHERE reference_id = ? AND reference_type = 'PURCHASE_INVOICE';",
            (invoice_id,),
        )
        assert cursor.fetchone()[0] == 1


# ==============================================================================
# 2. INACTIVE MEDICINE REJECTION
# ==============================================================================

def test_inactive_medicine_rejection_in_purchase_create_and_update(client: TestClient):
    """Test that inactive medicines are rejected during purchase create and update."""
    setup_payload = {
        "username": "inactive_test_admin",
        "full_name": "Admin Inactive Test",
        "password": "Password123!",
        "confirm_password": "Password123!",
        "pin": "3333",
        "store_name": "Validation Care",
    }
    setup_res = client.post("/api/v1/auth/first-run-setup", json=setup_payload)
    auth_header = {"Authorization": f"Bearer {setup_res.json()['access_token']}"}

    sup_res = client.post(
        "/api/v1/masters/suppliers",
        json={"name": "Supplier Val", "credit_days": 15},
        headers=auth_header,
    )
    supplier_id = sup_res.json()["data"]["id"]

    # Active medicine 1
    m1_res = client.post(
        "/api/v1/masters/medicines",
        json={
            "brand_name": "Active Med",
            "generic_salt": "Salt A",
            "dosage_form": "TABLET",
            "pack_size": 10,
            "gst_rate": 5.0,
        },
        headers=auth_header,
    )
    m1_id = m1_res.json()["data"]["id"]

    # Inactive medicine 2 (create then deactivate)
    m2_res = client.post(
        "/api/v1/masters/medicines",
        json={
            "brand_name": "Inactive Med",
            "generic_salt": "Salt B",
            "dosage_form": "TABLET",
            "pack_size": 10,
            "gst_rate": 5.0,
        },
        headers=auth_header,
    )
    m2_id = m2_res.json()["data"]["id"]
    deact_res = client.put(
        f"/api/v1/masters/medicines/{m2_id}",
        json={"is_active": False},
        headers=auth_header,
    )
    assert deact_res.status_code == 200
    assert deact_res.json()["data"]["is_active"] is False

    # 1. Attempt to create purchase invoice with inactive medicine
    create_res = client.post(
        "/api/v1/purchases",
        json={
            "supplier_id": supplier_id,
            "supplier_invoice_number": "INV-INACTIVE-01",
            "invoice_date": "2026-10-08",
            "lines": [
                {
                    "medicine_id": m2_id,
                    "batch_number": "INACT-01",
                    "expiry_date": "2028-12-31",
                    "pack_size": 10,
                    "paid_quantity": 5,
                    "purchase_rate_paise": 1000,
                    "mrp_paise": 1500,
                    "discount_paise": 0,
                    "gst_percentage": 5.0,
                }
            ],
        },
        headers=auth_header,
    )
    assert create_res.status_code == 400
    assert "is inactive and cannot be purchased" in create_res.json()["detail"]

    # 2. Create valid draft with active medicine
    draft_res = client.post(
        "/api/v1/purchases",
        json={
            "supplier_id": supplier_id,
            "supplier_invoice_number": "INV-VALID-01",
            "invoice_date": "2026-10-08",
            "lines": [
                {
                    "medicine_id": m1_id,
                    "batch_number": "ACT-01",
                    "expiry_date": "2028-12-31",
                    "pack_size": 10,
                    "paid_quantity": 5,
                    "purchase_rate_paise": 1000,
                    "mrp_paise": 1500,
                    "discount_paise": 0,
                    "gst_percentage": 5.0,
                }
            ],
        },
        headers=auth_header,
    )
    assert draft_res.status_code == 201
    draft_id = draft_res.json()["data"]["id"]

    # 3. Attempt to update draft with inactive medicine line
    update_res = client.put(
        f"/api/v1/purchases/{draft_id}",
        json={
            "supplier_id": supplier_id,
            "supplier_invoice_number": "INV-VALID-01",
            "invoice_date": "2026-10-08",
            "lines": [
                {
                    "medicine_id": m2_id,
                    "batch_number": "INACT-02",
                    "expiry_date": "2028-12-31",
                    "pack_size": 10,
                    "paid_quantity": 5,
                    "purchase_rate_paise": 1000,
                    "mrp_paise": 1500,
                    "discount_paise": 0,
                    "gst_percentage": 5.0,
                }
            ],
        },
        headers=auth_header,
    )
    assert update_res.status_code == 400
    assert "is inactive and cannot be purchased" in update_res.json()["detail"]


# ==============================================================================
# 3. PACK SIZE MISMATCH VALIDATION
# ==============================================================================

def test_pack_size_mismatch_validation_in_purchase(client: TestClient):
    """Test that purchase lines pack_size must strictly match the medicine master pack_size."""
    setup_payload = {
        "username": "pack_admin",
        "full_name": "Admin Pack Size Test",
        "password": "Password123!",
        "confirm_password": "Password123!",
        "pin": "4444",
        "store_name": "Pack Check Pharmacy",
    }
    setup_res = client.post("/api/v1/auth/first-run-setup", json=setup_payload)
    auth_header = {"Authorization": f"Bearer {setup_res.json()['access_token']}"}

    sup_res = client.post(
        "/api/v1/masters/suppliers",
        json={"name": "Pack Supplier", "credit_days": 15},
        headers=auth_header,
    )
    supplier_id = sup_res.json()["data"]["id"]

    # Medicine with pack_size = 10
    med_res = client.post(
        "/api/v1/masters/medicines",
        json={
            "brand_name": "Strip Pack 10",
            "generic_salt": "Paracetamol",
            "dosage_form": "TABLET",
            "pack_size": 10,
            "gst_rate": 12.0,
        },
        headers=auth_header,
    )
    med_id = med_res.json()["data"]["id"]

    # 1. Attempt create with pack_size = 1 (mismatch)
    bad_create = client.post(
        "/api/v1/purchases",
        json={
            "supplier_id": supplier_id,
            "supplier_invoice_number": "INV-PACK-ERR-1",
            "invoice_date": "2026-10-08",
            "lines": [
                {
                    "medicine_id": med_id,
                    "batch_number": "B-ERR-01",
                    "expiry_date": "2028-12-31",
                    "pack_size": 1,
                    "paid_quantity": 2,
                    "purchase_rate_paise": 1000,
                    "mrp_paise": 1500,
                    "discount_paise": 0,
                    "gst_percentage": 12.0,
                }
            ],
        },
        headers=auth_header,
    )
    assert bad_create.status_code == 422
    assert "does not match master pack size" in bad_create.json()["detail"]

    # 2. Create valid with pack_size = 10
    good_create = client.post(
        "/api/v1/purchases",
        json={
            "supplier_id": supplier_id,
            "supplier_invoice_number": "INV-PACK-OK",
            "invoice_date": "2026-10-08",
            "lines": [
                {
                    "medicine_id": med_id,
                    "batch_number": "B-OK-01",
                    "expiry_date": "2028-12-31",
                    "pack_size": 10,
                    "paid_quantity": 2,
                    "purchase_rate_paise": 1000,
                    "mrp_paise": 1500,
                    "discount_paise": 0,
                    "gst_percentage": 12.0,
                }
            ],
        },
        headers=auth_header,
    )
    assert good_create.status_code == 201
    draft_id = good_create.json()["data"]["id"]

    # 3. Attempt update with pack_size = 20 (mismatch)
    bad_update = client.put(
        f"/api/v1/purchases/{draft_id}",
        json={
            "supplier_id": supplier_id,
            "supplier_invoice_number": "INV-PACK-OK",
            "invoice_date": "2026-10-08",
            "lines": [
                {
                    "medicine_id": med_id,
                    "batch_number": "B-OK-01",
                    "expiry_date": "2028-12-31",
                    "pack_size": 20,
                    "paid_quantity": 2,
                    "purchase_rate_paise": 1000,
                    "mrp_paise": 1500,
                    "discount_paise": 0,
                    "gst_percentage": 12.0,
                }
            ],
        },
        headers=auth_header,
    )
    assert bad_update.status_code == 422
    assert "does not match master pack size" in bad_update.json()["detail"]


# ==============================================================================
# 4. MIGRATION TRANSACTIONAL ROLLBACK AND RETRY
# ==============================================================================

def test_migration_transactional_rollback_and_retry(tmp_path: Path):
    """Test that failed migrations roll back atomically and can be cleanly retried."""
    db_file = tmp_path / "migration_test.db"
    conn = sqlite3.connect(str(db_file), isolation_level=None)
    conn.execute("PRAGMA journal_mode = WAL;")

    # Run baseline registered migrations
    applied = run_migrations(conn)
    assert applied == len(MIGRATIONS)
    assert get_applied_versions(conn) == {m.VERSION for m in MIGRATIONS}

    # Define a faulty migration
    class FaultyMigration:
        VERSION = 998
        NAME = "test_faulty_migration"

        @staticmethod
        def apply(proxy: MigrationConnectionProxy):
            proxy.executescript("""
                CREATE TABLE test_canary_rollback (id INTEGER PRIMARY KEY, title TEXT);
                INSERT INTO test_canary_rollback (id, title) VALUES (1, 'Canary Before Failure');
                -- The following invalid SQL statement fails on purpose:
                INSERT INTO non_existent_table_xyz (col) VALUES (999);
            """)

    MIGRATIONS.append(FaultyMigration)
    try:
        with pytest.raises(sqlite3.OperationalError):
            run_migrations(conn)

        # Verify rollback: canary table should not exist!
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_canary_rollback';")
        assert cursor.fetchone() is None, "Table test_canary_rollback should have been rolled back!"

        # Verify migration 998 is NOT recorded
        assert 998 not in get_applied_versions(conn)

    finally:
        MIGRATIONS.pop()

    # Now define the fixed migration
    class FixedMigration:
        VERSION = 998
        NAME = "test_faulty_migration"

        @staticmethod
        def apply(proxy: MigrationConnectionProxy):
            proxy.executescript("""
                CREATE TABLE test_canary_rollback (id INTEGER PRIMARY KEY, title TEXT);
                INSERT INTO test_canary_rollback (id, title) VALUES (1, 'Canary After Fix');
            """)

    MIGRATIONS.append(FixedMigration)
    try:
        newly_applied = run_migrations(conn)
        assert newly_applied == 1
        assert 998 in get_applied_versions(conn)

        # Table exists and contains the row
        cursor = conn.cursor()
        cursor.execute("SELECT title FROM test_canary_rollback WHERE id = 1;")
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "Canary After Fix"

    finally:
        MIGRATIONS.pop()

    conn.close()


# ==============================================================================
# 5. REPOSITORY HYGIENE AND SCRIPT INTEGRITY
# ==============================================================================

def test_repository_hygiene_scripts_and_files():
    """Verify backend start script, readme, and gitignore configuration."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent

    # 1. scripts/start-backend.bat
    bat_file = repo_root / "scripts" / "start-backend.bat"
    assert bat_file.exists(), "scripts/start-backend.bat must exist"
    bat_content = bat_file.read_text(encoding="utf-8")
    assert "PYTHONPATH" in bat_content
    assert "%~dp0..\\apps\\daemon" in bat_content
    assert "DAEMON_SRC" in bat_content

    # 2. apps/daemon/README.md
    readme_file = repo_root / "apps" / "daemon" / "README.md"
    assert readme_file.exists(), "apps/daemon/README.md must exist for pyproject.toml"
    assert len(readme_file.read_text(encoding="utf-8").strip()) > 100

    # 3. .gitignore contains secret.key
    gitignore_file = repo_root / ".gitignore"
    assert gitignore_file.exists(), ".gitignore must exist"
    gitignore_content = gitignore_file.read_text(encoding="utf-8")
    assert "secret.key" in gitignore_content
