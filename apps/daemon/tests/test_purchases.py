"""Comprehensive automated test suite for Purchase Inwarding, Batches, Inventory Ledger, and Payables.

Covers:
- Migration 003 schema verification and idempotency
- Draft purchase creation (no stock or payable impact)
- Atomic purchase posting (stock increase, free scheme calculation, ledger balance)
- Duplicate invoice rejection
- Posted purchase immutability (cannot re-post, cannot edit)
- Multiple batches for same medicine
- FEFO batch ordering (earliest expiry first)
- Supplier payable accrual and ledger history
- Database-level negative stock prevention
- Role-based access control (ADMIN, PHARMACIST, CASHIER, Unauthorized)
- Validation errors (expired dates, invalid GST, invalid quantities)
"""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from pharmacy_daemon.db.migrations import run_migrations
from pharmacy_daemon.security.hashing import hash_password


@pytest.fixture
def auth_tokens(client: TestClient) -> dict:
    """Initialize store and generate tokens for ADMIN, PHARMACIST, and CASHIER."""
    # 1. Setup admin
    setup_payload = {
        "username": "admin_user",
        "full_name": "Admin Operator",
        "password": "AdminPassword123!",
        "confirm_password": "AdminPassword123!",
        "pin": "1111",
        "store_name": "City Care Chemist",
    }
    setup_res = client.post("/api/v1/auth/first-run-setup", json=setup_payload)
    admin_token = setup_res.json()["access_token"]

    # 2. Insert pharmacist and cashier
    app = client.app
    engine = app.state.db_engine
    with engine.get_connection() as conn:
        cursor = conn.cursor()
        pwd_hash = hash_password("OperatorPass123!")
        cursor.execute(
            """
            INSERT INTO users (username, full_name, password_hash, pin_hash, role, is_active, created_at, updated_at)
            VALUES ('pharm_user', 'Pharmacist One', ?, NULL, 'PHARMACIST', 1, '2026-10-07T00:00:00Z', '2026-10-07T00:00:00Z');
            """,
            (pwd_hash,),
        )
        cursor.execute(
            """
            INSERT INTO users (username, full_name, password_hash, pin_hash, role, is_active, created_at, updated_at)
            VALUES ('cashier_user', 'Cashier One', ?, NULL, 'CASHIER', 1, '2026-10-07T00:00:00Z', '2026-10-07T00:00:00Z');
            """,
            (pwd_hash,),
        )
        conn.commit()

    login_pharm = client.post("/api/v1/auth/login", json={"username": "pharm_user", "password": "OperatorPass123!"})
    login_cash = client.post("/api/v1/auth/login", json={"username": "cashier_user", "password": "OperatorPass123!"})

    return {
        "ADMIN": admin_token,
        "PHARMACIST": login_pharm.json()["access_token"],
        "CASHIER": login_cash.json()["access_token"],
    }


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def master_entities(client: TestClient, auth_tokens: dict) -> dict:
    """Fixture creating a supplier and two medicines for purchase testing."""
    headers = _auth_header(auth_tokens["ADMIN"])

    # Create supplier
    sup_res = client.post(
        "/api/v1/masters/suppliers",
        json={
            "name": "Apollo Distributing Corp",
            "gstin": "07AAAAA1111A1Z5",
            "credit_days": 30,
        },
        headers=headers,
    )
    supplier_id = sup_res.json()["data"]["id"]

    # Create medicine 1 (Paracetamol 650mg, pack of 10)
    med1_res = client.post(
        "/api/v1/masters/medicines",
        json={
            "brand_name": "Dolo 650",
            "generic_salt": "Paracetamol 650mg",
            "dosage_form": "TABLET",
            "pack_size": 10,
            "hsn_code": "3004",
            "gst_rate": 12.0,
        },
        headers=headers,
    )
    medicine1_id = med1_res.json()["data"]["id"]

    # Create medicine 2 (Azithromycin 500mg, pack of 3)
    med2_res = client.post(
        "/api/v1/masters/medicines",
        json={
            "brand_name": "Azithral 500",
            "generic_salt": "Azithromycin 500mg",
            "dosage_form": "TABLET",
            "pack_size": 3,
            "hsn_code": "3004",
            "gst_rate": 12.0,
        },
        headers=headers,
    )
    medicine2_id = med2_res.json()["data"]["id"]

    return {
        "supplier_id": supplier_id,
        "medicine1_id": medicine1_id,
        "medicine2_id": medicine2_id,
    }


# ==============================================================================
# TESTS
# ==============================================================================

def test_migration_003_tables_and_idempotency(test_engine):
    """Verify Migration 003 creates all required tables and indexes idempotently."""
    with test_engine.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}

        assert "purchase_invoices" in tables
        assert "purchase_invoice_lines" in tables
        assert "medicine_batches" in tables
        assert "inventory_ledger" in tables
        assert "supplier_payable_ledger" in tables

        # Re-running migrations must return 0
        newly_applied = run_migrations(conn)
        assert newly_applied == 0


def test_draft_purchase_creation_and_no_stock_impact(client: TestClient, auth_tokens: dict, master_entities: dict):
    """Verify creating a draft purchase does NOT alter batch inventory or supplier payables."""
    admin_headers = _auth_header(auth_tokens["ADMIN"])
    sup_id = master_entities["supplier_id"]
    med_id = master_entities["medicine1_id"]

    payload = {
        "supplier_id": sup_id,
        "supplier_invoice_number": "INV-2026-001",
        "invoice_date": "2026-10-07",
        "discount_paise": 0,
        "lines": [
            {
                "medicine_id": med_id,
                "batch_number": "DL-101",
                "expiry_date": "2028-12-31",
                "pack_size": 10,
                "paid_quantity": 10,
                "free_quantity": 1,  # 10 + 1 free scheme
                "purchase_rate_paise": 10000,
                "mrp_paise": 15000,
                "discount_paise": 0,
                "gst_percentage": 12.0,
            }
        ],
    }

    res = client.post("/api/v1/purchases", json=payload, headers=admin_headers)
    assert res.status_code == 201
    inv = res.json()["data"]

    assert inv["status"] == "DRAFT"
    assert inv["supplier_invoice_number"] == "INV-2026-001"
    # Line calculation: paid 10 * 10000 = 100000 paise. GST 12% on 100000 = 12000 paise. Total = 112000 paise.
    assert inv["subtotal_paise"] == 100000
    assert inv["tax_amount_paise"] == 12000
    assert inv["grand_total_paise"] == 112000

    # Verify NO stock exists for this medicine yet
    batches_res = client.get(f"/api/v1/inventory/batches?medicine_id={med_id}", headers=admin_headers)
    assert batches_res.status_code == 200
    assert len(batches_res.json()["data"]["items"]) == 0

    stock_res = client.get("/api/v1/inventory/stock", headers=admin_headers)
    assert stock_res.status_code == 200
    item = next(i for i in stock_res.json()["data"]["items"] if i["medicine_id"] == med_id)
    assert item["total_stock_units"] == 0

    # Verify supplier current payable is still 0
    sup_res = client.get(f"/api/v1/masters/suppliers/{sup_id}", headers=admin_headers)
    assert sup_res.json()["data"]["current_payable_paise"] == 0


def test_post_purchase_atomic_stock_and_free_scheme(client: TestClient, auth_tokens: dict, master_entities: dict):
    """Verify posting a purchase creates batches, updates stock with free units, and credits supplier payable."""
    admin_headers = _auth_header(auth_tokens["ADMIN"])
    sup_id = master_entities["supplier_id"]
    med_id = master_entities["medicine1_id"]

    # 1. Create draft with 10 paid + 1 free (pack size 10)
    draft_res = client.post(
        "/api/v1/purchases",
        json={
            "supplier_id": sup_id,
            "supplier_invoice_number": "INV-2026-002",
            "invoice_date": "2026-10-07",
            "lines": [
                {
                    "medicine_id": med_id,
                    "batch_number": "DL-102",
                    "expiry_date": "2028-06-30",
                    "pack_size": 10,
                    "paid_quantity": 10,
                    "free_quantity": 1,
                    "purchase_rate_paise": 10000,
                    "mrp_paise": 15000,
                    "gst_percentage": 12.0,
                }
            ],
        },
        headers=admin_headers,
    )
    inv_id = draft_res.json()["data"]["id"]

    # 2. Post invoice atomically
    post_res = client.post(f"/api/v1/purchases/{inv_id}/post", headers=admin_headers)
    assert post_res.status_code == 200
    posted_inv = post_res.json()["data"]
    assert posted_inv["status"] == "POSTED"
    assert posted_inv["posted_at"] is not None

    # 3. Check stock: Total units = (10 + 1) * 10 = 110 base units!
    batches_res = client.get(f"/api/v1/inventory/batches?medicine_id={med_id}", headers=admin_headers)
    assert batches_res.status_code == 200
    batches = batches_res.json()["data"]["items"]
    assert len(batches) == 1
    batch = batches[0]
    assert batch["batch_number"] == "DL-102"
    assert batch["current_quantity"] == 110
    assert batch["available_packs"] == 11.0
    assert batch["mrp_paise"] == 15000
    assert batch["purchase_rate_paise"] == 10000

    # 4. Check stock summary endpoint
    stock_res = client.get("/api/v1/inventory/stock", headers=admin_headers)
    stock_item = next(i for i in stock_res.json()["data"]["items"] if i["medicine_id"] == med_id)
    assert stock_item["total_stock_units"] == 110
    assert stock_item["total_packs"] == 11.0
    assert stock_item["active_batches_count"] == 1

    # 5. Check supplier payable accrued
    sup_res = client.get(f"/api/v1/masters/suppliers/{sup_id}", headers=admin_headers)
    assert sup_res.json()["data"]["current_payable_paise"] == 112000

    # 6. Check supplier payables history ledger
    ledger_res = client.get(f"/api/v1/suppliers/{sup_id}/payables", headers=admin_headers)
    assert ledger_res.status_code == 200
    history = ledger_res.json()["data"]
    assert history["current_payable_paise"] == 112000
    assert len(history["entries"]) == 1
    entry = history["entries"][0]
    assert entry["entry_type"] == "CREDIT"
    assert entry["amount_paise"] == 112000
    assert entry["balance_paise"] == 112000


def test_cannot_post_twice_and_cannot_edit_posted(client: TestClient, auth_tokens: dict, master_entities: dict):
    """Verify posted purchases cannot be re-posted or modified."""
    admin_headers = _auth_header(auth_tokens["ADMIN"])
    sup_id = master_entities["supplier_id"]
    med_id = master_entities["medicine1_id"]

    draft_res = client.post(
        "/api/v1/purchases",
        json={
            "supplier_id": sup_id,
            "supplier_invoice_number": "INV-2026-003",
            "invoice_date": "2026-10-07",
            "lines": [
                {
                    "medicine_id": med_id,
                    "batch_number": "DL-103",
                    "expiry_date": "2028-05-31",
                    "pack_size": 10,
                    "paid_quantity": 5,
                    "purchase_rate_paise": 10000,
                    "mrp_paise": 15000,
                }
            ],
        },
        headers=admin_headers,
    )
    inv_id = draft_res.json()["data"]["id"]

    # Post once
    client.post(f"/api/v1/purchases/{inv_id}/post", headers=admin_headers)

    # Post second time -> 400 Bad Request
    repost_res = client.post(f"/api/v1/purchases/{inv_id}/post", headers=admin_headers)
    assert repost_res.status_code == 400
    assert "already posted" in repost_res.json()["detail"].lower()

    # Attempt to edit posted invoice -> 400 Bad Request
    edit_res = client.put(
        f"/api/v1/purchases/{inv_id}",
        json={"notes": "Attempting edit on posted bill"},
        headers=admin_headers,
    )
    assert edit_res.status_code == 400
    assert "cannot edit" in edit_res.json()["detail"].lower()


def test_duplicate_invoice_prevention(client: TestClient, auth_tokens: dict, master_entities: dict):
    """Verify duplicate invoice number for the same supplier is rejected."""
    admin_headers = _auth_header(auth_tokens["ADMIN"])
    sup_id = master_entities["supplier_id"]
    med_id = master_entities["medicine1_id"]

    payload = {
        "supplier_id": sup_id,
        "supplier_invoice_number": "UNIQUE-BILL-999",
        "invoice_date": "2026-10-07",
        "lines": [
            {
                "medicine_id": med_id,
                "batch_number": "DL-999",
                "expiry_date": "2028-10-31",
                "pack_size": 10,
                "paid_quantity": 2,
                "purchase_rate_paise": 5000,
                "mrp_paise": 7500,
            }
        ],
    }

    # First bill succeeds
    res1 = client.post("/api/v1/purchases", json=payload, headers=admin_headers)
    assert res1.status_code == 201

    # Second bill with same supplier + invoice number fails
    res2 = client.post("/api/v1/purchases", json=payload, headers=admin_headers)
    assert res2.status_code == 400
    assert "already exists for this supplier" in res2.json()["detail"].lower()


def test_multiple_batches_and_fefo_ordering(client: TestClient, auth_tokens: dict, master_entities: dict):
    """Verify multiple batches of the same medicine and FEFO ordering (earliest expiry first)."""
    admin_headers = _auth_header(auth_tokens["ADMIN"])
    sup_id = master_entities["supplier_id"]
    med_id = master_entities["medicine2_id"]  # Azithral 500

    # Inward two batches with different expiries:
    # Batch FAR: 2029-12-31
    # Batch NEAR: 2027-03-31
    res = client.post(
        "/api/v1/purchases",
        json={
            "supplier_id": sup_id,
            "supplier_invoice_number": "FEFO-BILL-001",
            "invoice_date": "2026-10-07",
            "lines": [
                {
                    "medicine_id": med_id,
                    "batch_number": "BATCH-FAR",
                    "expiry_date": "2029-12-31",
                    "pack_size": 3,
                    "paid_quantity": 10,
                    "purchase_rate_paise": 9000,
                    "mrp_paise": 12000,
                },
                {
                    "medicine_id": med_id,
                    "batch_number": "BATCH-NEAR",
                    "expiry_date": "2027-03-31",
                    "pack_size": 3,
                    "paid_quantity": 5,
                    "purchase_rate_paise": 9000,
                    "mrp_paise": 12000,
                },
            ],
        },
        headers=admin_headers,
    )
    inv_id = res.json()["data"]["id"]
    client.post(f"/api/v1/purchases/{inv_id}/post", headers=admin_headers)

    # Query batches for medicine
    batches_res = client.get(f"/api/v1/inventory/batches?medicine_id={med_id}", headers=admin_headers)
    batches = batches_res.json()["data"]["items"]
    assert len(batches) == 2

    # FEFO check: BATCH-NEAR must be returned FIRST
    assert batches[0]["batch_number"] == "BATCH-NEAR"
    assert batches[0]["expiry_date"] == "2027-03-31"
    assert batches[0]["current_quantity"] == 15  # 5 packs * 3

    assert batches[1]["batch_number"] == "BATCH-FAR"
    assert batches[1]["expiry_date"] == "2029-12-31"
    assert batches[1]["current_quantity"] == 30  # 10 packs * 3


def test_negative_stock_prevention_at_database_level(test_engine):
    """Verify database CHECK constraints strictly reject negative current_quantity."""
    with test_engine.get_connection() as conn:
        cursor = conn.cursor()

        # Attempt to insert negative current_quantity into medicine_batches
        with pytest.raises(Exception):
            cursor.execute(
                """
                INSERT INTO medicine_batches (
                    medicine_id, batch_number, expiry_date, mrp_paise, purchase_rate_paise, pack_size,
                    current_quantity, reserved_quantity, is_active, created_at, updated_at
                ) VALUES (1, 'NEG-BATCH', '2028-12-31', 10000, 8000, 10, -5, 0, 1, '2026-10-07', '2026-10-07');
                """
            )

        # Attempt to insert negative quantity_balance into inventory_ledger
        with pytest.raises(Exception):
            cursor.execute(
                """
                INSERT INTO inventory_ledger (
                    medicine_id, batch_id, transaction_type, quantity_change, quantity_balance,
                    reference_type, reference_id, user_id, created_at
                ) VALUES (1, 1, 'SALE_DISPENSE', -10, -5, 'SALE_INVOICE', 1, 1, '2026-10-07');
                """
            )


def test_role_enforcement_purchases(client: TestClient, auth_tokens: dict, master_entities: dict):
    """Verify ADMIN and PHARMACIST can create/post purchases, while CASHIER is restricted to read-only."""
    admin_headers = _auth_header(auth_tokens["ADMIN"])
    pharm_headers = _auth_header(auth_tokens["PHARMACIST"])
    cashier_headers = _auth_header(auth_tokens["CASHIER"])
    sup_id = master_entities["supplier_id"]
    med_id = master_entities["medicine1_id"]

    purchase_payload = {
        "supplier_id": sup_id,
        "supplier_invoice_number": "ROLE-CHECK-001",
        "invoice_date": "2026-10-07",
        "lines": [
            {
                "medicine_id": med_id,
                "batch_number": "ROLE-B1",
                "expiry_date": "2028-12-31",
                "pack_size": 10,
                "paid_quantity": 2,
                "purchase_rate_paise": 5000,
                "mrp_paise": 7000,
            }
        ],
    }

    # 1. CASHIER attempting to create purchase -> 403 Forbidden
    cash_create = client.post("/api/v1/purchases", json=purchase_payload, headers=cashier_headers)
    assert cash_create.status_code == 403

    # 2. PHARMACIST creating purchase -> 201 Created
    pharm_create = client.post("/api/v1/purchases", json=purchase_payload, headers=pharm_headers)
    assert pharm_create.status_code == 201
    inv_id = pharm_create.json()["data"]["id"]

    # 3. CASHIER attempting to post purchase -> 403 Forbidden
    cash_post = client.post(f"/api/v1/purchases/{inv_id}/post", headers=cashier_headers)
    assert cash_post.status_code == 403

    # 4. CASHIER viewing purchases -> 200 OK
    cash_view = client.get(f"/api/v1/purchases/{inv_id}", headers=cashier_headers)
    assert cash_view.status_code == 200

    # 5. Unauthenticated user -> 401 Unauthorized
    unauth_res = client.get("/api/v1/purchases")
    assert unauth_res.status_code == 401


def test_purchase_validation_failures(client: TestClient, auth_tokens: dict, master_entities: dict):
    """Verify purchase validation rules reject expired dates, invalid GST, and zero quantities."""
    headers = _auth_header(auth_tokens["ADMIN"])
    sup_id = master_entities["supplier_id"]
    med_id = master_entities["medicine1_id"]

    # 1. Past/expired batch date
    bad_exp_res = client.post(
        "/api/v1/purchases",
        json={
            "supplier_id": sup_id,
            "supplier_invoice_number": "BAD-EXP",
            "invoice_date": "2026-10-07",
            "lines": [
                {
                    "medicine_id": med_id,
                    "batch_number": "OLD-01",
                    "expiry_date": "2020-01-01",  # Past date!
                    "pack_size": 10,
                    "paid_quantity": 5,
                    "purchase_rate_paise": 5000,
                    "mrp_paise": 7000,
                }
            ],
        },
        headers=headers,
    )
    assert bad_exp_res.status_code == 422
    assert "cannot be in the past" in str(bad_exp_res.json()).lower()

    # 2. Invalid GST percentage (e.g. 7.5%)
    bad_gst_res = client.post(
        "/api/v1/purchases",
        json={
            "supplier_id": sup_id,
            "supplier_invoice_number": "BAD-GST",
            "invoice_date": "2026-10-07",
            "lines": [
                {
                    "medicine_id": med_id,
                    "batch_number": "GST-01",
                    "expiry_date": "2028-12-31",
                    "pack_size": 10,
                    "paid_quantity": 5,
                    "purchase_rate_paise": 5000,
                    "mrp_paise": 7000,
                    "gst_percentage": 7.5,
                }
            ],
        },
        headers=headers,
    )
    assert bad_gst_res.status_code == 422
    assert "gst rate 7.5% is invalid" in str(bad_gst_res.json()).lower()

    # 3. Both paid and free quantities zero
    zero_qty_res = client.post(
        "/api/v1/purchases",
        json={
            "supplier_id": sup_id,
            "supplier_invoice_number": "ZERO-QTY",
            "invoice_date": "2026-10-07",
            "lines": [
                {
                    "medicine_id": med_id,
                    "batch_number": "ZERO-01",
                    "expiry_date": "2028-12-31",
                    "pack_size": 10,
                    "paid_quantity": 0,
                    "free_quantity": 0,
                    "purchase_rate_paise": 5000,
                    "mrp_paise": 7000,
                }
            ],
        },
        headers=headers,
    )
    assert zero_qty_res.status_code == 422
