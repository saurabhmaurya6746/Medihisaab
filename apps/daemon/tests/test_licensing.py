"""Unit and integration tests for offline asymmetric Ed25519 client licensing."""

from datetime import date, timedelta
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from pharmacy_daemon.security.license import (
    EMBEDDED_PUBLIC_KEY_HEX,
    evaluate_license,
    sign_license,
    verify_license_signature,
    LicenseManager,
)

ROOT = Path(__file__).resolve().parent.parent.parent.parent
PRIVATE_KEY_PATH = ROOT / "publisher_keys" / "license_private_key.pem"


def test_offline_license_signing_and_verification():
    payload = {
        "client_name": "Apollo Care Pharmacy",
        "license_id": "LIC-2026-APOLLO",
        "terminal_count": 5,
        "activation_date": date.today().isoformat(),
        "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
        "edition": "PRO",
        "features": "ALL",
    }
    sig = sign_license(payload, PRIVATE_KEY_PATH)
    payload["signature"] = sig

    assert verify_license_signature(payload) is True

    status = evaluate_license(payload)
    assert status.is_valid is True
    assert status.status == "ACTIVE"
    assert status.terminal_count == 5
    assert status.client_name == "Apollo Care Pharmacy"


def test_tampered_license_rejection():
    payload = {
        "client_name": "Tampered Store",
        "license_id": "LIC-FAKE-01",
        "terminal_count": 1,
        "activation_date": date.today().isoformat(),
        "signature": "bad_signature_here",
    }
    assert verify_license_signature(payload) is False
    status = evaluate_license(payload)
    assert status.is_valid is False
    assert status.status == "INVALID_SIGNATURE"


def test_tampered_payload_fields_rejection():
    """Verify that altering terminal count or client name after signing invalidates signature."""
    payload = {
        "client_name": "Genuine Pharmacy",
        "license_id": "LIC-GEN-01",
        "terminal_count": 2,
        "activation_date": date.today().isoformat(),
        "edition": "STANDARD",
        "features": "ALL",
    }
    sig = sign_license(payload, PRIVATE_KEY_PATH)
    payload["signature"] = sig

    # Tamper with terminal count from 2 to 50
    tampered = dict(payload)
    tampered["terminal_count"] = 50
    assert verify_license_signature(tampered) is False
    status = evaluate_license(tampered)
    assert status.is_valid is False
    assert status.status == "INVALID_SIGNATURE"


def test_expired_license_detection():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    last_year = (date.today() - timedelta(days=365)).isoformat()
    payload = {
        "client_name": "Expired Store",
        "license_id": "LIC-EXP-01",
        "terminal_count": 2,
        "activation_date": last_year,
        "expiry_date": yesterday,
        "edition": "STANDARD",
        "features": "ALL",
    }
    payload["signature"] = sign_license(payload, PRIVATE_KEY_PATH)

    status = evaluate_license(payload)
    assert status.is_valid is False
    assert status.status == "EXPIRED"


def test_future_activation_date_detection():
    next_week = (date.today() + timedelta(days=7)).isoformat()
    payload = {
        "client_name": "Future Store",
        "license_id": "LIC-FUT-01",
        "terminal_count": 2,
        "activation_date": next_week,
        "edition": "STANDARD",
        "features": "ALL",
    }
    payload["signature"] = sign_license(payload, PRIVATE_KEY_PATH)

    status = evaluate_license(payload)
    assert status.is_valid is False
    assert status.status == "NOT_YET_ACTIVE"


def test_unlicensed_community_fallback():
    status = evaluate_license(None)
    assert status.is_valid is True
    assert status.status == "UNLICENSED_COMMUNITY"
    assert status.terminal_count == 2


def test_license_api_endpoint(client: TestClient):
    setup_payload = {
        "username": "admin",
        "full_name": "Test Admin",
        "password": "AdminPassword123!",
        "confirm_password": "AdminPassword123!",
        "store_name": "Test Pharmacy",
    }
    setup_res = client.post("/api/v1/auth/first-run-setup", json=setup_payload)
    assert setup_res.status_code == 201
    admin_token = setup_res.json()["access_token"]

    # 1. GET initial status (defaults to unlicensed community)
    res = client.get("/api/v1/system/license", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    data = res.json()["data"]
    assert "status" in data
    assert "terminal_count" in data

    # 2. Reject tampered license upload
    bad_payload = {
        "client_name": "Hacked Store",
        "license_id": "LIC-HACK",
        "terminal_count": 100,
        "activation_date": date.today().isoformat(),
        "signature": "invalid_sig",
    }
    bad_res = client.post("/api/v1/system/license", json=bad_payload, headers={"Authorization": f"Bearer {admin_token}"})
    assert bad_res.status_code == 400
    assert "Invalid license" in bad_res.json()["detail"]

    # 3. POST valid Ed25519 signed license
    payload = {
        "client_name": "City Health Meds",
        "license_id": "LIC-CITY-01",
        "terminal_count": 10,
        "activation_date": date.today().isoformat(),
        "edition": "COMMERCIAL",
        "features": "ALL",
    }
    payload["signature"] = sign_license(payload, PRIVATE_KEY_PATH)

    post_res = client.post("/api/v1/system/license", json=payload, headers={"Authorization": f"Bearer {admin_token}"})
    assert post_res.status_code == 200
    assert post_res.json()["data"]["status"] == "ACTIVE"
    assert post_res.json()["data"]["terminal_count"] == 10
    assert post_res.json()["data"]["client_name"] == "City Health Meds"

    # 4. Verify GET status now returns updated active license
    get_res = client.get("/api/v1/system/license", headers={"Authorization": f"Bearer {admin_token}"})
    assert get_res.status_code == 200
    assert get_res.json()["data"]["status"] == "ACTIVE"
    assert get_res.json()["data"]["license_id"] == "LIC-CITY-01"


def test_absent_license_blocks_commercial_writes_through_community_mode(client: TestClient):
    """Ensure that an absent license (UNLICENSED_COMMUNITY) cannot enable commercial writes,
    while preserving read access and allowing hot backups."""
    setup_payload = {
        "username": "pos_admin_comm",
        "full_name": "Community Mode Admin",
        "password": "AdminPassword123!",
        "confirm_password": "AdminPassword123!",
        "pin": "1234",
        "store_name": "Community Chemist",
    }
    setup_res = client.post("/api/v1/auth/first-run-setup", json=setup_payload)
    assert setup_res.status_code == 201
    admin_token = setup_res.json()["access_token"]
    admin_h = {"Authorization": f"Bearer {admin_token}"}

    # Delete license.json to simulate absent license / community mode
    config = client.app.state.config
    lic_file = config.app_dir / "license.json"
    if lic_file.exists():
        lic_file.unlink()

    # 1. Verify license status reports UNLICENSED_COMMUNITY
    res = client.get("/api/v1/system/license", headers=admin_h)
    assert res.status_code == 200
    assert res.json()["data"]["status"] == "UNLICENSED_COMMUNITY"

    # 2. Verify all master data writes are blocked (HTTP 403 Forbidden)
    med_res = client.post(
        "/api/v1/masters/medicines",
        json={"brand_name": "Unlicensed Med", "generic_salt": "Salt X", "dosage_form": "TABLET", "pack_size": 10},
        headers=admin_h,
    )
    assert med_res.status_code == 403
    assert "Commercial operations and master-data writes are restricted" in med_res.json()["detail"]
    assert "UNLICENSED_COMMUNITY" in med_res.json()["detail"]

    sup_res = client.post(
        "/api/v1/masters/suppliers",
        json={"name": "Unlicensed Supplier", "phone": "9876543210"},
        headers=admin_h,
    )
    assert sup_res.status_code == 403

    cust_res = client.post(
        "/api/v1/masters/customers",
        json={"name": "Unlicensed Customer", "phone": "9876543210"},
        headers=admin_h,
    )
    assert cust_res.status_code == 403

    # 3. Verify commercial transactions are blocked (HTTP 403 Forbidden)
    checkout_res = client.post(
        "/api/v1/sales/checkout",
        json={"customer_name": "Walk-in", "lines": [{"medicine_id": 1, "quantity_units": 1}], "payment_mode": "CASH"},
        headers=admin_h,
    )
    assert checkout_res.status_code == 403

    hold_res = client.post(
        "/api/v1/sales/held-bills",
        json={"items": [{"medicine_id": 1, "quantity_units": 1}]},
        headers=admin_h,
    )
    assert hold_res.status_code == 403

    purch_res = client.post(
        "/api/v1/purchases",
        json={"supplier_id": 1, "invoice_number": "PUR-COMM-01", "invoice_date": date.today().isoformat(), "lines": []},
        headers=admin_h,
    )
    assert purch_res.status_code == 403

    audit_res = client.post(
        "/api/v1/inventory/audits",
        json={"batch_id": 1, "adjusted_quantity": 5, "reason_code": "PHYSICAL_COUNT_ADJUSTMENT", "reason": "PHYSICAL_COUNT_ADJUSTMENT"},
        headers=admin_h,
    )
    assert audit_res.status_code == 403

    wst_res = client.post(
        "/api/v1/inventory/wastage",
        json={"batch_id": 1, "quantity_units": 1, "wastage_reason": "DAMAGED"},
        headers=admin_h,
    )
    assert wst_res.status_code == 403

    # 4. Verify historical read queries and backups remain completely accessible
    assert client.get("/api/v1/masters/medicines", headers=admin_h).status_code == 200
    assert client.get("/api/v1/masters/suppliers", headers=admin_h).status_code == 200
    assert client.get("/api/v1/masters/customers", headers=admin_h).status_code == 200
    assert client.get("/api/v1/sales/invoices", headers=admin_h).status_code == 200
    assert client.get("/api/v1/purchases", headers=admin_h).status_code == 200
    assert client.get("/api/v1/reports/day-book/current", headers=admin_h).status_code == 200
    assert client.get("/api/v1/system/backups", headers=admin_h).status_code == 200

    # Backups can be created safely in community/unlicensed mode
    backup_res = client.post("/api/v1/system/backups", json={"backup_type": "MANUAL", "notes": "Community mode safety backup"}, headers=admin_h)
    assert backup_res.status_code in (200, 201)

    # 5. Importing a valid signed license token immediately activates the workstation
    valid_payload = {
        "client_name": "Community Chemist",
        "license_id": "LIC-ACTIVATED-01",
        "terminal_count": 2,
        "activation_date": date.today().isoformat(),
        "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
        "edition": "COMMERCIAL",
        "features": "ALL",
    }
    valid_payload["signature"] = sign_license(valid_payload, PRIVATE_KEY_PATH)
    import_res = client.post("/api/v1/system/license", json=valid_payload, headers=admin_h)
    assert import_res.status_code == 200
    assert import_res.json()["data"]["status"] == "ACTIVE"

    # 6. Master data writes immediately succeed
    new_med = client.post(
        "/api/v1/masters/medicines",
        json={"brand_name": "Activated Med", "generic_salt": "Paracetamol", "dosage_form": "TABLET", "pack_size": 10},
        headers=admin_h,
    )
    assert new_med.status_code == 201


def test_expired_license_blocks_all_transactions_and_master_writes_preserves_reads_and_renewal_restores(client: TestClient):
    """Verify that after license & grace expiry, ALL new/edited pharmacy transactions and master-data
    writes are blocked (403), local database data remains 100% intact, read queries and backups work,
    and importing a renewed license immediately restores all write operations."""
    setup_payload = {
        "username": "pos_admin_exp",
        "full_name": "License POS Owner",
        "password": "AdminPassword123!",
        "confirm_password": "AdminPassword123!",
        "pin": "1234",
        "store_name": "Expirable Pharmacy",
    }
    setup_res = client.post("/api/v1/auth/first-run-setup", json=setup_payload)
    admin_token = setup_res.json()["access_token"]
    admin_h = {"Authorization": f"Bearer {admin_token}"}

    # 1. Create baseline master data while license is initially active
    med_res = client.post(
        "/api/v1/masters/medicines",
        json={"brand_name": "Paracetamol 500", "generic_salt": "Paracetamol", "dosage_form": "TABLET", "pack_size": 10, "gst_rate": 12.0},
        headers=admin_h,
    )
    assert med_res.status_code == 201
    med_id = med_res.json()["data"]["id"]

    sup_res = client.post(
        "/api/v1/masters/suppliers",
        json={"name": "Alpha Pharma Distributors", "phone": "9998887776"},
        headers=admin_h,
    )
    assert sup_res.status_code == 201
    sup_id = sup_res.json()["data"]["id"]

    cust_res = client.post(
        "/api/v1/masters/customers",
        json={"name": "Kiran Patel", "phone": "9876543210", "credit_limit_paise": 50000},
        headers=admin_h,
    )
    assert cust_res.status_code == 201
    cust_id = cust_res.json()["data"]["id"]

    # Inward stock
    app = client.app
    engine = app.state.db_engine
    with engine.get_connection() as conn:
        cursor = conn.cursor()
        from datetime import datetime, timezone
        now_str = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            """
            INSERT INTO medicine_batches (medicine_id, batch_number, expiry_date, mrp_paise, purchase_rate_paise, pack_size, current_quantity, is_active, created_at, updated_at)
            VALUES (?, 'BATCH-EXP-01', '2028-12-31', 10000, 7000, 10, 100, 1, ?, ?);
            """,
            (med_id, now_str, now_str),
        )
        batch_id = cursor.lastrowid
        conn.commit()

    # 2. Simulate expired license on disk (expired 20 days ago, past 7-day grace)
    past_expiry = (date.today() - timedelta(days=20)).isoformat()
    past_activation = (date.today() - timedelta(days=50)).isoformat()
    expired_payload = {
        "client_name": "Expirable Pharmacy",
        "license_id": "LIC-EXPIRED-TEST",
        "terminal_count": 2,
        "activation_date": past_activation,
        "expiry_date": past_expiry,
        "grace_period_days": 7,
        "edition": "COMMERCIAL",
        "features": "ALL",
    }
    expired_payload["signature"] = sign_license(expired_payload, PRIVATE_KEY_PATH)

    config = client.app.state.config
    mgr = LicenseManager(config.app_dir / "license.json")
    mgr.save_license(expired_payload)

    # Verify status is EXPIRED
    lic_res = client.get("/api/v1/system/license", headers=admin_h)
    assert lic_res.status_code == 200
    assert lic_res.json()["data"]["status"] == "EXPIRED"

    # 3. VERIFY ALL WRITE ENDPOINTS ARE BLOCKED (HTTP 403 Forbidden)
    # Master-data: medicine create, update, delete
    assert client.post("/api/v1/masters/medicines", json={"brand_name": "New Med", "dosage_form": "TABLET"}, headers=admin_h).status_code == 403
    assert client.put(f"/api/v1/masters/medicines/{med_id}", json={"brand_name": "Updated Name"}, headers=admin_h).status_code == 403
    assert client.delete(f"/api/v1/masters/medicines/{med_id}", headers=admin_h).status_code == 403

    # Master-data: supplier & customer create/update/delete
    assert client.post("/api/v1/masters/suppliers", json={"name": "New Sup"}, headers=admin_h).status_code == 403
    assert client.put(f"/api/v1/masters/suppliers/{sup_id}", json={"name": "Updated Sup"}, headers=admin_h).status_code == 403
    assert client.delete(f"/api/v1/masters/suppliers/{sup_id}", headers=admin_h).status_code == 403
    assert client.post("/api/v1/masters/customers", json={"name": "New Cust"}, headers=admin_h).status_code == 403
    assert client.put(f"/api/v1/masters/customers/{cust_id}", json={"name": "Updated Cust"}, headers=admin_h).status_code == 403
    assert client.delete(f"/api/v1/masters/customers/{cust_id}", headers=admin_h).status_code == 403

    # Commercial transactions: Purchases
    assert client.post("/api/v1/purchases", json={"supplier_id": sup_id, "invoice_number": "INV-P-99", "invoice_date": date.today().isoformat(), "lines": []}, headers=admin_h).status_code == 403

    # Commercial transactions: Sales Checkout
    checkout_res = client.post(
        "/api/v1/sales/checkout",
        json={"customer_name": "Walk-in", "lines": [{"medicine_id": med_id, "quantity_units": 10}], "payment_mode": "CASH", "cash_tendered_paise": 10000},
        headers=admin_h,
    )
    assert checkout_res.status_code == 403
    assert "Commercial operations and master-data writes are restricted" in checkout_res.json()["detail"]

    # Commercial transactions: Held bills
    assert client.post("/api/v1/sales/held-bills", json={"items": [{"medicine_id": med_id, "quantity_units": 5}]}, headers=admin_h).status_code == 403

    # Commercial transactions: Returns
    assert client.post("/api/v1/returns/sales", json={"sale_invoice_id": 1, "return_reason": "DEFECTIVE", "refund_mode": "CASH", "lines": []}, headers=admin_h).status_code == 403
    assert client.post("/api/v1/returns/purchases", json={"purchase_invoice_id": 1, "supplier_id": sup_id, "debit_note_number": "DN-01", "return_date": date.today().isoformat(), "lines": []}, headers=admin_h).status_code == 403

    # Inventory adjustments & wastage
    assert client.post("/api/v1/inventory/audits", json={"batch_id": batch_id, "adjusted_quantity": 90, "reason": "PHYSICAL_COUNT_ADJUSTMENT", "reason_code": "PHYSICAL_COUNT_ADJUSTMENT", "notes": "Count fix"}, headers=admin_h).status_code == 403
    assert client.post("/api/v1/inventory/want-book", json={"medicine_id": med_id, "requested_quantity": 20}, headers=admin_h).status_code == 403
    assert client.post("/api/v1/inventory/wastage", json={"batch_id": batch_id, "quantity_units": 2, "wastage_reason": "DAMAGED"}, headers=admin_h).status_code == 403

    # Customer Khata deposit
    assert client.post(f"/api/v1/customers/{cust_id}/payments", json={"amount_paise": 1000, "payment_mode": "CASH"}, headers=admin_h).status_code == 403

    # 4. VERIFY READ-ONLY HISTORY, REPORTS & BACKUPS WORK COMPLETELY
    assert client.get("/api/v1/masters/medicines", headers=admin_h).status_code == 200
    assert client.get("/api/v1/masters/suppliers", headers=admin_h).status_code == 200
    assert client.get("/api/v1/masters/customers", headers=admin_h).status_code == 200
    assert client.get("/api/v1/sales/invoices", headers=admin_h).status_code == 200
    assert client.get("/api/v1/purchases", headers=admin_h).status_code == 200
    assert client.get(f"/api/v1/customers/{cust_id}/khata", headers=admin_h).status_code == 200
    assert client.get("/api/v1/customers/aging", headers=admin_h).status_code == 200
    assert client.get("/api/v1/reports/day-book/current", headers=admin_h).status_code == 200
    assert client.get("/api/v1/system/backups", headers=admin_h).status_code == 200

    # Backups can be created safely
    bkp_res = client.post("/api/v1/system/backups", json={"backup_type": "MANUAL", "notes": "Expiry safety archive"}, headers=admin_h)
    assert bkp_res.status_code in (200, 201)

    # 5. VERIFY LOCAL PHARMACY DATA REMAINS 100% INTACT (NO WIPING/ENCRYPTION)
    with engine.get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM medicines;")
        assert c.fetchone()[0] >= 1
        c.execute("SELECT COUNT(*) FROM medicine_batches;")
        assert c.fetchone()[0] >= 1
        c.execute("SELECT COUNT(*) FROM customers;")
        assert c.fetchone()[0] >= 1
        c.execute("SELECT COUNT(*) FROM suppliers;")
        assert c.fetchone()[0] >= 1

    # 6. IMPORT RENEWED CLIENT LICENSE (HTTP 200)
    next_year = (date.today() + timedelta(days=365)).isoformat()
    renewed_payload = {
        "client_name": "Expirable Pharmacy",
        "license_id": "LIC-RENEWED-01",
        "terminal_count": 5,
        "activation_date": date.today().isoformat(),
        "expiry_date": next_year,
        "edition": "COMMERCIAL",
        "features": "ALL",
    }
    renewed_payload["signature"] = sign_license(renewed_payload, PRIVATE_KEY_PATH)

    renew_res = client.post("/api/v1/system/license", json=renewed_payload, headers=admin_h)
    assert renew_res.status_code == 200
    assert renew_res.json()["data"]["status"] == "ACTIVE"

    # 7. WRITES ARE IMMEDIATELY RESTORED
    checkout_ok = client.post(
        "/api/v1/sales/checkout",
        json={"customer_name": "Walk-in Patient", "lines": [{"medicine_id": med_id, "quantity_units": 10}], "payment_mode": "CASH", "cash_tendered_paise": 10000},
        headers=admin_h,
    )
    assert checkout_ok.status_code == 201
    assert checkout_ok.json()["data"]["invoice_no"].startswith("INV/")


def test_grace_period_allows_writes(client: TestClient):
    """Verify that during active grace period, writes continue normally while warning is given."""
    setup_payload = {
        "username": "pos_admin_grace",
        "full_name": "Grace Owner",
        "password": "AdminPassword123!",
        "confirm_password": "AdminPassword123!",
        "pin": "1234",
        "store_name": "Grace Pharmacy",
    }
    setup_res = client.post("/api/v1/auth/first-run-setup", json=setup_payload)
    admin_token = setup_res.json()["access_token"]
    admin_h = {"Authorization": f"Bearer {admin_token}"}

    # Expired 3 days ago with 7-day grace period -> 4 days grace left
    expired_three_days_ago = (date.today() - timedelta(days=3)).isoformat()
    grace_payload = {
        "client_name": "Grace Pharmacy",
        "license_id": "LIC-GRACE-TEST",
        "terminal_count": 2,
        "activation_date": (date.today() - timedelta(days=33)).isoformat(),
        "expiry_date": expired_three_days_ago,
        "grace_period_days": 7,
        "edition": "COMMERCIAL",
        "features": "ALL",
    }
    grace_payload["signature"] = sign_license(grace_payload, PRIVATE_KEY_PATH)

    config = client.app.state.config
    mgr = LicenseManager(config.app_dir / "license.json")
    mgr.save_license(grace_payload)

    # 1. License status reports GRACE_PERIOD
    lic_res = client.get("/api/v1/system/license", headers=admin_h)
    assert lic_res.status_code == 200
    assert lic_res.json()["data"]["status"] == "GRACE_PERIOD"
    assert lic_res.json()["data"]["grace_period_active"] is True
    assert lic_res.json()["data"]["remaining_days"] == 4

    # 2. Writes are permitted during grace period
    med_res = client.post(
        "/api/v1/masters/medicines",
        json={"brand_name": "Grace Period Medicine", "generic_salt": "Paracetamol", "dosage_form": "TABLET", "pack_size": 10},
        headers=admin_h,
    )
    assert med_res.status_code == 201


def test_version2_license_signing_and_grace_tampering_rejection():
    """Verify that Version 2 licenses cryptographically sign grace_period_days,
    and altering grace duration invalidates the digital signature."""
    payload = {
        "client_name": "Apex Central Pharmacy",
        "license_id": "LIC-V2-SECURE-001",
        "terminal_count": 3,
        "activation_date": date.today().isoformat(),
        "expiry_date": (date.today() + timedelta(days=30)).isoformat(),
        "grace_period_days": 14,
        "edition": "COMMERCIAL",
        "features": "ALL",
        "version": 2,
    }
    payload["signature"] = sign_license(payload, PRIVATE_KEY_PATH)

    # 1. Untampered Version 2 license verifies and evaluates ACTIVE
    assert verify_license_signature(payload) is True
    status = evaluate_license(payload)
    assert status.is_valid is True
    assert status.status == "ACTIVE"

    # 2. Tampering with grace_period_days from 14 to 60 invalidates digital signature
    tampered = dict(payload)
    tampered["grace_period_days"] = 60
    assert verify_license_signature(tampered) is False
    tampered_status = evaluate_license(tampered)
    assert tampered_status.is_valid is False
    assert tampered_status.status == "INVALID_SIGNATURE"


def test_legacy_version1_license_backward_compatibility():
    """Verify that legacy Version 1 licenses (issued without version field or signed grace)
    continue to verify and evaluate successfully without invalidating existing customers."""
    legacy_payload = {
        "client_name": "Old Client Chemist",
        "license_id": "LIC-LEGACY-CLIENT",
        "terminal_count": 1,
        "activation_date": (date.today() - timedelta(days=10)).isoformat(),
        "expiry_date": (date.today() + timedelta(days=350)).isoformat(),
        "edition": "COMMERCIAL",
        "features": "ALL",
        "version": 1,
    }
    legacy_payload["signature"] = sign_license(legacy_payload, PRIVATE_KEY_PATH)

    assert verify_license_signature(legacy_payload) is True
    status = evaluate_license(legacy_payload)
    assert status.is_valid is True
    assert status.status == "ACTIVE"
    assert status.client_name == "Old Client Chemist"


def test_unsupported_version_and_malformed_grace_period_rejection():
    """Verify that licenses with unsupported schema versions or malformed grace durations are rejected."""
    base_payload = {
        "client_name": "Version Test Store",
        "license_id": "LIC-VER-TEST",
        "terminal_count": 1,
        "activation_date": date.today().isoformat(),
        "edition": "COMMERCIAL",
        "features": "ALL",
    }

    # Unsupported version 99
    unsupported = dict(base_payload)
    unsupported["version"] = 99
    unsupported["signature"] = "dummy_sig"
    status_unsupported = evaluate_license(unsupported)
    assert status_unsupported.is_valid is False
    assert status_unsupported.status == "UNSUPPORTED_VERSION"

    # Malformed grace_period_days (>365)
    malformed_grace_high = dict(base_payload)
    malformed_grace_high["version"] = 2
    malformed_grace_high["grace_period_days"] = 500
    malformed_grace_high["signature"] = "dummy_sig"
    status_malf = evaluate_license(malformed_grace_high)
    assert status_malf.is_valid is False
    assert status_malf.status == "MALFORMED_LICENSE"

    # Malformed grace_period_days (negative)
    malformed_grace_neg = dict(base_payload)
    malformed_grace_neg["version"] = 2
    malformed_grace_neg["grace_period_days"] = -10
    malformed_grace_neg["signature"] = "dummy_sig"
    status_neg = evaluate_license(malformed_grace_neg)
    assert status_neg.is_valid is False
    assert status_neg.status == "MALFORMED_LICENSE"


def test_import_rejects_client_mismatch_and_preserves_valid_license(client: TestClient):
    """Ensure that importing a license for another client is rejected (400),
    and the current active license is safely preserved without corruption."""
    setup_payload = {
        "username": "admin_mismatch",
        "full_name": "Admin Mismatch",
        "password": "Password123!",
        "confirm_password": "Password123!",
        "store_name": "First Care Pharmacy",
    }
    setup_res = client.post("/api/v1/auth/first-run-setup", json=setup_payload)
    assert setup_res.status_code == 201
    admin_token = setup_res.json()["access_token"]
    admin_h = {"Authorization": f"Bearer {admin_token}"}

    # 1. Install genuine license for "First Care Pharmacy"
    valid_payload = {
        "client_name": "First Care Pharmacy",
        "license_id": "LIC-FIRST-01",
        "terminal_count": 5,
        "activation_date": date.today().isoformat(),
        "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
        "edition": "COMMERCIAL",
        "features": "ALL",
    }
    valid_payload["signature"] = sign_license(valid_payload, PRIVATE_KEY_PATH)

    res1 = client.post("/api/v1/system/license", json=valid_payload, headers=admin_h)
    assert res1.status_code == 200
    assert res1.json()["data"]["client_name"] == "First Care Pharmacy"
    assert res1.json()["data"]["license_id"] == "LIC-FIRST-01"

    # 2. Attempt to import valid license belonging to another client
    other_client_payload = {
        "client_name": "Second Care Pharmacy",
        "license_id": "LIC-SECOND-99",
        "terminal_count": 10,
        "activation_date": date.today().isoformat(),
        "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
        "edition": "COMMERCIAL",
        "features": "ALL",
    }
    other_client_payload["signature"] = sign_license(other_client_payload, PRIVATE_KEY_PATH)

    mismatch_res = client.post("/api/v1/system/license", json=other_client_payload, headers=admin_h)
    assert mismatch_res.status_code == 400
    assert "License client mismatch" in mismatch_res.json()["detail"]

    # Verify existing license is untouched
    current_res = client.get("/api/v1/system/license", headers=admin_h)
    assert current_res.status_code == 200
    assert current_res.json()["data"]["client_name"] == "First Care Pharmacy"
    assert current_res.json()["data"]["license_id"] == "LIC-FIRST-01"

    # 3. Attempt to import expired license
    expired_payload = {
        "client_name": "First Care Pharmacy",
        "license_id": "LIC-FIRST-EXP",
        "terminal_count": 5,
        "activation_date": (date.today() - timedelta(days=60)).isoformat(),
        "expiry_date": (date.today() - timedelta(days=30)).isoformat(),
        "edition": "COMMERCIAL",
        "features": "ALL",
    }
    expired_payload["signature"] = sign_license(expired_payload, PRIVATE_KEY_PATH)

    exp_res = client.post("/api/v1/system/license", json=expired_payload, headers=admin_h)
    assert exp_res.status_code == 400
    assert "Invalid license" in exp_res.json()["detail"]

    # Verify existing license still untouched
    current_res2 = client.get("/api/v1/system/license", headers=admin_h)
    assert current_res2.json()["data"]["license_id"] == "LIC-FIRST-01"

    # 4. Attempt to import tampered license
    tampered_payload = dict(valid_payload)
    tampered_payload["terminal_count"] = 999

    tamp_res = client.post("/api/v1/system/license", json=tampered_payload, headers=admin_h)
    assert tamp_res.status_code == 400
    assert "Invalid license" in tamp_res.json()["detail"]

    # Verify existing license still untouched
    current_res3 = client.get("/api/v1/system/license", headers=admin_h)
    assert current_res3.json()["data"]["license_id"] == "LIC-FIRST-01"

    # 5. Import legitimate renewed license for the same client succeeds
    renewed_payload = {
        "client_name": "First Care Pharmacy",
        "license_id": "LIC-FIRST-02-RENEWED",
        "terminal_count": 8,
        "activation_date": date.today().isoformat(),
        "expiry_date": (date.today() + timedelta(days=730)).isoformat(),
        "edition": "COMMERCIAL",
        "features": "ALL",
    }
    renewed_payload["signature"] = sign_license(renewed_payload, PRIVATE_KEY_PATH)

    renew_ok = client.post("/api/v1/system/license", json=renewed_payload, headers=admin_h)
    assert renew_ok.status_code == 200
    assert renew_ok.json()["data"]["license_id"] == "LIC-FIRST-02-RENEWED"
    assert renew_ok.json()["data"]["terminal_count"] == 8

    # Verify updated license is persisted
    current_res4 = client.get("/api/v1/system/license", headers=admin_h)
    assert current_res4.json()["data"]["license_id"] == "LIC-FIRST-02-RENEWED"




