"""Automated test suite for Milestone 6:
Compliance Reports, Disaster Recovery, Hot Backups, and LAN Activation.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from pharmacy_daemon.security.hashing import hash_password


@pytest.fixture
def auth_fixture(client: TestClient) -> dict:
    """Setup store and generate tokens for ADMIN, PHARMACIST, and CASHIER."""
    # 1. Admin setup
    setup_payload = {
        "username": "m6_admin",
        "full_name": "Milestone6 Admin",
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
            VALUES ('m6_pharm', 'Staff Pharmacist', ?, NULL, 'PHARMACIST', 1, '2026-10-08T00:00:00Z', '2026-10-08T00:00:00Z');
            """,
            (pwd_hash,),
        )
        cursor.execute(
            """
            INSERT INTO users (username, full_name, password_hash, pin_hash, role, is_active, created_at, updated_at)
            VALUES ('m6_cashier', 'Counter Cashier', ?, NULL, 'CASHIER', 1, '2026-10-08T00:00:00Z', '2026-10-08T00:00:00Z');
            """,
            (pwd_hash,),
        )
        conn.commit()
    finally:
        conn.close()

    # Login pharmacist
    pharm_login = client.post("/api/v1/auth/login", json={"username": "m6_pharm", "password": "OperatorPass123!"})
    assert pharm_login.status_code == 200
    pharm_token = pharm_login.json()["access_token"]

    # Login cashier
    cashier_login = client.post("/api/v1/auth/login", json={"username": "m6_cashier", "password": "OperatorPass123!"})
    assert cashier_login.status_code == 200
    cashier_token = cashier_login.json()["access_token"]

    return {
        "admin": admin_token,
        "pharmacist": pharm_token,
        "cashier": cashier_token,
    }


def _seed_base_data(client: TestClient, admin_token: str) -> dict:
    """Seed supplier, customer with GSTIN, regular medicine, H1 medicine, and stock."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Supplier
    supp_res = client.post(
        "/api/v1/masters/suppliers",
        headers=headers,
        json={
            "name": "Apex Pharma Logistics",
            "gstin": "27AABCA1234F1Z5",
            "drug_license_no": "DL-M6-SUPP-01",
            "payment_terms_days": 30,
        },
    )
    assert supp_res.status_code == 201
    supplier_id = supp_res.json()["data"]["id"]

    # 2. Customer with GSTIN (B2B)
    b2b_cust_res = client.post(
        "/api/v1/masters/customers",
        headers=headers,
        json={
            "name": "Sunrise PolyClinic Ltd",
            "phone": "9876543210",
            "gstin": "27AABCS5678G1Z9",
            "credit_limit_paise": 5000000,
        },
    )
    assert b2b_cust_res.status_code == 201
    b2b_cust_id = b2b_cust_res.json()["data"]["id"]

    # 3. Regular Medicine
    med1_res = client.post(
        "/api/v1/masters/medicines",
        headers=headers,
        json={
            "brand_name": "Paracip 650",
            "generic_salt": "Paracetamol 650mg",
            "dosage_form": "TABLET",
            "pack_size": 10,
            "hsn_code": "30049099",
            "gst_rate": 12.0,
            "min_stock_units": 20,
            "is_schedule_h1": False,
        },
    )
    assert med1_res.status_code == 201
    med1_id = med1_res.json()["data"]["id"]

    # 4. Schedule H1 Medicine
    med_h1_res = client.post(
        "/api/v1/masters/medicines",
        headers=headers,
        json={
            "brand_name": "Alprax 0.5",
            "generic_salt": "Alprazolam 0.5mg",
            "dosage_form": "TABLET",
            "pack_size": 15,
            "hsn_code": "30049099",
            "gst_rate": 12.0,
            "min_stock_units": 10,
            "is_schedule_h1": True,
        },
    )
    assert med_h1_res.status_code == 201
    med_h1_id = med_h1_res.json()["data"]["id"]

    # 5. Purchase Entry for both
    purch_res = client.post(
        "/api/v1/purchases",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "supplier_invoice_number": "M6-SUPP-INV-1001",
            "invoice_date": "2026-10-01",
            "lines": [
                {
                    "medicine_id": med1_id,
                    "batch_number": "PARA-B1",
                    "expiry_date": "2027-12-31",
                    "pack_size": 10,
                    "paid_quantity": 10,
                    "purchase_rate_paise": 2000,
                    "mrp_paise": 3500,
                    "gst_percentage": 12.0,
                },
                {
                    "medicine_id": med_h1_id,
                    "batch_number": "ALP-H101",
                    "expiry_date": "2027-10-31",
                    "pack_size": 15,
                    "paid_quantity": 10,
                    "purchase_rate_paise": 3000,
                    "mrp_paise": 5500,
                    "gst_percentage": 12.0,
                },
            ],
        },
    )
    assert purch_res.status_code == 201
    purch_id = purch_res.json()["data"]["id"]

    # Post purchase into inventory
    post_res = client.post(f"/api/v1/purchases/{purch_id}/post", headers=headers)
    assert post_res.status_code == 200

    return {
        "supplier_id": supplier_id,
        "b2b_cust_id": b2b_cust_id,
        "med1_id": med1_id,
        "med_h1_id": med_h1_id,
        "purch_id": purch_id,
    }


def test_schedule_h1_report_and_csv_export(client: TestClient, auth_fixture: dict):
    """Test dispensing H1 drug, retrieving statutory register, and generating CSV export."""
    admin_token = auth_fixture["admin"]
    cashier_token = auth_fixture["cashier"]
    data = _seed_base_data(client, admin_token)

    # Cashier cannot access H1 report (ADMIN required)
    res_cashier = client.get(
        "/api/v1/reports/schedule-h1",
        headers={"Authorization": f"Bearer {cashier_token}"},
    )
    assert res_cashier.status_code == 403

    # Dispense H1 medicine via checkout
    h1_payload = {
        "lines": [
            {
                "medicine_id": data["med_h1_id"],
                "quantity_units": 15,
                "schedule_h1": {
                    "patient_name": "Rohan Sharma",
                    "patient_address": "Flat 402, Green View Apartments, Mumbai",
                    "doctor_name": "Dr. V. K. Gupta, MD",
                    "doctor_address": "Gupta Neuro Clinic, Mumbai",
                },
            }
        ],
        "payment_mode": "CASH",
        "cash_tendered_paise": 10000,
    }
    sale_res = client.post(
        "/api/v1/sales/checkout",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=h1_payload,
    )
    assert sale_res.status_code == 201
    sale_data = sale_res.json()["data"]
    inv_no = sale_data["invoice_no"]

    # Query Schedule H1 statutory register
    rep_res = client.get(
        "/api/v1/reports/schedule-h1",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rep_res.status_code == 200
    rep_body = rep_res.json()["data"]
    assert rep_body["total_records"] >= 1
    rec = next(r for r in rep_body["records"] if r["invoice_no"] == inv_no)
    assert rec["patient_name"] == "Rohan Sharma"
    assert rec["doctor_name"] == "Dr. V. K. Gupta, MD"
    assert rec["quantity_units"] == 15
    assert rec["batch_number"] == "ALP-H101"

    # Export Schedule H1 register as CSV
    csv_res = client.get(
        "/api/v1/reports/schedule-h1/export",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]
    csv_content = csv_res.text
    assert "Date of Dispensing" in csv_content
    assert "Rohan Sharma" in csv_content
    assert "ALP-H101" in csv_content


def test_gstr1_report_b2b_b2c_and_hsn(client: TestClient, auth_fixture: dict):
    """Test GSTR-1 classification into B2B and B2C invoices and HSN summaries."""
    admin_token = auth_fixture["admin"]
    data = _seed_base_data(client, admin_token)
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. B2B sale to registered customer
    b2b_sale = client.post(
        "/api/v1/sales/checkout",
        headers=headers,
        json={
            "customer_id": data["b2b_cust_id"],
            "lines": [
                {
                    "medicine_id": data["med1_id"],
                    "quantity_units": 20,
                }
            ],
            "payment_mode": "CASH",
        },
    )
    assert b2b_sale.status_code == 201

    # 2. B2C retail counter sale (no customer GSTIN)
    b2c_sale = client.post(
        "/api/v1/sales/checkout",
        headers=headers,
        json={
            "customer_name": "Walk-in Buyer",
            "lines": [
                {
                    "medicine_id": data["med1_id"],
                    "quantity_units": 10,
                }
            ],
            "payment_mode": "UPI",
        },
    )
    assert b2c_sale.status_code == 201

    # Fetch GSTR-1 report
    gstr1_res = client.get("/api/v1/reports/gstr-1", headers=headers)
    assert gstr1_res.status_code == 200
    g1 = gstr1_res.json()["data"]

    # Verify B2B invoices
    assert len(g1["b2b_invoices"]) >= 1
    b2b_entry = g1["b2b_invoices"][0]
    assert b2b_entry["customer_gstin"] == "27AABCS5678G1Z9"
    assert b2b_entry["customer_name"] == "Sunrise PolyClinic Ltd"
    assert b2b_entry["taxable_value_paise"] > 0
    assert b2b_entry["cgst_paise"] > 0

    # Verify B2C invoices
    assert len(g1["b2c_invoices"]) >= 1

    # Verify HSN summary
    hsn_list = g1["hsn_summary"]
    assert any(h["hsn_code"] == "30049099" for h in hsn_list)

    # Verify Doc summary
    doc_sum = g1["doc_summary"]
    assert doc_sum[0]["doc_type"] in ("Invoices for outward supply", "Tax Invoices")

    # Export B2B CSV
    csv_b2b = client.get("/api/v1/reports/gstr-1/b2b/export", headers=headers)
    assert csv_b2b.status_code == 200
    assert "27AABCS5678G1Z9" in csv_b2b.text

    # Export HSN CSV
    csv_hsn = client.get("/api/v1/reports/gstr-1/hsn/export", headers=headers)
    assert csv_hsn.status_code == 200
    assert "30049099" in csv_hsn.text


def test_gstr2_and_purchase_sales_registers(client: TestClient, auth_fixture: dict):
    """Test GSTR-2 grouped by supplier GSTIN, and Sales/Purchase registers."""
    admin_token = auth_fixture["admin"]
    data = _seed_base_data(client, admin_token)
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Fetch GSTR-2
    gstr2_res = client.get("/api/v1/reports/gstr-2", headers=headers)
    assert gstr2_res.status_code == 200
    g2 = gstr2_res.json()["data"]
    assert len(g2["suppliers"]) >= 1
    supp_entry = g2["suppliers"][0]
    assert supp_entry["supplier_gstin"] == "27AABCA1234F1Z5"
    assert supp_entry["grand_total_paise"] > 0

    # Export GSTR-2 CSV
    csv_g2 = client.get("/api/v1/reports/gstr-2/export", headers=headers)
    assert csv_g2.status_code == 200
    assert "27AABCA1234F1Z5" in csv_g2.text

    # Sales Register
    sr_res = client.get("/api/v1/reports/sales-register", headers=headers)
    assert sr_res.status_code == 200
    csv_sr = client.get("/api/v1/reports/sales-register/export", headers=headers)
    assert csv_sr.status_code == 200
    assert "Invoice No" in csv_sr.text

    # Purchase Register
    pr_res = client.get("/api/v1/reports/purchase-register", headers=headers)
    assert pr_res.status_code == 200
    csv_pr = client.get("/api/v1/reports/purchase-register/export", headers=headers)
    assert csv_pr.status_code == 200
    assert "Supplier Invoice" in csv_pr.text


def test_day_book_reconciliation_and_closed_immutability(client: TestClient, auth_fixture: dict):
    """Test opening float, cash sales calculation, closing drawer count, variance, and closed-day immutability."""
    admin_token = auth_fixture["admin"]
    data = _seed_base_data(client, admin_token)
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Set opening float: 50,000 paise (₹500.00)
    float_res = client.post(
        "/api/v1/reports/day-book/opening-float",
        headers=headers,
        json={"opening_float_paise": 50000},
    )
    assert float_res.status_code == 200
    assert float_res.json()["data"]["opening_float_paise"] == 50000

    # 2. Make a CASH sale of ₹35.00 = 3500 paise
    sale_res = client.post(
        "/api/v1/sales/checkout",
        headers=headers,
        json={
            "lines": [{"medicine_id": data["med1_id"], "quantity_units": 10}],
            "payment_mode": "CASH",
        },
    )
    assert sale_res.status_code == 201
    cash_sale_paise = sale_res.json()["data"]["grand_total_paise"]

    # 3. Customer Khata CASH deposit of 10,000 paise (₹100.00)
    deposit_res = client.post(
        f"/api/v1/customers/{data['b2b_cust_id']}/payments",
        headers=headers,
        json={
            "amount_paise": 10000,
            "payment_mode": "CASH",
            "notes": "Counter deposit",
        },
    )
    assert deposit_res.status_code == 201

    # 4. Inspect current day-book session
    current_res = client.get("/api/v1/reports/day-book/current", headers=headers)
    assert current_res.status_code == 200
    curr_data = current_res.json()["data"]

    expected = 50000 + cash_sale_paise + 10000
    assert curr_data["summary"]["opening_float_paise"] == 50000
    assert curr_data["summary"]["cash_sales_paise"] == cash_sale_paise
    assert curr_data["summary"]["cash_deposits_paise"] == 10000
    assert curr_data["summary"]["expected_cash_paise"] == expected

    # 5. Close drawer with actual cash = expected - 500 paise (-₹5.00 shortage)
    actual_cash = expected - 500
    close_res = client.post(
        "/api/v1/reports/day-book/close",
        headers=headers,
        json={
            "actual_cash_paise": actual_cash,
            "notes": "Evening drawer count: ₹5 cash shortage verified",
        },
    )
    assert close_res.status_code == 200
    closed_data = close_res.json()["data"]
    assert closed_data["status"] == "CLOSED"
    assert closed_data["actual_cash_paise"] == actual_cash
    assert closed_data["variance_paise"] == -500

    # 6. Re-closing closed day must fail
    reclose = client.post(
        "/api/v1/reports/day-book/close",
        headers=headers,
        json={"actual_cash_paise": actual_cash},
    )
    assert reclose.status_code == 400

    # 7. Updating opening float for closed day must fail
    float_fail = client.post(
        "/api/v1/reports/day-book/opening-float",
        headers=headers,
        json={"opening_float_paise": 60000},
    )
    assert float_fail.status_code == 400

    # 8. Sales checkout on closed date must fail
    sale_fail = client.post(
        "/api/v1/sales/checkout",
        headers=headers,
        json={
            "lines": [{"medicine_id": data["med1_id"], "quantity_units": 10}],
            "payment_mode": "CASH",
        },
    )
    assert sale_fail.status_code == 400
    assert "closed" in sale_fail.json()["detail"].lower()


def test_hot_backups_and_manifest_verification(client: TestClient, auth_fixture: dict):
    """Test hot non-blocking SQLite backup creation, SHA-256 verification, and download."""
    admin_token = auth_fixture["admin"]
    cashier_token = auth_fixture["cashier"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Cashier cannot take backup
    res_cashier = client.post(
        "/api/v1/system/backups",
        headers={"Authorization": f"Bearer {cashier_token}"},
        json={"notes": "Unauthorized backup"},
    )
    assert res_cashier.status_code == 403

    # Admin takes hot backup
    backup_res = client.post(
        "/api/v1/system/backups",
        headers=headers,
        json={"notes": "Pre-maintenance backup test", "backup_type": "MANUAL"},
    )
    assert backup_res.status_code == 200
    manifest = backup_res.json()["data"]
    backup_id = manifest["id"]
    assert manifest["filename"].endswith(".pbk")
    assert manifest["file_size_bytes"] > 0
    assert len(manifest["sha256_hash"]) == 64
    assert manifest["status"] == "VALID"

    # List backups
    list_res = client.get("/api/v1/system/backups", headers=headers)
    assert list_res.status_code == 200
    backups = list_res.json()["data"]
    assert any(b["id"] == backup_id for b in backups)

    # Verify backup integrity
    verify_res = client.get(f"/api/v1/system/backups/{backup_id}/verify", headers=headers)
    assert verify_res.status_code == 200
    verify_data = verify_res.json()["data"]
    assert verify_data["is_valid"] is True
    assert verify_data["integrity_status"] == "HEALTHY"

    # Download backup file
    dl_res = client.get(f"/api/v1/system/backups/{backup_id}/download", headers=headers)
    assert dl_res.status_code == 200
    assert len(dl_res.content) == manifest["file_size_bytes"]


def test_disaster_recovery_staged_restore_and_safety_backup(client: TestClient, auth_fixture: dict):
    """Test staging a backup, validating schema compatibility, pre-restore safety backup, and executing restoration."""
    admin_token = auth_fixture["admin"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Take initial backup
    b1_res = client.post(
        "/api/v1/system/backups",
        headers=headers,
        json={"notes": "Baseline state before modification", "backup_type": "MANUAL"},
    )
    assert b1_res.status_code == 200
    b1_id = b1_res.json()["data"]["id"]

    # 2. Modify database state by creating a new unique medicine
    unique_name = f"TestMed-{datetime.now().timestamp()}"
    new_med = client.post(
        "/api/v1/masters/medicines",
        headers=headers,
        json={
            "brand_name": unique_name,
            "generic_salt": "Test Salt",
            "dosage_form": "TABLET",
            "pack_size": 10,
            "hsn_code": "30049099",
            "gst_rate": 12.0,
        },
    )
    assert new_med.status_code == 201

    # Verify medicine exists
    med_list = client.get("/api/v1/masters/medicines", headers=headers)
    assert any(m["brand_name"] == unique_name for m in med_list.json()["data"]["items"])

    # 3. Preview restore of baseline backup
    preview_res = client.post(
        "/api/v1/system/restore/preview",
        headers=headers,
        data={"backup_id": b1_id},
    )
    assert preview_res.status_code == 200
    preview = preview_res.json()["data"]
    staging_token = preview["staging_token"]
    assert preview["is_compatible"] is True
    assert preview["integrity_status"] == "HEALTHY"

    # 4. Execute restore
    exec_res = client.post(
        "/api/v1/system/restore/execute",
        headers=headers,
        json={"staging_token": staging_token, "confirm": True},
    )
    assert exec_res.status_code == 200
    exec_data = exec_res.json()["data"]
    assert exec_data["success"] is True
    assert exec_data["safety_backup_filename"].startswith("backup_")

    # 5. Verify database was restored to baseline state (unique_name should no longer exist!)
    med_list_after = client.get("/api/v1/masters/medicines", headers=headers)
    assert not any(m["brand_name"] == unique_name for m in med_list_after.json()["data"]["items"])


def test_system_config_and_lan_discovery(client: TestClient, auth_fixture: dict):
    """Test getting/updating system configuration and reading LAN discovery telemetry."""
    admin_token = auth_fixture["admin"]
    cashier_token = auth_fixture["cashier"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Cashier cannot modify system config
    put_cashier = client.put(
        "/api/v1/system/config",
        headers={"Authorization": f"Bearer {cashier_token}"},
        json={"configs": {"server_mode": "LAN_SERVER"}},
    )
    assert put_cashier.status_code == 403

    # Admin reads config
    get_cfg = client.get("/api/v1/system/config", headers=headers)
    assert get_cfg.status_code == 200
    cfgs = get_cfg.json()["data"]["configs"]
    assert "server_mode" in cfgs
    assert "store_name" in cfgs

    # Admin updates config
    upd_cfg = client.put(
        "/api/v1/system/config",
        headers=headers,
        json={
            "configs": {
                "server_mode": "LAN_SERVER",
                "store_name": "Apex Central Pharmacy Superstore",
            }
        },
    )
    assert upd_cfg.status_code == 200
    assert upd_cfg.json()["data"]["configs"]["server_mode"] == "LAN_SERVER"
    assert upd_cfg.json()["data"]["configs"]["store_name"] == "Apex Central Pharmacy Superstore"

    # LAN discovery endpoint
    disc_res = client.get("/api/v1/system/discovery")
    assert disc_res.status_code == 200
    disc = disc_res.json()["data"]
    assert disc["server_name"] == "Apex Central Pharmacy Superstore"
    assert disc["server_mode"] == "LAN_SERVER"
    assert disc["database_status"] == "HEALTHY"
    assert isinstance(disc["lan_ips"], list)
    assert len(disc["lan_ips"]) >= 1


def test_hardware_printer_and_drawer_validation(client: TestClient, auth_fixture: dict):
    """Verify hardware test endpoints: ESC/POS receipt, cash drawer pulse, laser invoice, network fallback, and RBAC."""
    token = auth_fixture["admin"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. ESC/POS 80mm Simulation Test
    receipt_test = client.post(
        "/api/v1/system/hardware/test-printer",
        headers=headers,
        json={"printer_type": "thermal", "test_type": "receipt", "simulation_mode": True},
    )
    assert receipt_test.status_code == 200
    r_data = receipt_test.json()["data"]
    assert r_data["success"] is True
    assert r_data["bytes_generated"] > 0
    assert r_data["is_simulated"] is True
    assert "hex_sample" in r_data and len(r_data["hex_sample"]) > 0

    # 2. Cash Drawer Kick Pulse Test
    drawer_test = client.post(
        "/api/v1/system/hardware/test-printer",
        headers=headers,
        json={"test_type": "drawer_kick"},
    )
    assert drawer_test.status_code == 200
    d_data = drawer_test.json()["data"]
    assert d_data["success"] is True
    assert "1bp0019fa".replace("p", "70") in d_data["hex_sample"] or "1b70" in d_data["hex_sample"]

    # 3. A4 Laser Invoice Test
    laser_test = client.post(
        "/api/v1/system/hardware/test-printer",
        headers=headers,
        json={"printer_type": "laser", "test_type": "invoice"},
    )
    assert laser_test.status_code == 200
    l_data = laser_test.json()["data"]
    assert l_data["success"] is True
    assert l_data["printer_type"] == "laser"

    # 4. Network thermal printer offline fallback (unreachable port)
    net_test = client.post(
        "/api/v1/system/hardware/test-printer",
        headers=headers,
        json={"printer_type": "network", "target": "127.0.0.1:65534", "simulation_mode": False},
    )
    assert net_test.status_code == 200
    n_data = net_test.json()["data"]
    # Offline network printer reports success=False gracefully without HTTP 500 error
    assert n_data["success"] is False
    assert "offline" in n_data["message"].lower() or "unreachable" in n_data["message"].lower()

    # 5. Non-admin RBAC rejection
    non_admin_token = auth_fixture["cashier"]
    unauth_test = client.post(
        "/api/v1/system/hardware/test-printer",
        headers={"Authorization": f"Bearer {non_admin_token}"},
        json={"simulation_mode": True},
    )
    assert unauth_test.status_code == 403


