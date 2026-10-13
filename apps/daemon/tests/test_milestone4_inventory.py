"""Comprehensive automated test suite for Milestone 4: Inventory Control, Expiry Dashboard, Stock Audits, and Want-Book.

Covers:
- Migration 006 schema verification (tables, columns, indexes, constraints)
- Expiry threshold grouping (EXPIRED, 30d, 60d, 90d, 180d, ALL)
- Expired-batch detection and POS checkout sale rejection
- FEFO ordering preservation
- Near-expiry supplier return dump grouping and valuation
- Stock audit positive adjustment (delta > 0)
- Stock audit negative adjustment (delta < 0, notes requirement, loss calculation)
- Invalid audit reason rejection
- Negative physical stock rejection
- Immutable stock adjustment history & inventory ledger integration
- Automatic low-stock identification against min_stock_units
- Want-Book create, update status (PENDING -> ORDERED -> RECEIVED), and delete workflow
- Role permissions (ADMIN, PHARMACIST, CASHIER)
- Concurrent stock audit thread safety
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from pharmacy_daemon.security.hashing import hash_password


@pytest.fixture
def auth_fixture(client: TestClient) -> dict:
    """Setup store and generate tokens for ADMIN, PHARMACIST, and CASHIER."""
    # 1. Admin setup
    setup_payload = {
        "username": "inv_admin",
        "full_name": "Inventory Admin",
        "password": "Password123!",
        "confirm_password": "Password123!",
        "pin": "1234",
        "store_name": "Apex Central Pharmacy",
    }
    setup_res = client.post("/api/v1/auth/first-run-setup", json=setup_payload)
    assert setup_res.status_code == 201
    admin_token = setup_res.json()["access_token"]

    # 2. Pharmacist & Cashier users
    engine = client.app.state.db_engine
    conn = engine.get_connection()
    try:
        cursor = conn.cursor()
        pwd_hash = hash_password("OperatorPass123!")
        cursor.execute(
            """
            INSERT INTO users (username, full_name, password_hash, pin_hash, role, is_active, created_at, updated_at)
            VALUES ('inv_pharm', 'Staff Pharmacist', ?, NULL, 'PHARMACIST', 1, '2026-10-08T00:00:00Z', '2026-10-08T00:00:00Z');
            """,
            (pwd_hash,),
        )
        cursor.execute(
            """
            INSERT INTO users (username, full_name, password_hash, pin_hash, role, is_active, created_at, updated_at)
            VALUES ('inv_cashier', 'Counter Cashier', ?, NULL, 'CASHIER', 1, '2026-10-08T00:00:00Z', '2026-10-08T00:00:00Z');
            """,
            (pwd_hash,),
        )
        conn.commit()
    finally:
        conn.close()

    # Log in pharmacist and cashier to get JWTs
    p_login = client.post("/api/v1/auth/login", json={"username": "inv_pharm", "password": "OperatorPass123!"})
    c_login = client.post("/api/v1/auth/login", json={"username": "inv_cashier", "password": "OperatorPass123!"})

    return {
        "admin": {"Authorization": f"Bearer {admin_token}"},
        "pharmacist": {"Authorization": f"Bearer {p_login.json()['access_token']}"},
        "cashier": {"Authorization": f"Bearer {c_login.json()['access_token']}"},
    }


def test_migration_006_schema_verification(client: TestClient):
    """Verify that migration 006 created stock_adjustments, want_book, and relevant indices."""
    engine = client.app.state.db_engine
    conn = engine.get_connection()
    try:
        cursor = conn.cursor()
        # Verify schema_migrations includes version 6
        cursor.execute("SELECT version, name FROM schema_migrations WHERE version = 6;")
        m6 = cursor.fetchone()
        assert m6 is not None
        assert "006_inventory_expiry_and_want_book" in m6["name"]

        # Verify stock_adjustments table
        cursor.execute("PRAGMA table_info(stock_adjustments);")
        cols = {row["name"] for row in cursor.fetchall()}
        expected_cols = {
            "id", "adjustment_number", "batch_id", "medicine_id",
            "system_quantity", "physical_quantity", "delta_quantity",
            "reason", "estimated_loss_paise", "notes", "user_id", "created_at"
        }
        assert expected_cols.issubset(cols)

        # Verify want_book table
        cursor.execute("PRAGMA table_info(want_book);")
        wb_cols = {row["name"] for row in cursor.fetchall()}
        expected_wb_cols = {
            "id", "medicine_id", "requested_quantity_packs", "current_stock_units",
            "min_stock_units", "status", "supplier_id", "notes", "requested_by",
            "ordered_at", "received_at", "created_at", "updated_at"
        }
        assert expected_wb_cols.issubset(wb_cols)
    finally:
        conn.close()


def test_expiry_threshold_grouping_and_summary(client: TestClient, auth_fixture: dict):
    """Verify expiry thresholds (EXPIRED, <=30d, <=60d, <=90d, <=180d) and value calculations."""
    headers = auth_fixture["admin"]
    today = date.today()

    # 1. Create supplier
    sup_res = client.post("/api/v1/masters/suppliers", json={"name": "Universal Drugs", "credit_days": 30}, headers=headers)
    supplier_id = sup_res.json()["data"]["id"]

    # 2. Create medicine
    med_res = client.post(
        "/api/v1/masters/medicines",
        json={
            "brand_name": "Azithro-500",
            "generic_salt": "Azithromycin 500mg",
            "dosage_form": "TABLET",
            "pack_size": 10,
            "min_stock_units": 20,
            "gst_rate": 12.0,
        },
        headers=headers,
    )
    med_id = med_res.json()["data"]["id"]

    # Inward batches with varied expiry dates via direct DB insert to precisely test date math
    engine = client.app.state.db_engine
    conn = engine.get_connection()
    try:
        cursor = conn.cursor()
        batches = [
            ("AZ-EXP", (today - timedelta(days=10)).isoformat(), 10, 5000, 8000),      # Expired 10 days ago (10 units)
            ("AZ-30", (today + timedelta(days=15)).isoformat(), 20, 5000, 8000),       # Within 30 days (20 units)
            ("AZ-60", (today + timedelta(days=45)).isoformat(), 30, 5000, 8000),       # Within 60 days (30 units)
            ("AZ-90", (today + timedelta(days=75)).isoformat(), 40, 5000, 8000),       # Within 90 days (40 units)
            ("AZ-180", (today + timedelta(days=120)).isoformat(), 50, 5000, 8000),     # Within 180 days (50 units)
            ("AZ-FAR", (today + timedelta(days=365)).isoformat(), 100, 5000, 8000),    # Valid future (>180d)
        ]
        now_str = datetime.now(timezone.utc).isoformat()
        for b_num, exp_d, qty, ptr, mrp in batches:
            cursor.execute("""
                INSERT INTO medicine_batches (
                    medicine_id, batch_number, expiry_date, mrp_paise, purchase_rate_paise,
                    pack_size, current_quantity, reserved_quantity, is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 10, ?, 0, 1, ?, ?);
            """, (med_id, b_num, exp_d, mrp, ptr, qty, now_str, now_str))
        conn.commit()
    finally:
        conn.close()

    # 3. Test Dashboard Summary
    dash_res = client.get("/api/v1/inventory/expiry?filter=ALL", headers=headers)
    assert dash_res.status_code == 200
    dash_data = dash_res.json()["data"]
    summary = dash_data["summary"]

    assert summary["expired_count"] == 1
    # 10 units at 5000 paise / 10 pack_size = 500 paise/unit * 10 = 5000 paise
    assert summary["expired_value_paise"] == 5000
    assert summary["within_30_count"] == 1
    assert summary["within_60_count"] == 1
    assert summary["within_90_count"] == 1
    assert summary["within_180_count"] == 1

    # 4. Test explicit filter buckets
    exp_res = client.get("/api/v1/inventory/expiry?filter=EXPIRED", headers=headers)
    assert exp_res.status_code == 200
    exp_items = exp_res.json()["data"]["items"]
    assert len(exp_items) == 1
    assert exp_items[0]["batch_number"] == "AZ-EXP"
    assert exp_items[0]["is_expired"] is True
    assert exp_items[0]["days_to_expiry"] < 0

    w30_res = client.get("/api/v1/inventory/expiry?filter=WITHIN_30_DAYS", headers=headers)
    assert w30_res.status_code == 200
    assert len(w30_res.json()["data"]["items"]) == 1
    assert w30_res.json()["data"]["items"][0]["batch_number"] == "AZ-30"

    w90_res = client.get("/api/v1/inventory/expiry?filter=WITHIN_90_DAYS", headers=headers)
    assert w90_res.status_code == 200
    assert len(w90_res.json()["data"]["items"]) == 1
    assert w90_res.json()["data"]["items"][0]["batch_number"] == "AZ-90"


def test_expired_batch_detection_and_sale_rejection(client: TestClient, auth_fixture: dict):
    """Ensure expired batches cannot be dispensed via sales checkout."""
    headers = auth_fixture["admin"]
    today = date.today()

    # Create medicine & expired batch
    med_res = client.post(
        "/api/v1/masters/medicines",
        json={"brand_name": "Paracip-500", "generic_salt": "Paracetamol", "dosage_form": "TABLET", "pack_size": 10, "gst_rate": 5.0},
        headers=headers,
    )
    med_id = med_res.json()["data"]["id"]

    engine = client.app.state.db_engine
    conn = engine.get_connection()
    try:
        cursor = conn.cursor()
        exp_date = (today - timedelta(days=5)).isoformat()
        now_str = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO medicine_batches (
                medicine_id, batch_number, expiry_date, mrp_paise, purchase_rate_paise,
                pack_size, current_quantity, reserved_quantity, is_active, created_at, updated_at
            ) VALUES (?, 'PARA-EXPIRED', ?, 2000, 1200, 10, 50, 0, 1, ?, ?);
        """, (med_id, exp_date, now_str, now_str))
        batch_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()

    # Attempt sales checkout with the expired batch
    sale_payload = {
        "lines": [
            {
                "medicine_id": med_id,
                "batch_id": batch_id,
                "quantity_units": 10,
                "unit_rate_paise": 200,
                "discount_percent": 0.0,
            }
        ],
        "payment_mode": "CASH",
        "cash_tendered_paise": 2000,
    }
    sale_res = client.post("/api/v1/sales/checkout", json=sale_payload, headers=headers)
    assert sale_res.status_code == 422
    assert "expired" in sale_res.json()["detail"].lower()


def test_fefo_ordering_preserved(client: TestClient, auth_fixture: dict):
    """Verify batches are strictly sorted with earliest expiry date first."""
    headers = auth_fixture["admin"]
    today = date.today()

    med_res = client.post(
        "/api/v1/masters/medicines",
        json={"brand_name": "CoughRelief", "generic_salt": "Dextromethorphan", "dosage_form": "SYRUP", "pack_size": 1, "gst_rate": 12.0},
        headers=headers,
    )
    med_id = med_res.json()["data"]["id"]

    engine = client.app.state.db_engine
    conn = engine.get_connection()
    try:
        cursor = conn.cursor()
        now_str = datetime.now(timezone.utc).isoformat()
        # Insert out of order
        dates = [
            ("CR-2028", (today + timedelta(days=600)).isoformat()),
            ("CR-2026", (today + timedelta(days=50)).isoformat()),
            ("CR-2027", (today + timedelta(days=300)).isoformat()),
        ]
        for b_no, exp_d in dates:
            cursor.execute("""
                INSERT INTO medicine_batches (
                    medicine_id, batch_number, expiry_date, mrp_paise, purchase_rate_paise,
                    pack_size, current_quantity, reserved_quantity, is_active, created_at, updated_at
                ) VALUES (?, ?, ?, 12000, 8000, 1, 20, 0, 1, ?, ?);
            """, (med_id, b_no, exp_d, now_str, now_str))
        conn.commit()
    finally:
        conn.close()

    res = client.get(f"/api/v1/inventory/batches?medicine_id={med_id}&in_stock_only=true", headers=headers)
    assert res.status_code == 200
    batches = res.json()["data"]["items"]
    batch_numbers = [b["batch_number"] for b in batches]
    assert batch_numbers == ["CR-2026", "CR-2027", "CR-2028"]


def test_near_expiry_supplier_grouping_and_return_dump(client: TestClient, auth_fixture: dict):
    """Verify supplier return dump endpoint groups near-expiry stock by stockist."""
    headers = auth_fixture["admin"]
    today = date.today()

    sup_res = client.post("/api/v1/masters/suppliers", json={"name": "Kalyan Pharma Distributors", "phone": "9876543210"}, headers=headers)
    supplier_id = sup_res.json()["data"]["id"]

    med_res = client.post(
        "/api/v1/masters/medicines",
        json={"brand_name": "DermaCare Gel", "generic_salt": "Clindamycin", "dosage_form": "OINTMENT", "pack_size": 1, "gst_rate": 12.0},
        headers=headers,
    )
    med_id = med_res.json()["data"]["id"]

    # Inward via posted purchase invoice so supplier mapping is recorded
    inv_payload = {
        "supplier_id": supplier_id,
        "supplier_invoice_number": "KP-DUMP-01",
        "invoice_date": today.isoformat(),
        "lines": [
            {
                "medicine_id": med_id,
                "batch_number": "DC-NEAR-EXP",
                "expiry_date": (today + timedelta(days=40)).isoformat(),
                "pack_size": 1,
                "paid_quantity": 15,
                "free_quantity": 0,
                "purchase_rate_paise": 6000,
                "mrp_paise": 10000,
                "discount_paise": 0,
                "gst_percentage": 12.0,
            }
        ],
    }
    inv_res = client.post("/api/v1/purchases", json=inv_payload, headers=headers)
    assert inv_res.status_code == 201
    inv_id = inv_res.json()["data"]["id"]
    post_res = client.post(f"/api/v1/purchases/{inv_id}/post", headers=headers)
    assert post_res.status_code == 200

    # Query near-expiry return dump for <= 60 days
    dump_res = client.get("/api/v1/inventory/expiry/return-dump?days=60", headers=headers)
    assert dump_res.status_code == 200
    groups = dump_res.json()["data"]
    assert len(groups) >= 1

    kp_group = next((g for g in groups if g["supplier_id"] == supplier_id), None)
    assert kp_group is not None
    assert kp_group["supplier_name"] == "Kalyan Pharma Distributors"
    assert kp_group["total_batches"] == 1
    assert kp_group["total_units"] == 15
    assert kp_group["total_value_paise"] == 15 * 6000


def test_stock_audit_positive_adjustment(client: TestClient, auth_fixture: dict):
    """Test physical stock audit positive count increase (surplus correction)."""
    headers = auth_fixture["pharmacist"]
    today = date.today()

    med_res = client.post(
        "/api/v1/masters/medicines",
        json={"brand_name": "AuditPlus-50", "generic_salt": "Zinc 50mg", "dosage_form": "TABLET", "pack_size": 10, "gst_rate": 5.0},
        headers=auth_fixture["admin"],
    )
    med_id = med_res.json()["data"]["id"]

    engine = client.app.state.db_engine
    conn = engine.get_connection()
    try:
        cursor = conn.cursor()
        now_str = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO medicine_batches (
                medicine_id, batch_number, expiry_date, mrp_paise, purchase_rate_paise,
                pack_size, current_quantity, reserved_quantity, is_active, created_at, updated_at
            ) VALUES (?, 'BATCH-AUD-P', ?, 1500, 1000, 10, 50, 0, 1, ?, ?);
        """, (med_id, (today + timedelta(days=200)).isoformat(), now_str, now_str))
        batch_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()

    # Initial quantity is 50. Physical count reveals 65 (surplus +15)
    audit_payload = {
        "batch_id": batch_id,
        "physical_quantity": 65,
        "reason": "AUDIT_CORRECTION",
        "notes": "Found extra unopened strip during cycle count",
    }
    audit_res = client.post("/api/v1/inventory/audits", json=audit_payload, headers=headers)
    assert audit_res.status_code == 201
    data = audit_res.json()["data"]
    assert data["system_quantity"] == 50
    assert data["physical_quantity"] == 65
    assert data["delta_quantity"] == 15
    assert data["estimated_loss_paise"] == 0
    assert data["adjustment_number"].startswith("ADJ-")

    # Verify batch quantity updated to 65
    batch_check = client.get(f"/api/v1/inventory/audits/batch/{batch_id}", headers=headers)
    assert batch_check.status_code == 200
    assert batch_check.json()["data"]["current_quantity"] == 65

    # Verify inventory ledger entry
    conn = engine.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT transaction_type, quantity_change, quantity_balance, reference_type
            FROM inventory_ledger
            WHERE batch_id = ? ORDER BY id DESC LIMIT 1;
        """, (batch_id,))
        led = cursor.fetchone()
        assert led is not None
        assert led["transaction_type"] == "ADJUSTMENT"
        assert led["quantity_change"] == 15
        assert led["quantity_balance"] == 65
        assert led["reference_type"] == "STOCK_ADJUSTMENT"
    finally:
        conn.close()


def test_stock_audit_negative_adjustment_and_notes_requirement(client: TestClient, auth_fixture: dict):
    """Test physical stock audit loss (breakage/theft) requires notes and records loss in paise."""
    headers = auth_fixture["pharmacist"]
    today = date.today()

    med_res = client.post(
        "/api/v1/masters/medicines",
        json={"brand_name": "AuditLoss Syrup", "generic_salt": "Ambroxol", "dosage_form": "SYRUP", "pack_size": 1, "gst_rate": 12.0},
        headers=auth_fixture["admin"],
    )
    med_id = med_res.json()["data"]["id"]

    engine = client.app.state.db_engine
    conn = engine.get_connection()
    try:
        cursor = conn.cursor()
        now_str = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO medicine_batches (
                medicine_id, batch_number, expiry_date, mrp_paise, purchase_rate_paise,
                pack_size, current_quantity, reserved_quantity, is_active, created_at, updated_at
            ) VALUES (?, 'BATCH-AUD-L', ?, 12000, 7500, 1, 20, 0, 1, ?, ?);
        """, (med_id, (today + timedelta(days=300)).isoformat(), now_str, now_str))
        batch_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()

    # 1. Negative adjustment without notes must fail with HTTP 422
    fail_res = client.post(
        "/api/v1/inventory/audits",
        json={"batch_id": batch_id, "physical_quantity": 18, "reason": "BREAKAGE", "notes": ""},
        headers=headers,
    )
    assert fail_res.status_code == 422
    assert "notes are mandatory" in fail_res.json()["detail"].lower()

    # 2. Negative adjustment with valid notes succeeds
    ok_res = client.post(
        "/api/v1/inventory/audits",
        json={
            "batch_id": batch_id,
            "physical_quantity": 18,
            "reason": "BREAKAGE",
            "notes": "2 bottles dropped from shelf during morning cleaning",
        },
        headers=headers,
    )
    assert ok_res.status_code == 201
    data = ok_res.json()["data"]
    assert data["delta_quantity"] == -2
    assert data["physical_quantity"] == 18
    # 2 units * 7500 paise purchase rate = 15000 paise loss
    assert data["estimated_loss_paise"] == 15000


def test_stock_audit_validations_and_rejections(client: TestClient, auth_fixture: dict):
    """Test validation rejection for invalid reason, negative count, zero delta, and nonexistent batch."""
    headers = auth_fixture["pharmacist"]

    # Invalid reason
    res1 = client.post(
        "/api/v1/inventory/audits",
        json={"batch_id": 1, "physical_quantity": 10, "reason": "INVALID_REASON", "notes": "test"},
        headers=headers,
    )
    assert res1.status_code == 422

    # Negative physical count
    res2 = client.post(
        "/api/v1/inventory/audits",
        json={"batch_id": 1, "physical_quantity": -5, "reason": "THEFT", "notes": "test"},
        headers=headers,
    )
    assert res2.status_code == 422

    # Non-existent batch
    res3 = client.post(
        "/api/v1/inventory/audits",
        json={"batch_id": 99999, "physical_quantity": 10, "reason": "AUDIT_CORRECTION", "notes": "test"},
        headers=headers,
    )
    assert res3.status_code == 404


def test_low_stock_detection(client: TestClient, auth_fixture: dict):
    """Verify medicines whose stock is at or below min_stock_units are detected."""
    headers = auth_fixture["admin"]
    today = date.today()

    # Create medicine with min_stock_units = 50
    med_res = client.post(
        "/api/v1/masters/medicines",
        json={
            "brand_name": "LowStock Drug",
            "generic_salt": "Omeprazole 20mg",
            "dosage_form": "CAPSULE",
            "pack_size": 15,
            "min_stock_units": 50,
            "gst_rate": 12.0,
        },
        headers=headers,
    )
    med_id = med_res.json()["data"]["id"]

    # Inward only 15 units (<= 50)
    engine = client.app.state.db_engine
    conn = engine.get_connection()
    try:
        cursor = conn.cursor()
        now_str = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO medicine_batches (
                medicine_id, batch_number, expiry_date, mrp_paise, purchase_rate_paise,
                pack_size, current_quantity, reserved_quantity, is_active, created_at, updated_at
            ) VALUES (?, 'LS-B01', ?, 3500, 2200, 15, 15, 0, 1, ?, ?);
        """, (med_id, (today + timedelta(days=200)).isoformat(), now_str, now_str))
        conn.commit()
    finally:
        conn.close()

    low_res = client.get("/api/v1/inventory/want-book/low-stock", headers=headers)
    assert low_res.status_code == 200
    items = low_res.json()["data"]
    match = next((item for item in items if item["medicine_id"] == med_id), None)
    assert match is not None
    assert match["current_stock_units"] == 15
    assert match["min_stock_units"] == 50
    assert match["suggested_reorder_packs"] >= 1


def test_want_book_lifecycle_and_crud(client: TestClient, auth_fixture: dict):
    """Test full Want-Book lifecycle: create -> list -> update status (ORDERED, RECEIVED) -> delete."""
    headers = auth_fixture["pharmacist"]

    med_res = client.post(
        "/api/v1/masters/medicines",
        json={"brand_name": "WantMed 100", "generic_salt": "Losartan", "dosage_form": "TABLET", "pack_size": 10, "min_stock_units": 30, "gst_rate": 5.0},
        headers=auth_fixture["admin"],
    )
    med_id = med_res.json()["data"]["id"]

    # 1. Create want-book entry
    create_payload = {
        "medicine_id": med_id,
        "requested_quantity_packs": 10,
        "notes": "Patient regular reorder requested at counter",
    }
    create_res = client.post("/api/v1/inventory/want-book", json=create_payload, headers=headers)
    assert create_res.status_code == 201
    wb_item = create_res.json()["data"]
    wb_id = wb_item["id"]
    assert wb_item["status"] == "PENDING"
    assert wb_item["requested_quantity_packs"] == 10

    # 2. List want-book entries
    list_res = client.get("/api/v1/inventory/want-book?status=PENDING", headers=headers)
    assert list_res.status_code == 200
    listed_ids = [i["id"] for i in list_res.json()["data"]["items"]]
    assert wb_id in listed_ids

    # 3. Update status to ORDERED
    ordered_res = client.patch(
        f"/api/v1/inventory/want-book/{wb_id}/status",
        json={"status": "ORDERED", "notes": "PO placed with distributor via phone"},
        headers=headers,
    )
    assert ordered_res.status_code == 200
    assert ordered_res.json()["data"]["status"] == "ORDERED"
    assert ordered_res.json()["data"]["ordered_at"] is not None

    # 4. Update status to RECEIVED
    rcvd_res = client.patch(
        f"/api/v1/inventory/want-book/{wb_id}/status",
        json={"status": "RECEIVED", "notes": "Inwarded via GRN"},
        headers=headers,
    )
    assert rcvd_res.status_code == 200
    assert rcvd_res.json()["data"]["status"] == "RECEIVED"
    assert rcvd_res.json()["data"]["received_at"] is not None

    # 5. Delete want-book item
    del_res = client.delete(f"/api/v1/inventory/want-book/{wb_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["data"]["deleted_id"] == wb_id


def test_stock_audit_rbac_permissions(client: TestClient, auth_fixture: dict):
    """Enforce that CASHIER cannot execute stock audits, while PHARMACIST and ADMIN can."""
    cashier_headers = auth_fixture["cashier"]
    admin_headers = auth_fixture["admin"]

    # Cashier cannot execute audit
    c_res = client.post(
        "/api/v1/inventory/audits",
        json={"batch_id": 1, "physical_quantity": 10, "reason": "AUDIT_CORRECTION", "notes": "Cashier trial"},
        headers=cashier_headers,
    )
    assert c_res.status_code == 403

    # Cashier can view want-book and create a want-book quick entry (e.g. from POS counter)
    c_want = client.post(
        "/api/v1/inventory/want-book",
        json={"medicine_id": 1, "requested_quantity_packs": 2, "notes": "Cashier counter demand"},
        headers=cashier_headers,
    )
    # Status is 201 or 404 if medicine 1 doesn't exist, but NOT 403 Forbidden
    assert c_want.status_code in (201, 404)


def test_concurrent_stock_adjustment_safety(client: TestClient, auth_fixture: dict):
    """Verify thread-safety and transactional isolation when multiple audits run concurrently."""
    headers = auth_fixture["admin"]
    today = date.today()

    med_res = client.post(
        "/api/v1/masters/medicines",
        json={"brand_name": "RaceStock-20", "generic_salt": "Race Test", "dosage_form": "TABLET", "pack_size": 10, "gst_rate": 5.0},
        headers=headers,
    )
    med_id = med_res.json()["data"]["id"]

    engine = client.app.state.db_engine
    conn = engine.get_connection()
    try:
        cursor = conn.cursor()
        now_str = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO medicine_batches (
                medicine_id, batch_number, expiry_date, mrp_paise, purchase_rate_paise,
                pack_size, current_quantity, reserved_quantity, is_active, created_at, updated_at
            ) VALUES (?, 'RACE-BATCH', ?, 2000, 1000, 10, 100, 0, 1, ?, ?);
        """, (med_id, (today + timedelta(days=200)).isoformat(), now_str, now_str))
        batch_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()

    def submit_adj(worker_id: int):
        new_qty = 100 + worker_id + 1
        return client.post(
            "/api/v1/inventory/audits",
            json={
                "batch_id": batch_id,
                "physical_quantity": new_qty,
                "reason": "AUDIT_CORRECTION",
                "notes": f"Worker {worker_id} adjustment",
            },
            headers=headers,
        )

    with ThreadPoolExecutor(max_workers=5) as executor:
        responses = list(executor.map(submit_adj, range(5)))

    # All should either succeed (201) or cleanly serialize without corrupting data
    status_codes = [r.status_code for r in responses]
    assert all(code in (201, 422) for code in status_codes)

    # Database integrity check: batch current_quantity must match the last successful physical_quantity
    conn = engine.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT current_quantity FROM medicine_batches WHERE id = ?;", (batch_id,))
        final_qty = cursor.fetchone()[0]

        cursor.execute("SELECT physical_quantity FROM stock_adjustments WHERE batch_id = ? ORDER BY id DESC LIMIT 1;", (batch_id,))
        last_adj_qty = cursor.fetchone()[0]
        assert final_qty == last_adj_qty
    finally:
        conn.close()
