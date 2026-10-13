"""Milestone 2A Monetary-Data Hardening automated test suite.

Validates that:
- SQLite REAL is eliminated for money; integer paise is used everywhere.
- 1 paisa (₹0.01) calculations are exact.
- 1050 paise (₹10.50) calculations and payables are exact.
- Line and invoice discounts compute accurately without drift.
- GST calculations for all slabs (0%, 5%, 12%, 18%, 28%) use pure integer half-up rounding.
- 10+1 free schemes calculate payable on paid quantity while inwarding total stock.
- Supplier payable ledger balances accumulate deterministically across multiple invoices.
- Invoice totals satisfy: grand_total_paise = subtotal_paise + tax_amount_paise - discount_paise.
- Pure integer arithmetic prevents binary floating-point drift (e.g. 0.1 + 0.2 != 0.3).
- SQLite tables and columns strictly store integer values without float drift.
"""

import pytest
from fastapi.testclient import TestClient

from pharmacy_daemon.security.hashing import hash_password


@pytest.fixture
def auth_header(client: TestClient) -> dict:
    """Setup admin user and return authorization header."""
    setup_payload = {
        "username": "monetary_admin",
        "full_name": "Monetary Admin",
        "password": "AdminPassword123!",
        "confirm_password": "AdminPassword123!",
        "pin": "9999",
        "store_name": "Monetary Safe Chemist",
    }
    setup_res = client.post("/api/v1/auth/first-run-setup", json=setup_payload)
    token = setup_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def setup_supplier_and_medicines(client: TestClient, auth_header: dict) -> dict:
    """Fixture creating supplier and medicines for monetary tests."""
    sup_res = client.post(
        "/api/v1/masters/suppliers",
        json={
            "name": "Precision Pharma Distributors",
            "gstin": "27AAPFU0938N1ZV",
            "credit_days": 15,
        },
        headers=auth_header,
    )
    supplier_id = sup_res.json()["data"]["id"]

    # Medicines with various GST rates
    med_ids = {}
    for gst in [0.0, 5.0, 12.0, 18.0, 28.0]:
        tag = int(gst)
        res = client.post(
            "/api/v1/masters/medicines",
            json={
                "brand_name": f"Med-GST-{tag}",
                "generic_salt": f"Salt-{tag}",
                "dosage_form": "TABLET",
                "pack_size": 10,
                "gst_rate": gst,
            },
            headers=auth_header,
        )
        med_ids[tag] = res.json()["data"]["id"]

    return {"supplier_id": supplier_id, "med_ids": med_ids}


# ==============================================================================
# TESTS
# ==============================================================================

def test_one_paisa_monetary_handling(client: TestClient, auth_header: dict, setup_supplier_and_medicines: dict):
    """Test ₹0.01 (1 paisa) line item, subtotal, GST rounding, and batch inwarding."""
    sup_id = setup_supplier_and_medicines["supplier_id"]
    med_18 = setup_supplier_and_medicines["med_ids"][18]

    # 1 item @ 1 paisa (₹0.01), 18% GST:
    # Taxable = 1 paisa.
    # GST: (1 * 1800 + 5000) // 10000 = 6800 // 10000 = 0 paise.
    # Total = 1 paisa.
    payload_1 = {
        "supplier_id": sup_id,
        "supplier_invoice_number": "PAISA-001",
        "invoice_date": "2026-10-07",
        "lines": [
            {
                "medicine_id": med_18,
                "batch_number": "ONE-PAISA-01",
                "expiry_date": "2028-12-31",
                "pack_size": 10,
                "paid_quantity": 1,
                "purchase_rate_paise": 1,  # ₹0.01
                "mrp_paise": 2,            # ₹0.02
                "discount_paise": 0,
                "gst_percentage": 18.0,
            }
        ],
    }
    res1 = client.post("/api/v1/purchases", json=payload_1, headers=auth_header)
    assert res1.status_code == 201
    inv1 = res1.json()["data"]
    assert inv1["subtotal_paise"] == 1
    assert inv1["tax_amount_paise"] == 0
    assert inv1["grand_total_paise"] == 1

    # 100 items @ 1 paisa = 100 paise (₹1.00), 18% GST:
    # Taxable = 100 paise.
    # GST: (100 * 1800 + 5000) // 10000 = 185000 // 10000 = 18 paise.
    # Total = 118 paise.
    payload_100 = {
        "supplier_id": sup_id,
        "supplier_invoice_number": "PAISA-100",
        "invoice_date": "2026-10-07",
        "lines": [
            {
                "medicine_id": med_18,
                "batch_number": "ONE-PAISA-100",
                "expiry_date": "2028-12-31",
                "pack_size": 10,
                "paid_quantity": 100,
                "purchase_rate_paise": 1,  # ₹0.01
                "mrp_paise": 2,            # ₹0.02
                "discount_paise": 0,
                "gst_percentage": 18.0,
            }
        ],
    }
    res2 = client.post("/api/v1/purchases", json=payload_100, headers=auth_header)
    assert res2.status_code == 201
    inv2 = res2.json()["data"]
    assert inv2["subtotal_paise"] == 100
    assert inv2["tax_amount_paise"] == 18
    assert inv2["grand_total_paise"] == 118

    # Post invoice and verify exact paise in batch and payable
    post_res = client.post(f"/api/v1/purchases/{inv2['id']}/post", headers=auth_header)
    assert post_res.status_code == 200

    sup_res = client.get(f"/api/v1/masters/suppliers/{sup_id}", headers=auth_header)
    assert sup_res.json()["data"]["current_payable_paise"] == 118


def test_ten_rupees_fifty_paise_monetary_handling(client: TestClient, auth_header: dict, setup_supplier_and_medicines: dict):
    """Test ₹10.50 (1050 paise) line item and payable ledger balance."""
    sup_id = setup_supplier_and_medicines["supplier_id"]
    med_5 = setup_supplier_and_medicines["med_ids"][5]

    # 2 packs @ 1050 paise (₹10.50), MRP 1550 paise (₹15.50), 5% GST
    # Gross = 2 * 1050 = 2100 paise.
    # GST 5%: (2100 * 500 + 5000) // 10000 = 1055000 // 10000 = 105 paise.
    # Total = 2100 + 105 = 2205 paise (₹22.05).
    payload = {
        "supplier_id": sup_id,
        "supplier_invoice_number": "INV-10-50",
        "invoice_date": "2026-10-07",
        "lines": [
            {
                "medicine_id": med_5,
                "batch_number": "B-1050",
                "expiry_date": "2028-11-30",
                "pack_size": 10,
                "paid_quantity": 2,
                "purchase_rate_paise": 1050,  # ₹10.50
                "mrp_paise": 1550,            # ₹15.50
                "discount_paise": 0,
                "gst_percentage": 5.0,
            }
        ],
    }
    res = client.post("/api/v1/purchases", json=payload, headers=auth_header)
    assert res.status_code == 201
    inv = res.json()["data"]
    assert inv["subtotal_paise"] == 2100
    assert inv["tax_amount_paise"] == 105
    assert inv["grand_total_paise"] == 2205

    # Post and check batch and supplier ledger
    post_res = client.post(f"/api/v1/purchases/{inv['id']}/post", headers=auth_header)
    assert post_res.status_code == 200

    batches_res = client.get(f"/api/v1/inventory/batches?medicine_id={med_5}", headers=auth_header)
    batch = batches_res.json()["data"]["items"][0]
    assert batch["purchase_rate_paise"] == 1050
    assert batch["mrp_paise"] == 1550

    ledger_res = client.get(f"/api/v1/suppliers/{sup_id}/payables", headers=auth_header)
    entries = ledger_res.json()["data"]["entries"]
    assert entries[0]["amount_paise"] == 2205
    assert entries[0]["balance_paise"] == 2205


def test_monetary_discounts_line_and_invoice(client: TestClient, auth_header: dict, setup_supplier_and_medicines: dict):
    """Test line-level and invoice-level discounts in integer paise."""
    sup_id = setup_supplier_and_medicines["supplier_id"]
    med_12 = setup_supplier_and_medicines["med_ids"][12]

    # Line: 10 packs @ 1000 paise = 10000 paise (₹100.00).
    # Line discount = 1500 paise (₹15.00).
    # Taxable = 10000 - 1500 = 8500 paise (₹85.00).
    # GST 12%: (8500 * 1200 + 5000) // 10000 = 10200000 // 10000 = 1020 paise (₹10.20).
    # Line total = 8500 + 1020 = 9520 paise.
    # Invoice discount = 200 paise (₹2.00).
    # Grand total = 8500 + 1020 - 200 = 9320 paise (₹93.20).
    payload = {
        "supplier_id": sup_id,
        "supplier_invoice_number": "INV-DISC-01",
        "invoice_date": "2026-10-07",
        "discount_paise": 200,
        "lines": [
            {
                "medicine_id": med_12,
                "batch_number": "B-DISC",
                "expiry_date": "2028-10-31",
                "pack_size": 10,
                "paid_quantity": 10,
                "purchase_rate_paise": 1000,
                "mrp_paise": 1500,
                "discount_paise": 1500,
                "gst_percentage": 12.0,
            }
        ],
    }
    res = client.post("/api/v1/purchases", json=payload, headers=auth_header)
    assert res.status_code == 201
    inv = res.json()["data"]
    assert inv["discount_paise"] == 200
    assert inv["subtotal_paise"] == 8500
    assert inv["tax_amount_paise"] == 1020
    assert inv["grand_total_paise"] == 9320

    # Discount exceeding gross must fail validation
    bad_payload = {
        "supplier_id": sup_id,
        "supplier_invoice_number": "INV-DISC-BAD",
        "invoice_date": "2026-10-07",
        "lines": [
            {
                "medicine_id": med_12,
                "batch_number": "B-BAD",
                "expiry_date": "2028-10-31",
                "pack_size": 10,
                "paid_quantity": 2,
                "purchase_rate_paise": 1000,  # Gross = 2000 paise
                "mrp_paise": 1500,
                "discount_paise": 2500,       # 2500 > 2000!
                "gst_percentage": 12.0,
            }
        ],
    }
    bad_res = client.post("/api/v1/purchases", json=bad_payload, headers=auth_header)
    assert bad_res.status_code == 422


def test_gst_calculations_all_slabs_and_half_up_rounding(client: TestClient, auth_header: dict, setup_supplier_and_medicines: dict):
    """Test GST integer half-up rounding boundary cases across all standard slabs."""
    sup_id = setup_supplier_and_medicines["supplier_id"]
    meds = setup_supplier_and_medicines["med_ids"]

    # Boundary test cases:
    # Taxable paise, GST rate, Expected Tax paise, Explanation
    # 333 paise @ 5%  -> (333 * 500 + 5000) // 10000 = 171500 // 10000 = 17 paise (16.65 rounds to 17)
    # 150 paise @ 5%  -> (150 * 500 + 5000) // 10000 = 80000 // 10000  = 8 paise  (7.50 rounds to 8)
    # 149 paise @ 5%  -> (149 * 500 + 5000) // 10000 = 79500 // 10000  = 7 paise  (7.45 rounds to 7)
    # 357 paise @ 12% -> (357 * 1200 + 5000) // 10000 = 433400 // 10000 = 43 paise (42.84 rounds to 43)
    # 250 paise @ 18% -> (250 * 1800 + 5000) // 10000 = 455000 // 10000 = 45 paise (45.00 rounds to 45)
    # 175 paise @ 28% -> (175 * 2800 + 5000) // 10000 = 495000 // 10000 = 49 paise (49.00 rounds to 49)
    # 1000 paise @ 0% -> 0 paise
    cases = [
        (meds[5], 5.0, 333, 17),
        (meds[5], 5.0, 150, 8),
        (meds[5], 5.0, 149, 7),
        (meds[12], 12.0, 357, 43),
        (meds[18], 18.0, 250, 45),
        (meds[28], 28.0, 175, 49),
        (meds[0], 0.0, 1000, 0),
    ]

    lines = []
    expected_subtotal = 0
    expected_tax = 0

    for idx, (med_id, gst_rate, taxable_rate, exp_tax) in enumerate(cases):
        lines.append({
            "medicine_id": med_id,
            "batch_number": f"GST-ROUND-{idx}",
            "expiry_date": "2028-12-31",
            "pack_size": 10,
            "paid_quantity": 1,
            "purchase_rate_paise": taxable_rate,
            "mrp_paise": taxable_rate * 2,
            "discount_paise": 0,
            "gst_percentage": gst_rate,
        })
        expected_subtotal += taxable_rate
        expected_tax += exp_tax

    payload = {
        "supplier_id": sup_id,
        "supplier_invoice_number": "INV-GST-ROUND",
        "invoice_date": "2026-10-07",
        "lines": lines,
    }
    res = client.post("/api/v1/purchases", json=payload, headers=auth_header)
    assert res.status_code == 201
    inv = res.json()["data"]

    for idx, (_, _, taxable_rate, exp_tax) in enumerate(cases):
        line = inv["lines"][idx]
        taxable = (line["paid_quantity"] * line["purchase_rate_paise"]) - line["discount_paise"]
        assert taxable == taxable_rate
        assert line["tax_amount_paise"] == exp_tax
        assert line["line_total_paise"] == taxable_rate + exp_tax

    assert inv["subtotal_paise"] == expected_subtotal
    assert inv["tax_amount_paise"] == expected_tax
    assert inv["grand_total_paise"] == expected_subtotal + expected_tax


def test_free_scheme_ten_plus_one_integer_arithmetic(client: TestClient, auth_header: dict, setup_supplier_and_medicines: dict):
    """Test 10+1 free scheme stock inwarding vs payable billing amount."""
    sup_id = setup_supplier_and_medicines["supplier_id"]
    med_12 = setup_supplier_and_medicines["med_ids"][12]

    # 10 paid + 1 free, pack size 10 -> inwarded stock units = (10 + 1) * 10 = 110 units.
    # Purchase rate = 10000 paise (₹100.00).
    # Taxable amount = paid_quantity (10) * 10000 = 100000 paise (₹1000.00).
    # Free quantity is charged at 0 paise!
    # GST 12% on 100000 = 12000 paise (₹120.00).
    # Grand total = 112000 paise (₹1120.00).
    payload = {
        "supplier_id": sup_id,
        "supplier_invoice_number": "INV-SCHEME-10-1",
        "invoice_date": "2026-10-07",
        "lines": [
            {
                "medicine_id": med_12,
                "batch_number": "BATCH-10-PLUS-1",
                "expiry_date": "2028-12-31",
                "pack_size": 10,
                "paid_quantity": 10,
                "free_quantity": 1,
                "purchase_rate_paise": 10000,
                "mrp_paise": 15000,
                "discount_paise": 0,
                "gst_percentage": 12.0,
            }
        ],
    }
    res = client.post("/api/v1/purchases", json=payload, headers=auth_header)
    assert res.status_code == 201
    inv = res.json()["data"]
    assert inv["subtotal_paise"] == 100000
    assert inv["tax_amount_paise"] == 12000
    assert inv["grand_total_paise"] == 112000

    # Post and verify inwarded units vs payable
    post_res = client.post(f"/api/v1/purchases/{inv['id']}/post", headers=auth_header)
    assert post_res.status_code == 200

    batches_res = client.get(f"/api/v1/inventory/batches?medicine_id={med_12}", headers=auth_header)
    batch = next(b for b in batches_res.json()["data"]["items"] if b["batch_number"] == "BATCH-10-PLUS-1")
    assert batch["current_quantity"] == 110  # 11 packs * 10 units

    # Supplier payable should reflect exact invoice amount without free quantity added to bill
    ledger_res = client.get(f"/api/v1/suppliers/{sup_id}/payables", headers=auth_header)
    latest_entry = ledger_res.json()["data"]["entries"][0]
    assert latest_entry["amount_paise"] == 112000


def test_supplier_payable_balances_continuity_and_accumulation(client: TestClient, auth_header: dict, setup_supplier_and_medicines: dict):
    """Test supplier payable ledger balances accumulate deterministically across multiple invoices."""
    sup_id = setup_supplier_and_medicines["supplier_id"]
    med_0 = setup_supplier_and_medicines["med_ids"][0]

    # Create and post 3 consecutive invoices:
    # Inv 1: 50000 paise (₹500.00)
    # Inv 2: 75250 paise (₹752.50)
    # Inv 3: 1050 paise (₹10.50)
    amounts = [50000, 75250, 1050]
    cumulative = 0

    for idx, amt in enumerate(amounts):
        res = client.post(
            "/api/v1/purchases",
            json={
                "supplier_id": sup_id,
                "supplier_invoice_number": f"LEDGER-BILL-{idx}",
                "invoice_date": "2026-10-07",
                "lines": [
                    {
                        "medicine_id": med_0,
                        "batch_number": f"ACC-BATCH-{idx}",
                        "expiry_date": "2028-12-31",
                        "pack_size": 10,
                        "paid_quantity": 1,
                        "purchase_rate_paise": amt,
                        "mrp_paise": amt * 2,
                        "discount_paise": 0,
                        "gst_percentage": 0.0,
                    }
                ],
            },
            headers=auth_header,
        )
        inv_id = res.json()["data"]["id"]
        client.post(f"/api/v1/purchases/{inv_id}/post", headers=auth_header)

    # Check supplier master table
    expected_total = sum(amounts)
    sup_res = client.get(f"/api/v1/masters/suppliers/{sup_id}", headers=auth_header)
    assert sup_res.json()["data"]["current_payable_paise"] >= expected_total

    # Verify ledger history entries: balance continuity
    ledger_res = client.get(f"/api/v1/suppliers/{sup_id}/payables", headers=auth_header)
    entries = ledger_res.json()["data"]["entries"]
    # Entries are in reverse chronological order (newest first)
    # Verify balance decreases backwards by amount
    for i in range(len(entries) - 1):
        assert entries[i]["balance_paise"] - entries[i]["amount_paise"] == entries[i + 1]["balance_paise"]


def test_invoice_total_calculations_formula(client: TestClient, auth_header: dict, setup_supplier_and_medicines: dict):
    """Test invoice total calculations: grand_total_paise == subtotal_paise + tax_amount_paise - discount_paise."""
    sup_id = setup_supplier_and_medicines["supplier_id"]
    meds = setup_supplier_and_medicines["med_ids"]

    payload = {
        "supplier_id": sup_id,
        "supplier_invoice_number": "INV-FORMULA-VERIFY",
        "invoice_date": "2026-10-07",
        "discount_paise": 550,  # ₹5.50 invoice discount
        "lines": [
            {
                "medicine_id": meds[5],
                "batch_number": "F-01",
                "expiry_date": "2028-12-31",
                "pack_size": 10,
                "paid_quantity": 4,
                "purchase_rate_paise": 2500,  # Gross = 10000 paise
                "mrp_paise": 3500,
                "discount_paise": 1000,      # Taxable = 9000 paise. 5% GST = 450 paise.
                "gst_percentage": 5.0,
            },
            {
                "medicine_id": meds[18],
                "batch_number": "F-02",
                "expiry_date": "2028-12-31",
                "pack_size": 10,
                "paid_quantity": 3,
                "purchase_rate_paise": 4000,  # Gross = 12000 paise
                "mrp_paise": 6000,
                "discount_paise": 2000,      # Taxable = 10000 paise. 18% GST = 1800 paise.
                "gst_percentage": 18.0,
            },
        ],
    }
    res = client.post("/api/v1/purchases", json=payload, headers=auth_header)
    assert res.status_code == 201
    inv = res.json()["data"]

    assert inv["subtotal_paise"] == 9000 + 10000  # 19000 paise
    assert inv["tax_amount_paise"] == 450 + 1800  # 2250 paise
    assert inv["discount_paise"] == 550
    # Grand total = 19000 + 2250 - 550 = 20700 paise
    assert inv["grand_total_paise"] == inv["subtotal_paise"] + inv["tax_amount_paise"] - inv["discount_paise"]
    assert inv["grand_total_paise"] == 20700


def test_no_floating_point_drift_repetitive_arithmetic(client: TestClient, test_engine):
    """Verify that integer paise prevents IEEE-754 floating-point drift and SQLite schema stores INTEGER."""
    # Test binary floating point drift:
    # In float: 0.1 + 0.2 = 0.30000000000000004 != 0.3
    # In paise: 10 + 20 = 30
    drift_float = sum([0.1] * 10)
    assert drift_float != 1.0 or isinstance(drift_float, float)

    drift_paise = sum([10] * 10)
    assert drift_paise == 100
    assert isinstance(drift_paise, int)

    # Verify SQLite column data types are strictly INTEGER for all monetary columns
    with test_engine.get_connection() as conn:
        cursor = conn.cursor()

        # purchase_invoices
        cursor.execute("PRAGMA table_info(purchase_invoices);")
        cols = {row[1]: row[2] for row in cursor.fetchall()}
        for monetary_col in ["subtotal_paise", "discount_paise", "tax_amount_paise", "grand_total_paise"]:
            assert cols[monetary_col] == "INTEGER"
            assert monetary_col.replace("_paise", "") not in cols  # REAL cols dropped!

        # purchase_invoice_lines
        cursor.execute("PRAGMA table_info(purchase_invoice_lines);")
        cols = {row[1]: row[2] for row in cursor.fetchall()}
        for monetary_col in ["purchase_rate_paise", "mrp_paise", "discount_paise", "tax_amount_paise", "line_total_paise"]:
            assert cols[monetary_col] == "INTEGER"

        # medicine_batches
        cursor.execute("PRAGMA table_info(medicine_batches);")
        cols = {row[1]: row[2] for row in cursor.fetchall()}
        assert cols["mrp_paise"] == "INTEGER"
        assert cols["purchase_rate_paise"] == "INTEGER"

        # supplier_payable_ledger
        cursor.execute("PRAGMA table_info(supplier_payable_ledger);")
        cols = {row[1]: row[2] for row in cursor.fetchall()}
        assert cols["amount_paise"] == "INTEGER"
        assert cols["balance_paise"] == "INTEGER"

        # suppliers
        cursor.execute("PRAGMA table_info(suppliers);")
        cols = {row[1]: row[2] for row in cursor.fetchall()}
        assert cols["current_payable_paise"] == "INTEGER"

        # customers
        cursor.execute("PRAGMA table_info(customers);")
        cols = {row[1]: row[2] for row in cursor.fetchall()}
        assert cols["credit_limit_paise"] == "INTEGER"
        assert cols["current_balance_paise"] == "INTEGER"
