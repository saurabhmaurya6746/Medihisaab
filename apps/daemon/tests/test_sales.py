"""Comprehensive automated test suite for Milestone 3: Sales & Billing POS.

Tests:
1. Successful cash sale (stock deduction, invoice, item lines, payment record, ledger entry)
2. UPI and Card sales
3. Split tender sale (combination of cash + UPI/card + change calculation)
4. Khata credit-limit validation and balance update
5. FEFO auto-selection (earliest non-expired batch picked first)
6. Manual batch selection override
7. Loose tablet deduction using fundamental units and pro-rata math
8. Expired batch rejection
9. Insufficient stock rejection
10. Inactive medicine rejection
11. Schedule H1 validation, RBAC enforcement, and immutable persistence
12. Held bill creation, listing, recall, and deletion
13. Atomic rollback on checkout failure
14. Substitute medicine search by generic salt and dosage form
15. Decoupled printing: printer error does not roll back committed sale
16. Sequential invoice number generation without duplicates
"""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from pharmacy_daemon.security.hashing import hash_password
from pharmacy_daemon.printing.service import default_printer_service


@pytest.fixture
def auth_tokens(client: TestClient) -> dict:
    """Setup admin, pharmacist, and cashier users, and return JWT authorization headers."""
    setup_payload = {
        "username": "pos_admin",
        "full_name": "POS Admin Owner",
        "password": "AdminPassword123!",
        "confirm_password": "AdminPassword123!",
        "pin": "1234",
        "store_name": "Apex POS Chemist",
    }
    setup_res = client.post("/api/v1/auth/first-run-setup", json=setup_payload)
    admin_token = setup_res.json()["access_token"]

    app = client.app
    engine = app.state.db_engine
    with engine.get_connection() as conn:
        cursor = conn.cursor()
        pwd_hash = hash_password("OperatorPass123!")
        cursor.execute(
            """
            INSERT INTO users (username, full_name, password_hash, pin_hash, role, is_active, created_at, updated_at)
            VALUES ('pos_pharm', 'Dispensing Pharmacist', ?, NULL, 'PHARMACIST', 1, '2026-10-08T00:00:00Z', '2026-10-08T00:00:00Z');
            """,
            (pwd_hash,),
        )
        cursor.execute(
            """
            INSERT INTO users (username, full_name, password_hash, pin_hash, role, is_active, created_at, updated_at)
            VALUES ('pos_cashier', 'Counter Cashier', ?, NULL, 'CASHIER', 1, '2026-10-08T00:00:00Z', '2026-10-08T00:00:00Z');
            """,
            (pwd_hash,),
        )
        conn.commit()

    pharm_res = client.post("/api/v1/auth/login", json={"username": "pos_pharm", "password": "OperatorPass123!"})
    pharm_token = pharm_res.json()["access_token"]

    cashier_res = client.post("/api/v1/auth/login", json={"username": "pos_cashier", "password": "OperatorPass123!"})
    cashier_token = cashier_res.json()["access_token"]

    return {
        "admin": {"Authorization": f"Bearer {admin_token}"},
        "pharmacist": {"Authorization": f"Bearer {pharm_token}"},
        "cashier": {"Authorization": f"Bearer {cashier_token}"},
    }


@pytest.fixture
def pos_setup(client: TestClient, auth_tokens: dict) -> dict:
    """Fixture creating catalog medicines, batches with stock, and customer profiles."""
    admin_h = auth_tokens["admin"]

    # 1. Normal Medicine (Paracetamol 500mg, pack_size=10, 12% GST)
    res_m1 = client.post(
        "/api/v1/masters/medicines",
        json={
            "brand_name": "Calpol 500",
            "generic_salt": "Paracetamol 500mg",
            "dosage_form": "TABLET",
            "pack_size": 10,
            "gst_rate": 12.0,
            "is_schedule_h1": False,
            "barcode": "8901234567890",
        },
        headers=admin_h,
    )
    m1_id = res_m1.json()["data"]["id"]

    # 2. Substitute Medicine (Dolo 500, same salt & dosage form, pack_size=10, 12% GST)
    res_m2 = client.post(
        "/api/v1/masters/medicines",
        json={
            "brand_name": "Dolo 500",
            "generic_salt": "Paracetamol 500mg",
            "dosage_form": "TABLET",
            "pack_size": 10,
            "gst_rate": 12.0,
            "is_schedule_h1": False,
        },
        headers=admin_h,
    )
    m2_id = res_m2.json()["data"]["id"]

    # 3. Schedule H1 Medicine (Azithromycin 500mg, pack_size=3, 12% GST, H1=True)
    res_h1 = client.post(
        "/api/v1/masters/medicines",
        json={
            "brand_name": "Azee 500",
            "generic_salt": "Azithromycin 500mg",
            "dosage_form": "TABLET",
            "pack_size": 3,
            "gst_rate": 12.0,
            "is_schedule_h1": True,
        },
        headers=admin_h,
    )
    h1_id = res_h1.json()["data"]["id"]

    # 4. Inactive Medicine
    res_inact = client.post(
        "/api/v1/masters/medicines",
        json={
            "brand_name": "Discontinued Med",
            "generic_salt": "Old Compound",
            "dosage_form": "TABLET",
            "pack_size": 10,
            "gst_rate": 12.0,
        },
        headers=admin_h,
    )
    inact_id = res_inact.json()["data"]["id"]
    client.delete(f"/api/v1/masters/medicines/{inact_id}", headers=admin_h)

    # Inward batches directly in DB with stock
    app = client.app
    engine = app.state.db_engine
    with engine.get_connection() as conn:
        cursor = conn.cursor()
        now_str = datetime.now(timezone.utc).isoformat()

        # Calpol 500 - Batch A (Expires 2027-12-31, 100 units = 10 strips, MRP 10000 paise = ₹100/strip)
        cursor.execute(
            """
            INSERT INTO medicine_batches (medicine_id, batch_number, expiry_date, mrp_paise, purchase_rate_paise, pack_size, current_quantity, is_active, created_at, updated_at)
            VALUES (?, 'CAL-B1', '2027-12-31', 10000, 7000, 10, 100, 1, ?, ?);
            """,
            (m1_id, now_str, now_str),
        )
        b_cal_1 = cursor.lastrowid

        # Calpol 500 - Batch B (Expires earlier: 2027-06-30, 50 units, MRP 10000 paise) -> Should be FEFO prioritized!
        cursor.execute(
            """
            INSERT INTO medicine_batches (medicine_id, batch_number, expiry_date, mrp_paise, purchase_rate_paise, pack_size, current_quantity, is_active, created_at, updated_at)
            VALUES (?, 'CAL-B2', '2027-06-30', 10000, 7000, 10, 50, 1, ?, ?);
            """,
            (m1_id, now_str, now_str),
        )
        b_cal_fefo = cursor.lastrowid

        # Calpol 500 - Expired Batch (Expired 2024-01-01, 20 units)
        cursor.execute(
            """
            INSERT INTO medicine_batches (medicine_id, batch_number, expiry_date, mrp_paise, purchase_rate_paise, pack_size, current_quantity, is_active, created_at, updated_at)
            VALUES (?, 'CAL-EXP', '2024-01-01', 10000, 7000, 10, 20, 1, ?, ?);
            """,
            (m1_id, now_str, now_str),
        )
        b_cal_exp = cursor.lastrowid

        # Dolo 500 (Substitute) - Batch (Expires 2028-05-31, 80 units, MRP 12000 paise = ₹120/strip)
        cursor.execute(
            """
            INSERT INTO medicine_batches (medicine_id, batch_number, expiry_date, mrp_paise, purchase_rate_paise, pack_size, current_quantity, is_active, created_at, updated_at)
            VALUES (?, 'DOLO-01', '2028-05-31', 12000, 8000, 10, 80, 1, ?, ?);
            """,
            (m2_id, now_str, now_str),
        )
        b_dolo = cursor.lastrowid

        # Azee 500 (Schedule H1) - Batch (Expires 2028-10-31, 30 units = 10 strips of 3, MRP 9000 paise = ₹90/strip of 3)
        cursor.execute(
            """
            INSERT INTO medicine_batches (medicine_id, batch_number, expiry_date, mrp_paise, purchase_rate_paise, pack_size, current_quantity, is_active, created_at, updated_at)
            VALUES (?, 'AZEE-01', '2028-10-31', 9000, 6000, 3, 30, 1, ?, ?);
            """,
            (h1_id, now_str, now_str),
        )
        b_azee = cursor.lastrowid

        conn.commit()

    # 5. Customer with Khata limit (Credit Limit: ₹1,000 = 100,000 paise)
    cust_res = client.post(
        "/api/v1/masters/customers",
        json={
            "name": "Ramesh Kumar",
            "phone": "9876543210",
            "address": "42 Ring Road",
            "credit_limit_paise": 100000,
        },
        headers=admin_h,
    )
    cust_id = cust_res.json()["data"]["id"]

    return {
        "m1_id": m1_id,
        "m2_id": m2_id,
        "h1_id": h1_id,
        "inact_id": inact_id,
        "b_cal_1": b_cal_1,
        "b_cal_fefo": b_cal_fefo,
        "b_cal_exp": b_cal_exp,
        "b_dolo": b_dolo,
        "b_azee": b_azee,
        "cust_id": cust_id,
    }


# ==============================================================================
# TESTS
# ==============================================================================

def test_successful_cash_sale(client: TestClient, auth_tokens: dict, pos_setup: dict):
    """Test standard counter sale with CASH tender, stock deduction, and ledger logging."""
    m1_id = pos_setup["m1_id"]
    cashier_h = auth_tokens["cashier"]

    # Sell 10 units (1 pack). Unit MRP = 1000 paise. Total = 10,000 paise = ₹100.00
    checkout_payload = {
        "customer_name": "Walk-in Patient",
        "customer_phone": "9998887776",
        "lines": [
            {
                "medicine_id": m1_id,
                "quantity_units": 10,
                "discount_percent": 0.0,
            }
        ],
        "payment_mode": "CASH",
        "cash_tendered_paise": 15000,  # ₹150 tendered
    }

    res = client.post("/api/v1/sales/checkout", json=checkout_payload, headers=cashier_h)
    assert res.status_code == 201
    data = res.json()["data"]

    assert data["invoice_no"].startswith("INV/")
    assert data["grand_total_paise"] == 10000
    assert data["cash_tendered_paise"] == 15000
    assert data["change_returned_paise"] == 5000  # ₹50 change
    assert len(data["items"]) == 1
    assert data["items"][0]["quantity_units"] == 10
    assert data["items"][0]["total_amount_paise"] == 10000

    # Verify inventory was deducted from earliest expiry batch (CAL-B2 had 50 units -> now 40)
    app = client.app
    with app.state.db_engine.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT current_quantity FROM medicine_batches WHERE id = ?;", (pos_setup["b_cal_fefo"],))
        assert cursor.fetchone()[0] == 40

        # Verify inventory ledger entry
        cursor.execute("SELECT * FROM inventory_ledger WHERE reference_id = ?;", (data["id"],))
        ledger_row = cursor.fetchone()
        assert ledger_row["transaction_type"] == "SALE_DISPENSE"
        assert ledger_row["quantity_change"] == -10
        assert ledger_row["quantity_balance"] == 40


def test_upi_and_card_sales(client: TestClient, auth_tokens: dict, pos_setup: dict):
    """Test digital cashless sales (UPI & CARD) with exact tender matching."""
    m1_id = pos_setup["m1_id"]
    cashier_h = auth_tokens["cashier"]

    # UPI sale
    upi_payload = {
        "lines": [{"medicine_id": m1_id, "quantity_units": 5}],
        "payment_mode": "UPI",
    }
    res_upi = client.post("/api/v1/sales/checkout", json=upi_payload, headers=cashier_h)
    assert res_upi.status_code == 201
    upi_data = res_upi.json()["data"]
    assert upi_data["payment_mode"] == "UPI"
    assert upi_data["grand_total_paise"] == 5000
    assert upi_data["cash_tendered_paise"] == 5000
    assert upi_data["change_returned_paise"] == 0

    # CARD sale
    card_payload = {
        "lines": [{"medicine_id": m1_id, "quantity_units": 5}],
        "payment_mode": "CARD",
    }
    res_card = client.post("/api/v1/sales/checkout", json=card_payload, headers=cashier_h)
    assert res_card.status_code == 201
    card_data = res_card.json()["data"]
    assert card_data["payment_mode"] == "CARD"
    assert card_data["grand_total_paise"] == 5000


def test_split_tender_sale(client: TestClient, auth_tokens: dict, pos_setup: dict):
    """Test multi-tender payment (e.g. ₹60 Cash + ₹40 UPI on ₹100 bill)."""
    m1_id = pos_setup["m1_id"]
    cashier_h = auth_tokens["cashier"]

    # 10 units = ₹100 (10,000 paise)
    split_payload = {
        "lines": [{"medicine_id": m1_id, "quantity_units": 10}],
        "payment_mode": "SPLIT",
        "payments": [
            {"payment_mode": "CASH", "amount_paise": 6000},
            {"payment_mode": "UPI", "amount_paise": 4000, "reference_note": "UPI/987123"},
        ],
        "cash_tendered_paise": 10000,  # ₹100 cash given for the ₹60 cash portion
    }

    res = client.post("/api/v1/sales/checkout", json=split_payload, headers=cashier_h)
    assert res.status_code == 201
    data = res.json()["data"]
    assert data["grand_total_paise"] == 10000
    assert data["cash_tendered_paise"] == 10000
    assert data["change_returned_paise"] == 4000  # ₹40 cash change returned
    assert len(data["payments"]) == 2


def test_khata_sale_and_credit_limit_validation(client: TestClient, auth_tokens: dict, pos_setup: dict):
    """Test customer credit account sale and blocking when limit is exceeded."""
    m1_id = pos_setup["m1_id"]
    cust_id = pos_setup["cust_id"]
    cashier_h = auth_tokens["cashier"]

    # Customer credit limit is ₹1,000.00 (100,000 paise).
    # 1. Successful sale of ₹500 (50,000 paise = 50 units)
    res_ok = client.post(
        "/api/v1/sales/checkout",
        json={
            "customer_id": cust_id,
            "lines": [{"medicine_id": m1_id, "quantity_units": 20}],  # 20 * 1000 = 20,000 paise
            "payment_mode": "KHATA",
        },
        headers=cashier_h,
    )
    assert res_ok.status_code == 201

    # Verify customer balance incremented
    app = client.app
    with app.state.db_engine.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT current_balance_paise FROM customers WHERE id = ?;", (cust_id,))
        assert cursor.fetchone()[0] == 20000

    # 2. Exceed credit limit: Customer already has ₹200 balance, limit is ₹1,000.
    # CAL-B1 has 100 units available. Attempt to buy 90 units (90,000 paise):
    # 20,000 + 90,000 = 110,000 > 100,000 limit -> Should REJECT on credit limit!
    b_cal_1 = pos_setup["b_cal_1"]
    res_exceed = client.post(
        "/api/v1/sales/checkout",
        json={
            "customer_id": cust_id,
            "lines": [{"medicine_id": m1_id, "batch_id": b_cal_1, "quantity_units": 90}],
            "payment_mode": "KHATA",
        },
        headers=cashier_h,
    )
    assert res_exceed.status_code == 422
    assert "credit limit exceeded" in res_exceed.json()["detail"].lower()


def test_fefo_auto_selection(client: TestClient, auth_tokens: dict, pos_setup: dict):
    """Test that FEFO auto-selection chooses the earliest non-expired batch."""
    m1_id = pos_setup["m1_id"]
    cashier_h = auth_tokens["cashier"]

    # Calpol has CAL-B2 (2027-06-30) and CAL-B1 (2027-12-31).
    # Omit batch_id -> system MUST choose CAL-B2 (earliest expiry)
    res = client.post(
        "/api/v1/sales/draft-calculate",
        json={"lines": [{"medicine_id": m1_id, "quantity_units": 5}]},
        headers=cashier_h,
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["lines"][0]["batch_id"] == pos_setup["b_cal_fefo"]
    assert data["lines"][0]["batch_number"] == "CAL-B2"


def test_manual_batch_selection(client: TestClient, auth_tokens: dict, pos_setup: dict):
    """Test cashier manual batch selection override (F2)."""
    m1_id = pos_setup["m1_id"]
    b_cal_1 = pos_setup["b_cal_1"]  # CAL-B1
    cashier_h = auth_tokens["cashier"]

    # Explicitly pick CAL-B1
    res = client.post(
        "/api/v1/sales/checkout",
        json={
            "lines": [{"medicine_id": m1_id, "batch_id": b_cal_1, "quantity_units": 10}],
            "payment_mode": "CASH",
            "cash_tendered_paise": 10000,
        },
        headers=cashier_h,
    )
    assert res.status_code == 201
    data = res.json()["data"]
    assert data["items"][0]["batch_id"] == b_cal_1
    assert data["items"][0]["batch_number"] == "CAL-B1"


def test_loose_tablet_deduction(client: TestClient, auth_tokens: dict, pos_setup: dict):
    """Test loose tablet strip cutting (fractional dispensing) using fundamental units."""
    m1_id = pos_setup["m1_id"]
    cashier_h = auth_tokens["cashier"]

    # Strip size is 10, MRP is ₹100 (10,000 paise).
    # Selling 3 loose tablets: pro-rata unit MRP = 1,000 paise.
    # Total = 3,000 paise = ₹30.00.
    res = client.post(
        "/api/v1/sales/checkout",
        json={
            "lines": [{"medicine_id": m1_id, "quantity_units": 3}],
            "payment_mode": "CASH",
            "cash_tendered_paise": 3000,
        },
        headers=cashier_h,
    )
    assert res.status_code == 201
    data = res.json()["data"]
    assert data["grand_total_paise"] == 3000
    assert data["items"][0]["quantity_units"] == 3
    assert data["items"][0]["unit_mrp_paise"] == 1000


def test_expired_batch_rejection(client: TestClient, auth_tokens: dict, pos_setup: dict):
    """Verify expired batches are strictly rejected at checkout."""
    m1_id = pos_setup["m1_id"]
    b_exp = pos_setup["b_cal_exp"]
    cashier_h = auth_tokens["cashier"]

    res = client.post(
        "/api/v1/sales/checkout",
        json={
            "lines": [{"medicine_id": m1_id, "batch_id": b_exp, "quantity_units": 1}],
            "payment_mode": "CASH",
            "cash_tendered_paise": 1000,
        },
        headers=cashier_h,
    )
    assert res.status_code == 422
    assert "expired" in res.json()["detail"].lower()


def test_insufficient_stock_rejection(client: TestClient, auth_tokens: dict, pos_setup: dict):
    """Verify checkout rejects when requested quantity exceeds available stock."""
    m1_id = pos_setup["m1_id"]
    cashier_h = auth_tokens["cashier"]

    # Request 9999 units (far exceeding stock)
    res = client.post(
        "/api/v1/sales/checkout",
        json={
            "lines": [{"medicine_id": m1_id, "quantity_units": 9999}],
            "payment_mode": "CASH",
            "cash_tendered_paise": 9999000,
        },
        headers=cashier_h,
    )
    assert res.status_code == 422
    assert "insufficient" in res.json()["detail"].lower() or "stock" in res.json()["detail"].lower()


def test_inactive_medicine_rejection(client: TestClient, auth_tokens: dict, pos_setup: dict):
    """Verify deactivated medicines cannot be billed."""
    inact_id = pos_setup["inact_id"]
    cashier_h = auth_tokens["cashier"]

    res = client.post(
        "/api/v1/sales/checkout",
        json={
            "lines": [{"medicine_id": inact_id, "quantity_units": 1}],
            "payment_mode": "CASH",
            "cash_tendered_paise": 1000,
        },
        headers=cashier_h,
    )
    assert res.status_code == 400
    assert "deactivated" in res.json()["detail"].lower() or "cannot be sold" in res.json()["detail"].lower()


def test_schedule_h1_validation_and_persistence(client: TestClient, auth_tokens: dict, pos_setup: dict):
    """Test Schedule H1 drug statutory prompt, rejection on missing data, and immutable record."""
    h1_id = pos_setup["h1_id"]
    pharm_h = auth_tokens["pharmacist"]

    # 1. Rejection when Schedule H1 details missing
    res_fail = client.post(
        "/api/v1/sales/checkout",
        json={
            "lines": [{"medicine_id": h1_id, "quantity_units": 3}],
            "payment_mode": "CASH",
            "cash_tendered_paise": 9000,
        },
        headers=pharm_h,
    )
    assert res_fail.status_code == 422
    assert "schedule h1" in res_fail.json()["detail"].lower()

    # 2. Success with statutory patient and doctor data
    res_ok = client.post(
        "/api/v1/sales/checkout",
        json={
            "lines": [
                {
                    "medicine_id": h1_id,
                    "quantity_units": 3,
                    "schedule_h1": {
                        "patient_name": "Anita Sharma",
                        "patient_address": "Flat 302, Green Enclave",
                        "doctor_name": "Dr. V. K. Gupta",
                        "doctor_address": "City Hospital Clinic",
                    },
                }
            ],
            "payment_mode": "CASH",
            "cash_tendered_paise": 9000,
        },
        headers=pharm_h,
    )
    assert res_ok.status_code == 201
    data = res_ok.json()["data"]
    item = data["items"][0]
    assert item["is_schedule_h1"] is True
    assert item["schedule_h1_record"] is not None
    assert item["schedule_h1_record"]["patient_name"] == "Anita Sharma"
    assert item["schedule_h1_record"]["doctor_name"] == "Dr. V. K. Gupta"

    # Verify immutable database record in schedule_h1_records
    app = client.app
    with app.state.db_engine.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM schedule_h1_records WHERE patient_name = 'Anita Sharma';")
        h1_row = cursor.fetchone()
        assert h1_row is not None
        assert h1_row["medicine_name"] == "Azee 500"


def test_schedule_h1_rbac_permission_enforcement(client: TestClient, auth_tokens: dict, pos_setup: dict):
    """Cashier lacks DISPENSE_SCHEDULE_H1 permission and must be rejected with 403."""
    h1_id = pos_setup["h1_id"]
    cashier_h = auth_tokens["cashier"]

    res = client.post(
        "/api/v1/sales/checkout",
        json={
            "lines": [
                {
                    "medicine_id": h1_id,
                    "quantity_units": 3,
                    "schedule_h1": {
                        "patient_name": "Anita Sharma",
                        "patient_address": "Flat 302",
                        "doctor_name": "Dr. Gupta",
                    },
                }
            ],
            "payment_mode": "CASH",
            "cash_tendered_paise": 9000,
        },
        headers=cashier_h,
    )
    assert res.status_code == 403
    assert "schedule h1" in res.json()["detail"].lower()


def test_held_bill_hold_and_recall(client: TestClient, auth_tokens: dict, pos_setup: dict):
    """Test multi-cart park (Ctrl+H), list, recall (Ctrl+R), and checkout."""
    m1_id = pos_setup["m1_id"]
    cashier_h = auth_tokens["cashier"]

    # 1. Park / Hold a bill
    held_payload = {
        "hold_reference": "PARK-01",
        "customer_name": "Waiting Customer",
        "items": [
            {
                "medicine_id": m1_id,
                "medicine_name": "Calpol 500",
                "quantity_units": 10,
                "unit_rate_paise": 1000,
                "total_amount_paise": 10000,
            }
        ],
        "notes": "Left wallet in car",
    }
    res_hold = client.post("/api/v1/sales/held-bills", json=held_payload, headers=cashier_h)
    assert res_hold.status_code == 201
    held_id = res_hold.json()["data"]["id"]

    # 2. List held bills
    res_list = client.post("/api/v1/sales/held-bills", headers=cashier_h)  # Wait, list is GET
    res_list = client.get("/api/v1/sales/held-bills", headers=cashier_h)
    assert res_list.status_code == 200
    held_items = res_list.json()["data"]
    assert any(h["id"] == held_id for h in held_items)

    # 3. Recall specific held bill
    res_get = client.get(f"/api/v1/sales/held-bills/{held_id}", headers=cashier_h)
    assert res_get.status_code == 200
    assert res_get.json()["data"]["hold_reference"] == "PARK-01"

    # 4. Convert held bill to committed sale (held_bill_id passed to checkout)
    res_commit = client.post(
        "/api/v1/sales/checkout",
        json={
            "lines": [{"medicine_id": m1_id, "quantity_units": 10}],
            "payment_mode": "CASH",
            "cash_tendered_paise": 10000,
            "held_bill_id": held_id,
        },
        headers=cashier_h,
    )
    assert res_commit.status_code == 201

    # Verify held bill was automatically deleted upon successful checkout
    res_after = client.get(f"/api/v1/sales/held-bills/{held_id}", headers=cashier_h)
    assert res_after.status_code == 404


def test_atomic_rollback_on_checkout_failure(client: TestClient, auth_tokens: dict, pos_setup: dict):
    """Verify that if any line fails mid-transaction, the entire checkout rolls back."""
    m1_id = pos_setup["m1_id"]
    b_cal_1 = pos_setup["b_cal_1"]
    b_exp = pos_setup["b_cal_exp"]
    cashier_h = auth_tokens["cashier"]

    app = client.app
    with app.state.db_engine.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT current_quantity FROM medicine_batches WHERE id = ?;", (b_cal_1,))
        initial_stock = cursor.fetchone()[0]

    # Batch with 1 good item and 1 expired item -> MUST rollback completely
    fail_payload = {
        "lines": [
            {"medicine_id": m1_id, "batch_id": b_cal_1, "quantity_units": 5},
            {"medicine_id": m1_id, "batch_id": b_exp, "quantity_units": 1},
        ],
        "payment_mode": "CASH",
        "cash_tendered_paise": 6000,
    }
    res = client.post("/api/v1/sales/checkout", json=fail_payload, headers=cashier_h)
    assert res.status_code == 422

    # Verify stock was NOT deducted for the first valid line
    with app.state.db_engine.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT current_quantity FROM medicine_batches WHERE id = ?;", (b_cal_1,))
        assert cursor.fetchone()[0] == initial_stock


def test_substitute_medicine_search(client: TestClient, auth_tokens: dict, pos_setup: dict):
    """Test F3 substitute search returning in-stock alternatives with identical generic salt."""
    m1_id = pos_setup["m1_id"]
    cashier_h = auth_tokens["cashier"]

    # Calpol 500 has generic_salt 'Paracetamol 500mg'. Dolo 500 has identical salt and dosage form.
    res = client.get(f"/api/v1/sales/substitutes?medicine_id={m1_id}", headers=cashier_h)
    assert res.status_code == 200
    subs = res.json()["data"]
    assert len(subs) >= 1
    dolo_sub = next((s for s in subs if s["brand_name"] == "Dolo 500"), None)
    assert dolo_sub is not None
    assert dolo_sub["total_stock_units"] == 80
    assert dolo_sub["recommended_batch_number"] == "DOLO-01"


def test_printer_failure_does_not_affect_committed_sale(client: TestClient, auth_tokens: dict, pos_setup: dict):
    """Test that hardware printer offline/jam does NOT roll back or fail the committed transaction."""
    m1_id = pos_setup["m1_id"]
    cashier_h = auth_tokens["cashier"]

    # Temporarily monkeypatch printer service to raise an exception
    orig_print = default_printer_service.print_invoice

    def mock_broken_print(*args, **kwargs):
        raise RuntimeError("Hardware spooler paper jam / offline error!")

    default_printer_service.print_invoice = mock_broken_print
    try:
        res = client.post(
            "/api/v1/sales/checkout",
            json={
                "lines": [{"medicine_id": m1_id, "quantity_units": 5}],
                "payment_mode": "CASH",
                "cash_tendered_paise": 5000,
            },
            headers=cashier_h,
        )
        # Even with printer crashing, sale must be committed successfully!
        assert res.status_code == 201
        assert res.json()["data"]["invoice_no"].startswith("INV/")
    finally:
        default_printer_service.print_invoice = orig_print


def test_sequential_invoice_number_generation(client: TestClient, auth_tokens: dict, pos_setup: dict):
    """Test that consecutive sales receive sequential numbers (INV/2026-27/00001, 00002)."""
    m1_id = pos_setup["m1_id"]
    cashier_h = auth_tokens["cashier"]

    res1 = client.post(
        "/api/v1/sales/checkout",
        json={
            "lines": [{"medicine_id": m1_id, "quantity_units": 1}],
            "payment_mode": "CASH",
            "cash_tendered_paise": 1000,
        },
        headers=cashier_h,
    )
    inv1 = res1.json()["data"]["invoice_no"]

    res2 = client.post(
        "/api/v1/sales/checkout",
        json={
            "lines": [{"medicine_id": m1_id, "quantity_units": 1}],
            "payment_mode": "CASH",
            "cash_tendered_paise": 1000,
        },
        headers=cashier_h,
    )
    inv2 = res2.json()["data"]["invoice_no"]

    # Ensure sequence increments
    seq1 = int(inv1.split("/")[-1])
    seq2 = int(inv2.split("/")[-1])
    assert seq2 == seq1 + 1
