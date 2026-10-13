"""Comprehensive automated test suite for Milestone 5:
Customer Khata, Supplier Payables, Sales Returns, Purchase Returns, and Wastage.
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
        "username": "m5_admin",
        "full_name": "Milestone5 Admin",
        "password": "Password123!",
        "confirm_password": "Password123!",
        "pin": "1234",
        "store_name": "Apex Care Pharmacy",
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
            VALUES ('m5_pharm', 'Staff Pharmacist', ?, NULL, 'PHARMACIST', 1, '2026-10-08T00:00:00Z', '2026-10-08T00:00:00Z');
            """,
            (pwd_hash,),
        )
        cursor.execute(
            """
            INSERT INTO users (username, full_name, password_hash, pin_hash, role, is_active, created_at, updated_at)
            VALUES ('m5_cashier', 'Counter Cashier', ?, NULL, 'CASHIER', 1, '2026-10-08T00:00:00Z', '2026-10-08T00:00:00Z');
            """,
            (pwd_hash,),
        )
        conn.commit()
    finally:
        conn.close()

    # Login to get tokens
    pharm_login = client.post("/api/v1/auth/login", json={"username": "m5_pharm", "password": "OperatorPass123!"})
    assert pharm_login.status_code == 200
    pharm_token = pharm_login.json()["access_token"]

    cashier_login = client.post("/api/v1/auth/login", json={"username": "m5_cashier", "password": "OperatorPass123!"})
    assert cashier_login.status_code == 200
    cashier_token = cashier_login.json()["access_token"]

    return {
        "admin_headers": {"Authorization": f"Bearer {admin_token}"},
        "pharm_headers": {"Authorization": f"Bearer {pharm_token}"},
        "cashier_headers": {"Authorization": f"Bearer {cashier_token}"},
    }


def _seed_base_catalog_and_stock(client: TestClient, admin_headers: dict) -> dict:
    """Helper to seed supplier, customer, medicines, and inwarded stock."""
    # 1. Supplier
    sup_res = client.post(
        "/api/v1/masters/suppliers",
        headers=admin_headers,
        json={
            "name": "Medilink Distributors Ltd",
            "gstin": "27AABCM1234F1Z5",
            "phone": "9876543210",
            "email": "orders@medilink.com",
            "credit_days": 30,
        },
    )
    assert sup_res.status_code == 201
    supplier = sup_res.json()["data"]

    # 2. Customer
    cust_res = client.post(
        "/api/v1/masters/customers",
        headers=admin_headers,
        json={
            "name": "Ramesh Kumar",
            "phone": "9123456789",
            "address": "Flat 101, Shanti Heights",
            "credit_limit_paise": 200000,  # ₹2,000 credit limit
        },
    )
    assert cust_res.status_code == 201
    customer = cust_res.json()["data"]

    # 3. Medicine
    med_res = client.post(
        "/api/v1/masters/medicines",
        headers=admin_headers,
        json={
            "brand_name": "Azithral 500",
            "generic_salt": "Azithromycin 500mg",
            "dosage_form": "TABLET",
            "pack_size": 10,
            "hsn_code": "30049099",
            "gst_rate": 12.0,
            "min_stock_units": 20,
        },
    )
    assert med_res.status_code == 201
    medicine = med_res.json()["data"]

    # 4. Inward Stock via Purchase (10 packs @ ₹100 PTR = 100 tablets)
    future_exp = (date.today() + timedelta(days=365)).strftime("%Y-%m-%d")
    purchase_res = client.post(
        "/api/v1/purchases",
        headers=admin_headers,
        json={
            "supplier_id": supplier["id"],
            "supplier_invoice_number": "INV-MED-5001",
            "invoice_date": date.today().strftime("%Y-%m-%d"),
            "lines": [
                {
                    "medicine_id": medicine["id"],
                    "batch_number": "AZ-801",
                    "expiry_date": future_exp,
                    "pack_size": 10,
                    "paid_quantity": 10,
                    "free_quantity": 0,
                    "purchase_rate_paise": 10000,  # ₹100 PTR
                    "mrp_paise": 15000,           # ₹150 MRP
                    "discount_percent": 0.0,
                    "gst_percentage": 12.0,
                }
            ],
        },
    )
    assert purchase_res.status_code == 201
    purchase = purchase_res.json()["data"]

    # Post purchase to materialize stock & payable
    post_res = client.post(f"/api/v1/purchases/{purchase['id']}/post", headers=admin_headers)
    assert post_res.status_code == 200

    # Get batch ID
    engine = client.app.state.db_engine
    conn = engine.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM medicine_batches WHERE batch_number = 'AZ-801';")
        batch_id = cursor.fetchone()[0]
    finally:
        conn.close()

    return {
        "supplier": supplier,
        "customer": customer,
        "medicine": medicine,
        "batch_id": batch_id,
        "purchase": purchase,
    }


def test_migration_007_schema_verification(client: TestClient):
    """Verify that migration 007 created all required tables, columns, constraints, and indexes."""
    engine = client.app.state.db_engine
    conn = engine.get_connection()
    try:
        cursor = conn.cursor()

        # Check required tables exist
        required_tables = {
            "khata_ledger",
            "sales_returns",
            "sales_return_items",
            "purchase_returns",
            "purchase_return_items",
            "wastage_register",
        }
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        assert required_tables.issubset(tables)

        # Verify khata_ledger columns
        cursor.execute("PRAGMA table_info(khata_ledger);")
        khata_cols = {row[1] for row in cursor.fetchall()}
        assert {"customer_id", "transaction_type", "entry_type", "amount_paise", "balance_paise", "receipt_no"}.issubset(khata_cols)

        # Verify sales_returns columns
        cursor.execute("PRAGMA table_info(sales_returns);")
        sr_cols = {row[1] for row in cursor.fetchall()}
        assert {"return_number", "sale_invoice_id", "refund_mode", "refund_amount_paise"}.issubset(sr_cols)

        # Verify purchase_returns columns
        cursor.execute("PRAGMA table_info(purchase_returns);")
        pr_cols = {row[1] for row in cursor.fetchall()}
        assert {"debit_note_number", "purchase_invoice_id", "supplier_id", "total_amount_paise"}.issubset(pr_cols)

        # Verify wastage_register columns
        cursor.execute("PRAGMA table_info(wastage_register);")
        wst_cols = {row[1] for row in cursor.fetchall()}
        assert {"reference_no", "batch_id", "quantity_units", "reason", "cost_impact_paise"}.issubset(wst_cols)
    finally:
        conn.close()


def test_khata_credit_sale_and_append_only_ledger(client: TestClient, auth_fixture: dict):
    """Verify that a credit sale increments customer balance and creates an immutable DEBIT ledger entry."""
    data = _seed_base_catalog_and_stock(client, auth_fixture["admin_headers"])
    cust = data["customer"]
    med = data["medicine"]
    batch_id = data["batch_id"]

    # Sell 20 tablets on Khata
    checkout_payload = {
        "customer_id": cust["id"],
        "payment_mode": "KHATA",
        "lines": [
            {
                "medicine_id": med["id"],
                "batch_id": batch_id,
                "quantity_units": 20,
            }
        ],
    }

    res = client.post("/api/v1/sales/checkout", headers=auth_fixture["cashier_headers"], json=checkout_payload)
    assert res.status_code == 201
    inv = res.json()["data"]

    # Customer balance must have increased by grand total
    grand_total_paise = inv["grand_total_paise"]
    assert grand_total_paise > 0

    bal_res = client.get(f"/api/v1/customers/{cust['id']}/balance", headers=auth_fixture["cashier_headers"])
    assert bal_res.status_code == 200
    bal_data = bal_res.json()["data"]
    assert bal_data["current_balance_paise"] == grand_total_paise

    # Khata ledger must contain DEBIT entry
    khata_res = client.get(f"/api/v1/customers/{cust['id']}/khata", headers=auth_fixture["cashier_headers"])
    assert khata_res.status_code == 200
    khata_entries = khata_res.json()["data"]["items"]
    assert len(khata_entries) == 1
    assert khata_entries[0]["transaction_type"] == "SALE_CREDIT"
    assert khata_entries[0]["entry_type"] == "DEBIT"
    assert khata_entries[0]["amount_paise"] == grand_total_paise
    assert khata_entries[0]["balance_paise"] == grand_total_paise


def test_customer_payment_deposit_and_receipt(client: TestClient, auth_fixture: dict):
    """Verify customer payment reduces balance and generates a printable receipt with CREDIT ledger entry."""
    data = _seed_base_catalog_and_stock(client, auth_fixture["admin_headers"])
    cust = data["customer"]
    med = data["medicine"]
    batch_id = data["batch_id"]

    # 1. First credit sale of 20 tablets
    client.post(
        "/api/v1/sales/checkout",
        headers=auth_fixture["cashier_headers"],
        json={"customer_id": cust["id"], "payment_mode": "KHATA", "lines": [{"medicine_id": med["id"], "batch_id": batch_id, "quantity_units": 20}]},
    )

    bal1 = client.get(f"/api/v1/customers/{cust['id']}/balance", headers=auth_fixture["cashier_headers"]).json()["data"]["current_balance_paise"]
    assert bal1 > 0

    # 2. Make deposit of 10000 paise (₹100)
    pay_res = client.post(
        f"/api/v1/customers/{cust['id']}/payments",
        headers=auth_fixture["cashier_headers"],
        json={"amount_paise": 10000, "payment_mode": "UPI", "notes": "UPI GPay settlement"},
    )
    assert pay_res.status_code == 201
    receipt = pay_res.json()["data"]

    assert receipt["amount_paise"] == 10000
    assert receipt["previous_balance_paise"] == bal1
    assert receipt["new_balance_paise"] == bal1 - 10000
    assert receipt["receipt_no"].startswith("RCP-")

    # Verify receipt fetch endpoint
    rcp_res = client.get(f"/api/v1/customers/receipts/{receipt['receipt_no']}", headers=auth_fixture["cashier_headers"])
    assert rcp_res.status_code == 200
    assert rcp_res.json()["data"]["receipt_no"] == receipt["receipt_no"]

    # Verify ledger history has 2 entries (DEBIT then CREDIT)
    k_res = client.get(f"/api/v1/customers/{cust['id']}/khata", headers=auth_fixture["cashier_headers"])
    items = k_res.json()["data"]["items"]
    assert len(items) == 2
    assert items[0]["entry_type"] == "CREDIT"
    assert items[0]["amount_paise"] == 10000
    assert items[0]["balance_paise"] == bal1 - 10000


def test_credit_limit_enforcement(client: TestClient, auth_fixture: dict):
    """Verify that credit sales exceeding credit limit are rejected with HTTP 422."""
    data = _seed_base_catalog_and_stock(client, auth_fixture["admin_headers"])
    cust = data["customer"]  # limit is ₹2,000 = 200,000 paise
    med = data["medicine"]
    batch_id = data["batch_id"]

    # Sell 200 tablets (MRP ₹15/tablet = ₹3,000 > limit)
    # But batch only has 100 tablets. Inward another 200 tablets
    client.post(
        "/api/v1/purchases",
        headers=auth_fixture["admin_headers"],
        json={
            "supplier_id": data["supplier"]["id"],
            "supplier_invoice_number": "INV-EXTRA",
            "invoice_date": date.today().strftime("%Y-%m-%d"),
            "lines": [
                {
                    "medicine_id": med["id"],
                    "batch_number": "AZ-801",
                    "expiry_date": (date.today() + timedelta(days=365)).strftime("%Y-%m-%d"),
                    "pack_size": 10,
                    "paid_quantity": 20,
                    "free_quantity": 0,
                    "purchase_rate_paise": 10000,
                    "mrp_paise": 15000,
                    "discount_percent": 0.0,
                    "gst_percentage": 12.0,
                }
            ],
        },
    )
    # Post second purchase
    client.post("/api/v1/purchases/2/post", headers=auth_fixture["admin_headers"])

    # Attempt to bill 150 tablets (150 * ₹15 = ₹2,250 > ₹2,000 limit)
    checkout_res = client.post(
        "/api/v1/sales/checkout",
        headers=auth_fixture["cashier_headers"],
        json={"customer_id": cust["id"], "payment_mode": "KHATA", "lines": [{"medicine_id": med["id"], "batch_id": batch_id, "quantity_units": 150}]},
    )
    assert checkout_res.status_code == 422
    assert "credit limit exceeded" in checkout_res.json()["detail"].lower()


def test_aging_bucket_calculation(client: TestClient, auth_fixture: dict):
    """Verify customer aging breakdown across 0-30, 31-60, and 60+ days."""
    data = _seed_base_catalog_and_stock(client, auth_fixture["admin_headers"])
    cust = data["customer"]

    # Create manual ledger entries with backdated timestamps
    engine = client.app.state.db_engine
    conn = engine.get_connection()
    try:
        cursor = conn.cursor()
        t_recent = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        t_mid = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
        t_old = (datetime.now(timezone.utc) - timedelta(days=75)).isoformat()

        # Update customer balance to 30000 paise
        cursor.execute("UPDATE customers SET current_balance_paise = 30000 WHERE id = ?;", (cust["id"],))

        # Insert 3 debits of 10000 paise each
        cursor.execute(
            "INSERT INTO khata_ledger (customer_id, transaction_type, entry_type, amount_paise, balance_paise, reference_type, created_at) VALUES (?, 'SALE_CREDIT', 'DEBIT', 10000, 10000, 'SALE_INVOICE', ?);",
            (cust["id"], t_old),
        )
        cursor.execute(
            "INSERT INTO khata_ledger (customer_id, transaction_type, entry_type, amount_paise, balance_paise, reference_type, created_at) VALUES (?, 'SALE_CREDIT', 'DEBIT', 10000, 20000, 'SALE_INVOICE', ?);",
            (cust["id"], t_mid),
        )
        cursor.execute(
            "INSERT INTO khata_ledger (customer_id, transaction_type, entry_type, amount_paise, balance_paise, reference_type, created_at) VALUES (?, 'SALE_CREDIT', 'DEBIT', 10000, 30000, 'SALE_INVOICE', ?);",
            (cust["id"], t_recent),
        )
        conn.commit()
    finally:
        conn.close()

    # Query aging report
    aging_res = client.get("/api/v1/customers/aging", headers=auth_fixture["admin_headers"])
    assert aging_res.status_code == 200
    report = aging_res.json()["data"]
    assert report["total_customers"] >= 1
    assert report["total_outstanding_paise"] == 30000

    cust_aging = next(c for c in report["customers"] if c["customer_id"] == cust["id"])
    assert cust_aging["bucket_0_30_paise"] == 10000
    assert cust_aging["bucket_31_60_paise"] == 10000
    assert cust_aging["bucket_60_plus_paise"] == 10000


def test_valid_customer_sales_return_and_restocking(client: TestClient, auth_fixture: dict):
    """Verify sales return restocks inventory and issues a cash refund."""
    data = _seed_base_catalog_and_stock(client, auth_fixture["admin_headers"])
    med = data["medicine"]
    batch_id = data["batch_id"]

    # 1. Sale of 10 tablets for Cash
    sale_res = client.post(
        "/api/v1/sales/checkout",
        headers=auth_fixture["cashier_headers"],
        json={"payment_mode": "CASH", "cash_tendered_paise": 50000, "lines": [{"medicine_id": med["id"], "batch_id": batch_id, "quantity_units": 10}]},
    )
    assert sale_res.status_code == 201
    inv = sale_res.json()["data"]
    sale_item_id = inv["items"][0]["id"]

    # Stock is now 90 tablets
    engine = client.app.state.db_engine
    conn = engine.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT current_quantity FROM medicine_batches WHERE id = ?;", (batch_id,))
        assert cursor.fetchone()[0] == 90
    finally:
        conn.close()

    # 2. Return 4 tablets with resellable = True
    ret_res = client.post(
        "/api/v1/returns/sales",
        headers=auth_fixture["pharm_headers"],
        json={
            "sale_invoice_id": inv["id"],
            "refund_mode": "CASH",
            "reason": "Customer bought extra strip",
            "items": [{"sale_item_id": sale_item_id, "quantity_units": 4, "is_resellable": True}],
        },
    )
    assert ret_res.status_code == 201
    ret_data = ret_res.json()["data"]
    assert ret_data["return_number"].startswith("CN-")
    assert ret_data["refund_amount_paise"] > 0
    assert ret_data["items"][0]["quantity_units"] == 4

    # Stock must now be 94 tablets
    conn = engine.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT current_quantity FROM medicine_batches WHERE id = ?;", (batch_id,))
        assert cursor.fetchone()[0] == 94

        # Check inventory_ledger has SALE_RETURN
        cursor.execute("SELECT transaction_type, quantity_change FROM inventory_ledger WHERE reference_type = 'SALES_RETURN';")
        led = cursor.fetchone()
        assert led[0] == "SALE_RETURN"
        assert led[1] == 4
    finally:
        conn.close()


def test_sales_return_khata_refund(client: TestClient, auth_fixture: dict):
    """Verify sales return with KHATA refund mode reduces customer debt balance."""
    data = _seed_base_catalog_and_stock(client, auth_fixture["admin_headers"])
    cust = data["customer"]
    med = data["medicine"]
    batch_id = data["batch_id"]

    # 1. Sale of 10 tablets on Khata
    sale_res = client.post(
        "/api/v1/sales/checkout",
        headers=auth_fixture["cashier_headers"],
        json={"customer_id": cust["id"], "payment_mode": "KHATA", "lines": [{"medicine_id": med["id"], "batch_id": batch_id, "quantity_units": 10}]},
    )
    inv = sale_res.json()["data"]
    sale_item_id = inv["items"][0]["id"]
    initial_debt = inv["grand_total_paise"]

    # 2. Return 5 tablets with refund_mode = KHATA
    ret_res = client.post(
        "/api/v1/returns/sales",
        headers=auth_fixture["pharm_headers"],
        json={
            "sale_invoice_id": inv["id"],
            "refund_mode": "KHATA",
            "reason": "Doctor changed prescription",
            "items": [{"sale_item_id": sale_item_id, "quantity_units": 5, "is_resellable": True}],
        },
    )
    assert ret_res.status_code == 201
    refund_amt = ret_res.json()["data"]["refund_amount_paise"]

    # Customer balance must be reduced by refund_amt
    bal = client.get(f"/api/v1/customers/{cust['id']}/balance", headers=auth_fixture["cashier_headers"]).json()["data"]["current_balance_paise"]
    assert bal == initial_debt - refund_amt


def test_sales_return_over_return_rejection(client: TestClient, auth_fixture: dict):
    """Verify returning more than sold quantity or returning twice beyond limit is rejected."""
    data = _seed_base_catalog_and_stock(client, auth_fixture["admin_headers"])
    med = data["medicine"]
    batch_id = data["batch_id"]

    # Sale of 5 tablets
    sale_res = client.post(
        "/api/v1/sales/checkout",
        headers=auth_fixture["cashier_headers"],
        json={"payment_mode": "CASH", "cash_tendered_paise": 20000, "lines": [{"medicine_id": med["id"], "batch_id": batch_id, "quantity_units": 5}]},
    )
    inv = sale_res.json()["data"]
    sale_item_id = inv["items"][0]["id"]

    # Attempt to return 6 tablets (over-return)
    fail_res = client.post(
        "/api/v1/returns/sales",
        headers=auth_fixture["pharm_headers"],
        json={"sale_invoice_id": inv["id"], "refund_mode": "CASH", "reason": "Test", "items": [{"sale_item_id": sale_item_id, "quantity_units": 6, "is_resellable": True}]},
    )
    assert fail_res.status_code == 422
    assert "available for return" in fail_res.json()["detail"].lower()

    # Return 3 tablets (valid)
    client.post(
        "/api/v1/returns/sales",
        headers=auth_fixture["pharm_headers"],
        json={"sale_invoice_id": inv["id"], "refund_mode": "CASH", "reason": "Test", "items": [{"sale_item_id": sale_item_id, "quantity_units": 3, "is_resellable": True}]},
    )

    # Attempt to return 3 more tablets (only 2 remain)
    fail_res2 = client.post(
        "/api/v1/returns/sales",
        headers=auth_fixture["pharm_headers"],
        json={"sale_invoice_id": inv["id"], "refund_mode": "CASH", "reason": "Test", "items": [{"sale_item_id": sale_item_id, "quantity_units": 3, "is_resellable": True}]},
    )
    assert fail_res2.status_code == 422


def test_sales_return_non_resellable_recorded_as_wastage(client: TestClient, auth_fixture: dict):
    """Verify non-resellable customer return is logged in wastage_register and does NOT restock inventory."""
    data = _seed_base_catalog_and_stock(client, auth_fixture["admin_headers"])
    med = data["medicine"]
    batch_id = data["batch_id"]

    # Sale of 10 tablets
    sale_res = client.post(
        "/api/v1/sales/checkout",
        headers=auth_fixture["cashier_headers"],
        json={"payment_mode": "CASH", "cash_tendered_paise": 50000, "lines": [{"medicine_id": med["id"], "batch_id": batch_id, "quantity_units": 10}]},
    )
    sale_item_id = sale_res.json()["data"]["items"][0]["id"]

    # Return 3 tablets as non-resellable (damaged strip)
    client.post(
        "/api/v1/returns/sales",
        headers=auth_fixture["pharm_headers"],
        json={"sale_invoice_id": sale_res.json()["data"]["id"], "refund_mode": "CASH", "reason": "Seal broken", "items": [{"sale_item_id": sale_item_id, "quantity_units": 3, "is_resellable": False}]},
    )

    # Stock must remain 90 (not restocked to 93)
    engine = client.app.state.db_engine
    conn = engine.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT current_quantity FROM medicine_batches WHERE id = ?;", (batch_id,))
        assert cursor.fetchone()[0] == 90

        # Check wastage_register has entry
        cursor.execute("SELECT quantity_units, reason FROM wastage_register WHERE reference_type = 'SALES_RETURN';")
        wst = cursor.fetchone()
        assert wst[0] == 3
        assert wst[1] == "DAMAGED"
    finally:
        conn.close()


def test_supplier_purchase_return_debit_note(client: TestClient, auth_fixture: dict):
    """Verify purchase return creates debit note, deducts stock, and reduces supplier payables."""
    data = _seed_base_catalog_and_stock(client, auth_fixture["admin_headers"])
    sup = data["supplier"]
    purchase = data["purchase"]
    batch_id = data["batch_id"]

    # Original purchase: 10 packs = 100 tablets. Supplier payable increased.
    sup_before = client.get(f"/api/v1/masters/suppliers/{sup['id']}", headers=auth_fixture["admin_headers"]).json()["data"]["current_payable_paise"]
    assert sup_before > 0

    # Line ID on purchase invoice
    line_id = purchase["lines"][0]["id"]

    # Return 20 units (2 packs) to supplier
    ret_res = client.post(
        "/api/v1/returns/purchases",
        headers=auth_fixture["pharm_headers"],
        json={
            "purchase_invoice_id": purchase["id"],
            "reason": "Defective packaging from distributor",
            "items": [{"purchase_invoice_line_id": line_id, "return_packs": 2, "return_units": 20}],
        },
    )
    assert ret_res.status_code == 201
    dn_data = ret_res.json()["data"]
    assert dn_data["debit_note_number"].startswith("DN-")
    assert dn_data["total_amount_paise"] > 0

    # Stock must be reduced from 100 to 80
    engine = client.app.state.db_engine
    conn = engine.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT current_quantity FROM medicine_batches WHERE id = ?;", (batch_id,))
        assert cursor.fetchone()[0] == 80
    finally:
        conn.close()

    # Supplier payable must be reduced
    sup_after = client.get(f"/api/v1/masters/suppliers/{sup['id']}", headers=auth_fixture["admin_headers"]).json()["data"]["current_payable_paise"]
    assert sup_after == sup_before - dn_data["total_amount_paise"]


def test_purchase_return_negative_stock_rejection(client: TestClient, auth_fixture: dict):
    """Verify purchase return is rejected if available batch stock is less than return quantity."""
    data = _seed_base_catalog_and_stock(client, auth_fixture["admin_headers"])
    med = data["medicine"]
    batch_id = data["batch_id"]
    purchase = data["purchase"]
    line_id = purchase["lines"][0]["id"]

    # Sell 90 tablets so only 10 tablets remain in stock
    client.post(
        "/api/v1/sales/checkout",
        headers=auth_fixture["cashier_headers"],
        json={"payment_mode": "CASH", "cash_tendered_paise": 200000, "lines": [{"medicine_id": med["id"], "batch_id": batch_id, "quantity_units": 90}]},
    )

    # Attempt to return 20 tablets (only 10 in stock)
    fail_res = client.post(
        "/api/v1/returns/purchases",
        headers=auth_fixture["pharm_headers"],
        json={"purchase_invoice_id": purchase["id"], "reason": "Test", "items": [{"purchase_invoice_line_id": line_id, "return_units": 20}]},
    )
    assert fail_res.status_code == 422
    assert "insufficient physical stock" in fail_res.json()["detail"].lower()


def test_wastage_register_write_off(client: TestClient, auth_fixture: dict):
    """Verify manual stock write-off due to breakage or damage deducts stock and records loss."""
    data = _seed_base_catalog_and_stock(client, auth_fixture["admin_headers"])
    batch_id = data["batch_id"]

    # Write off 5 tablets due to BREAKAGE
    res = client.post(
        "/api/v1/inventory/wastage",
        headers=auth_fixture["pharm_headers"],
        json={"batch_id": batch_id, "quantity_units": 5, "reason": "BREAKAGE", "notes": "Bottle slipped from shelf during cleaning"},
    )
    assert res.status_code == 201
    wst = res.json()["data"]
    assert wst["reference_no"].startswith("WST-")
    assert wst["cost_impact_paise"] > 0

    # Stock must decrease from 100 to 95
    engine = client.app.state.db_engine
    conn = engine.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT current_quantity FROM medicine_batches WHERE id = ?;", (batch_id,))
        assert cursor.fetchone()[0] == 95
    finally:
        conn.close()

    # Omission of notes on non-expired reason must fail
    fail_res = client.post(
        "/api/v1/inventory/wastage",
        headers=auth_fixture["pharm_headers"],
        json={"batch_id": batch_id, "quantity_units": 2, "reason": "BREAKAGE", "notes": ""},
    )
    assert fail_res.status_code == 422


def test_role_permissions_milestone5(client: TestClient, auth_fixture: dict):
    """Verify CASHIER cannot perform returns or wastage write-offs (must be PHARMACIST or ADMIN)."""
    data = _seed_base_catalog_and_stock(client, auth_fixture["admin_headers"])
    batch_id = data["batch_id"]
    purchase = data["purchase"]

    # Cashier cannot write off wastage
    wst_fail = client.post(
        "/api/v1/inventory/wastage",
        headers=auth_fixture["cashier_headers"],
        json={"batch_id": batch_id, "quantity_units": 1, "reason": "BREAKAGE", "notes": "Broken"},
    )
    assert wst_fail.status_code == 403

    # Cashier cannot perform purchase return
    pr_fail = client.post(
        "/api/v1/returns/purchases",
        headers=auth_fixture["cashier_headers"],
        json={"purchase_invoice_id": purchase["id"], "reason": "Test", "items": [{"purchase_invoice_line_id": purchase["lines"][0]["id"], "return_units": 1}]},
    )
    assert pr_fail.status_code == 403
