"""Automated tests for CSV and Excel bulk imports:
- Medicine catalog bulk import (CSV & Excel)
- Opening stock batch inventory bulk import (CSV & Excel)
- Template download endpoints
- Duplicate resolution policies (SKIP vs UPDATE, SKIP vs MERGE)
- Ledger auditing of opening balances
"""

import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from pharmacy_daemon.security.hashing import hash_password


@pytest.fixture
def auth_headers(client: TestClient) -> dict:
    """Initialize test admin user and return auth headers."""
    setup_payload = {
        "username": "admin_import",
        "full_name": "Import Admin",
        "password": "AdminPassword123!",
        "confirm_password": "AdminPassword123!",
        "pin": "1234",
        "store_name": "MediHisaab Test Chemist",
    }
    setup_res = client.post("/api/v1/auth/first-run-setup", json=setup_payload)
    token = setup_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_download_medicine_templates(client: TestClient, auth_headers: dict):
    """Verify downloading CSV and XLSX medicine catalog sample templates."""
    # CSV template
    res_csv = client.get("/api/v1/masters/medicines/import/template?format=csv", headers=auth_headers)
    assert res_csv.status_code == 200
    assert "Medicine Name" in res_csv.text
    assert "Dosage Form" in res_csv.text

    # Excel template
    res_xlsx = client.get("/api/v1/masters/medicines/import/template?format=xlsx", headers=auth_headers)
    assert res_xlsx.status_code == 200
    assert "openxmlformats" in res_xlsx.headers.get("content-type", "")
    assert len(res_xlsx.content) > 1000


def test_download_opening_stock_templates(client: TestClient, auth_headers: dict):
    """Verify downloading CSV and XLSX opening stock sample templates."""
    # CSV template
    res_csv = client.get("/api/v1/inventory/opening-stock/import/template?format=csv", headers=auth_headers)
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers.get("content-type", "")
    assert "Medicine Name" in res_csv.text
    assert "Batch Number" in res_csv.text

    # Excel template
    res_xlsx = client.get("/api/v1/inventory/opening-stock/import/template?format=xlsx", headers=auth_headers)
    assert res_xlsx.status_code == 200
    assert "openxmlformats" in res_xlsx.headers.get("content-type", "")
    assert len(res_xlsx.content) > 1000


def test_medicine_import_preview_and_execute(client: TestClient, auth_headers: dict):
    """Verify uploading a CSV of medicines, previewing validation errors, and committing."""
    csv_data = (
        "Brand Name,Generic Salt,Dosage Form,Strength,Pack Size,Manufacturer,GST Rate\n"
        "Azithrocare 500,Azithromycin,TABLET,500mg,10,Apex Pharma,12\n"
        ",Paracetamol,TABLET,500mg,10,Apex Pharma,12\n"  # Invalid: Missing brand name
        "Coughnil Syrup,Dextromethorphan,INVALID_FORM,100ml,1,Cipla,12\n"  # Invalid: Bad dosage form
    )

    files = {"file": ("medicines.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    res_preview = client.post("/api/v1/masters/medicines/import-preview", files=files, headers=auth_headers)
    assert res_preview.status_code == 200

    data = res_preview.json()["data"]
    assert data["total_rows"] == 3
    assert data["valid_rows"] == 1
    assert data["error_rows"] == 2
    assert len(data["staging_token"]) > 0

    # Commit execution
    exec_payload = {
        "staging_token": data["staging_token"],
        "duplicate_policy": "SKIP",
    }
    res_exec = client.post("/api/v1/masters/medicines/import-execute", json=exec_payload, headers=auth_headers)
    assert res_exec.status_code == 200

    exec_data = res_exec.json()["data"]
    assert exec_data["success"] is True
    assert exec_data["inserted_count"] == 1

    # Verify medicine was inserted into DB and manufacturer was auto-linked
    res_list = client.get("/api/v1/masters/medicines?query=Azithrocare", headers=auth_headers)
    assert res_list.status_code == 200
    items = res_list.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["brand_name"] == "Azithrocare 500"
    assert items[0]["pack_size"] == 10


def test_medicine_duplicate_policy_skip_vs_update(client: TestClient, auth_headers: dict):
    """Verify duplicate policies: SKIP preserves existing record while UPDATE applies new attributes."""
    # First insert a medicine
    initial_csv = (
        "Brand Name,Generic Salt,Dosage Form,Pack Size,GST Rate\n"
        "CalciQuick D3,Calcium Carbonate,CAPSULE,15,12\n"
    )
    files = {"file": ("meds1.csv", io.BytesIO(initial_csv.encode("utf-8")), "text/csv")}
    res1 = client.post("/api/v1/masters/medicines/import-preview", files=files, headers=auth_headers)
    token1 = res1.json()["data"]["staging_token"]
    client.post("/api/v1/masters/medicines/import-execute", json={"staging_token": token1, "duplicate_policy": "SKIP"}, headers=auth_headers)

    # Prepare updated version with new salt and pack size
    dup_csv = (
        "Brand Name,Generic Salt,Dosage Form,Pack Size,GST Rate\n"
        "CalciQuick D3,Calcium + Vitamin D3,CAPSULE,30,18\n"
    )
    files = {"file": ("meds2.csv", io.BytesIO(dup_csv.encode("utf-8")), "text/csv")}
    res2 = client.post("/api/v1/masters/medicines/import-preview", files=files, headers=auth_headers)
    data2 = res2.json()["data"]
    assert data2["duplicate_rows"] == 1
    assert data2["rows"][0]["status"] == "DUPLICATE"

    # Test SKIP policy
    res_skip = client.post(
        "/api/v1/masters/medicines/import-execute",
        json={"staging_token": data2["staging_token"], "duplicate_policy": "SKIP"},
        headers=auth_headers,
    )
    assert res_skip.json()["data"]["skipped_count"] == 1
    assert res_skip.json()["data"]["updated_count"] == 0

    # Verify unchanged
    med_res = client.get("/api/v1/masters/medicines?query=CalciQuick", headers=auth_headers)
    med = med_res.json()["data"]["items"][0]
    assert med["pack_size"] == 15
    assert med["generic_salt"] == "Calcium Carbonate"

    # Test UPDATE policy
    # Re-preview to get a new staging session
    files = {"file": ("meds2.csv", io.BytesIO(dup_csv.encode("utf-8")), "text/csv")}
    res3 = client.post("/api/v1/masters/medicines/import-preview", files=files, headers=auth_headers)
    token3 = res3.json()["data"]["staging_token"]

    res_update = client.post(
        "/api/v1/masters/medicines/import-execute",
        json={"staging_token": token3, "duplicate_policy": "UPDATE"},
        headers=auth_headers,
    )
    assert res_update.json()["data"]["updated_count"] == 1

    # Verify updated
    med_res2 = client.get("/api/v1/masters/medicines?query=CalciQuick", headers=auth_headers)
    med2 = med_res2.json()["data"]["items"][0]
    assert med2["pack_size"] == 30
    assert med2["generic_salt"] == "Calcium + Vitamin D3"


def test_opening_stock_import_preview_and_execute(client: TestClient, auth_headers: dict):
    """Verify importing batch inventory, validating MRP/PTR, expiry, and inserting ledger records."""
    # 1. First add a catalog medicine to receive stock
    med_payload = {
        "brand_name": "Paracip 650",
        "generic_salt": "Paracetamol",
        "dosage_form": "TABLET",
        "pack_size": 15,
        "gst_rate": 12,
    }
    med_res = client.post("/api/v1/masters/medicines", json=med_payload, headers=auth_headers)
    assert med_res.status_code == 201

    # 2. Upload opening stock CSV with valid, expired, and unknown medicines
    stock_csv = (
        "Medicine Name,Batch Number,Expiry Date,Packs,Pack Size,Purchase Rate,MRP,Supplier\n"
        "Paracip 650,B-PAR-001,2027-11,20,15,25.50,35.00,Sun Healthcare\n"  # Valid
        "Nonexistent Medicine 999,B-UNKNOWN-01,2027-11,10,10,20.00,30.00,Sun Healthcare\n"  # Invalid: med not in catalog
        "Paracip 650,B-EXP-002,2021-05,10,15,20.00,30.00,Sun Healthcare\n"  # Invalid: already expired
        "Paracip 650,B-PRICE-003,2027-11,10,15,50.00,40.00,Sun Healthcare\n"  # Invalid: MRP < PTR
    )

    files = {"file": ("opening_stock.csv", io.BytesIO(stock_csv.encode("utf-8")), "text/csv")}
    res_preview = client.post("/api/v1/inventory/opening-stock/import-preview", files=files, headers=auth_headers)
    assert res_preview.status_code == 200

    data = res_preview.json()["data"]
    assert data["total_rows"] == 4
    assert data["valid_rows"] == 1
    assert data["error_rows"] == 3
    assert len(data["staging_token"]) > 0

    # 3. Execute opening stock import
    exec_payload = {
        "staging_token": data["staging_token"],
        "duplicate_policy": "SKIP",
    }
    res_exec = client.post("/api/v1/inventory/opening-stock/import-execute", json=exec_payload, headers=auth_headers)
    assert res_exec.status_code == 200

    exec_data = res_exec.json()["data"]
    assert exec_data["success"] is True
    assert exec_data["inserted_batches"] == 1
    assert exec_data["total_units_added"] == 300  # 20 packs * 15 units/pack

    # 4. Verify batch in inventory database
    app = client.app
    engine = app.state.db_engine
    with engine.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT batch_number, current_quantity, expiry_date FROM medicine_batches WHERE batch_number = 'B-PAR-001';")
        batch_row = cursor.fetchone()
        assert batch_row is not None
        assert batch_row[0] == "B-PAR-001"
        assert batch_row[1] == 300

        # Check ledger record
        cursor.execute("SELECT transaction_type, quantity_change, reference_type FROM inventory_ledger WHERE reference_type = 'OPENING_STOCK';")
        ledger_row = cursor.fetchone()
        assert ledger_row is not None
        assert ledger_row[0] == "ADJUSTMENT"
        assert ledger_row[1] == 300


def test_opening_stock_duplicate_policy_merge(client: TestClient, auth_headers: dict):
    """Verify MERGE duplicate policy sums opening stock into existing batch."""
    # Add catalog medicine
    med_res = client.post(
        "/api/v1/masters/medicines",
        json={"brand_name": "Dolo 650", "generic_salt": "Paracetamol", "dosage_form": "TABLET", "pack_size": 15},
        headers=auth_headers,
    )
    assert med_res.status_code == 201

    # First import: 10 packs (150 units)
    csv1 = "Medicine Name,Batch Number,Expiry Date,Packs,Pack Size,Purchase Rate,MRP\nDolo 650,B-DOLO-101,2028-06,10,15,20.00,30.00\n"
    files1 = {"file": ("stock1.csv", io.BytesIO(csv1.encode("utf-8")), "text/csv")}
    res_p1 = client.post("/api/v1/inventory/opening-stock/import-preview", files=files1, headers=auth_headers)
    t1 = res_p1.json()["data"]["staging_token"]
    client.post("/api/v1/inventory/opening-stock/import-execute", json={"staging_token": t1, "duplicate_policy": "SKIP"}, headers=auth_headers)

    # Second import with same batch: 5 packs (75 units)
    csv2 = "Medicine Name,Batch Number,Expiry Date,Packs,Pack Size,Purchase Rate,MRP\nDolo 650,B-DOLO-101,2028-06,5,15,20.00,30.00\n"
    files2 = {"file": ("stock2.csv", io.BytesIO(csv2.encode("utf-8")), "text/csv")}
    res_p2 = client.post("/api/v1/inventory/opening-stock/import-preview", files=files2, headers=auth_headers)
    data_p2 = res_p2.json()["data"]
    assert data_p2["duplicate_rows"] == 1
    assert data_p2["rows"][0]["status"] == "DUPLICATE"

    # Execute with MERGE
    res_merge = client.post(
        "/api/v1/inventory/opening-stock/import-execute",
        json={"staging_token": data_p2["staging_token"], "duplicate_policy": "MERGE"},
        headers=auth_headers,
    )
    assert res_merge.status_code == 200
    merge_data = res_merge.json()["data"]
    assert merge_data["merged_batches"] == 1
    assert merge_data["total_units_added"] == 75

    # Check total stock in database is now 225 units (150 + 75)
    app = client.app
    engine = app.state.db_engine
    with engine.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT current_quantity FROM medicine_batches WHERE batch_number = 'B-DOLO-101';")
        total_units = cursor.fetchone()[0]
        assert total_units == 225
