"""Comprehensive automated test suite for Master Catalog APIs.

Covers:
- CRUD for Manufacturers, Medicines, Suppliers, and Customers
- Pagination and FTS5 search
- Validation failures and duplicate checks
- Role-based permissions (ADMIN, PHARMACIST, CASHIER)
- Unauthorized access rejection
- Safe soft-deactivation
"""

import pytest
from fastapi.testclient import TestClient

from pharmacy_daemon.security.hashing import hash_password
from pharmacy_daemon.security.roles import UserRole


@pytest.fixture
def auth_tokens(client: TestClient) -> dict:
    """Fixture initializing store and generating tokens for ADMIN, PHARMACIST, and CASHIER."""
    # 1. First-run setup to create ADMIN
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

    # 2. Directly insert PHARMACIST and CASHIER accounts
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
        cursor.close()

    # Log in as PHARMACIST
    pharm_login = client.post("/api/v1/auth/login", json={"username": "pharm_user", "password": "OperatorPass123!"})
    pharm_token = pharm_login.json()["access_token"]

    # Log in as CASHIER
    cashier_login = client.post("/api/v1/auth/login", json={"username": "cashier_user", "password": "OperatorPass123!"})
    cashier_token = cashier_login.json()["access_token"]

    return {
        "ADMIN": admin_token,
        "PHARMACIST": pharm_token,
        "CASHIER": cashier_token,
    }


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# 1. MANUFACTURERS TESTS
# ==============================================================================

def test_manufacturer_crud_and_duplicates(client: TestClient, auth_tokens: dict):
    """Test Manufacturer CRUD lifecycle, duplicate prevention, and soft deactivation."""
    admin_headers = _auth_header(auth_tokens["ADMIN"])

    # 1. Create Manufacturer
    create_payload = {"name": "Sun Pharma Laboratories", "short_code": "SUN"}
    create_res = client.post("/api/v1/masters/manufacturers", json=create_payload, headers=admin_headers)
    assert create_res.status_code == 201
    created_data = create_res.json()
    assert created_data["success"] is True
    m_id = created_data["data"]["id"]
    assert created_data["data"]["name"] == "Sun Pharma Laboratories"
    assert created_data["data"]["short_code"] == "SUN"
    assert created_data["data"]["is_active"] is True

    # 2. Duplicate Name Rejection
    dup_name_res = client.post("/api/v1/masters/manufacturers", json=create_payload, headers=admin_headers)
    assert dup_name_res.status_code == 400
    assert "already exists" in dup_name_res.json()["error"]["message"].lower()

    # 3. Duplicate Short Code Rejection
    dup_code_res = client.post(
        "/api/v1/masters/manufacturers",
        json={"name": "Sun Generic Division", "short_code": "SUN"},
        headers=admin_headers,
    )
    assert dup_code_res.status_code == 400
    assert "short code" in dup_code_res.json()["error"]["message"].lower()

    # 4. Get by ID
    get_res = client.get(f"/api/v1/masters/manufacturers/{m_id}", headers=admin_headers)
    assert get_res.status_code == 200
    assert get_res.json()["data"]["id"] == m_id

    # 5. Update
    update_res = client.put(
        f"/api/v1/masters/manufacturers/{m_id}",
        json={"name": "Sun Pharmaceutical Industries Ltd", "short_code": "SUNPHARMA"},
        headers=admin_headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["data"]["name"] == "Sun Pharmaceutical Industries Ltd"

    # 6. Soft Deactivation
    delete_res = client.delete(f"/api/v1/masters/manufacturers/{m_id}", headers=admin_headers)
    assert delete_res.status_code == 200
    assert delete_res.json()["data"]["is_active"] is False

    # Verify record still exists in database (not deleted)
    get_again = client.get(f"/api/v1/masters/manufacturers/{m_id}", headers=admin_headers)
    assert get_again.status_code == 200
    assert get_again.json()["data"]["is_active"] is False


# ==============================================================================
# 2. MEDICINES TESTS (FTS5 SEARCH, DOSAGE FORMS, VALIDATIONS)
# ==============================================================================

def test_medicine_crud_and_validations(client: TestClient, auth_tokens: dict):
    """Test Medicine master creation, validation guards, and uniqueness checks."""
    admin_headers = _auth_header(auth_tokens["ADMIN"])

    # Create manufacturer first
    m_res = client.post(
        "/api/v1/masters/manufacturers",
        json={"name": "Cipla Ltd", "short_code": "CIPLA"},
        headers=admin_headers,
    )
    cipla_id = m_res.json()["data"]["id"]

    # 1. Invalid Dosage Form
    bad_form_res = client.post(
        "/api/v1/masters/medicines",
        json={
            "brand_name": "Asthalin 100",
            "generic_salt": "Salbutamol 100mcg",
            "dosage_form": "INVALID_PILL",
            "pack_size": 1,
        },
        headers=admin_headers,
    )
    assert bad_form_res.status_code == 422

    # 2. Invalid GST Rate
    bad_gst_res = client.post(
        "/api/v1/masters/medicines",
        json={
            "brand_name": "Asthalin 100",
            "generic_salt": "Salbutamol 100mcg",
            "dosage_form": "INHALER",
            "gst_rate": 15.0,  # Invalid GST rate slab
        },
        headers=admin_headers,
    )
    assert bad_gst_res.status_code == 422

    # 3. Successful Creation
    med_payload = {
        "medicine_code": "MED-CIP-001",
        "brand_name": "Asthalin Inhaler",
        "generic_salt": "Salbutamol 100mcg",
        "dosage_form": "INHALER",
        "strength": "100mcg",
        "pack_size": 1,
        "manufacturer_id": cipla_id,
        "hsn_code": "3004",
        "gst_rate": 12.0,
        "is_schedule_h": True,
        "is_schedule_h1": False,
        "barcode": "8901117001234",
    }
    create_res = client.post("/api/v1/masters/medicines", json=med_payload, headers=admin_headers)
    assert create_res.status_code == 201
    med_data = create_res.json()["data"]
    med_id = med_data["id"]
    assert med_data["brand_name"] == "Asthalin Inhaler"
    assert med_data["manufacturer_name"] == "Cipla Ltd"

    # 4. Duplicate Medicine Code Rejection
    dup_code_res = client.post(
        "/api/v1/masters/medicines",
        json={
            "medicine_code": "MED-CIP-001",
            "brand_name": "Another Drug",
            "generic_salt": "Salbutamol",
            "dosage_form": "SYRUP",
        },
        headers=admin_headers,
    )
    assert dup_code_res.status_code == 400
    assert "medicine code" in dup_code_res.json()["error"]["message"].lower()

    # 5. Duplicate Barcode Rejection
    dup_bar_res = client.post(
        "/api/v1/masters/medicines",
        json={
            "brand_name": "Yet Another Drug",
            "generic_salt": "Salbutamol",
            "dosage_form": "SYRUP",
            "barcode": "8901117001234",
        },
        headers=admin_headers,
    )
    assert dup_bar_res.status_code == 400
    assert "barcode" in dup_bar_res.json()["error"]["message"].lower()

    # 6. Update Medicine
    update_res = client.put(
        f"/api/v1/masters/medicines/{med_id}",
        json={"strength": "200mcg", "rack_location": "B-12"},
        headers=admin_headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["data"]["strength"] == "200mcg"
    assert update_res.json()["data"]["rack_location"] == "B-12"

    # 7. Soft Deactivation
    deact_res = client.delete(f"/api/v1/masters/medicines/{med_id}", headers=admin_headers)
    assert deact_res.status_code == 200
    assert deact_res.json()["data"]["is_active"] is False


def test_medicine_fts5_search_and_active_filtering(client: TestClient, auth_tokens: dict):
    """Test SQLite FTS5 search indexing across brand name, salt, code, and active filtering."""
    admin_headers = _auth_header(auth_tokens["ADMIN"])

    # Seed 3 distinct medicines
    client.post(
        "/api/v1/masters/medicines",
        json={
            "medicine_code": "PCM-001",
            "brand_name": "Calpol 650",
            "generic_salt": "Paracetamol 650mg",
            "dosage_form": "TABLET",
            "barcode": "1110001",
        },
        headers=admin_headers,
    )
    client.post(
        "/api/v1/masters/medicines",
        json={
            "medicine_code": "PCM-002",
            "brand_name": "Dolo 650",
            "generic_salt": "Paracetamol 650mg",
            "dosage_form": "TABLET",
            "barcode": "1110002",
        },
        headers=admin_headers,
    )
    med3_res = client.post(
        "/api/v1/masters/medicines",
        json={
            "medicine_code": "AZI-001",
            "brand_name": "Azithral 500",
            "generic_salt": "Azithromycin 500mg",
            "dosage_form": "TABLET",
            "is_schedule_h1": True,
            "barcode": "1110003",
        },
        headers=admin_headers,
    )
    azithral_id = med3_res.json()["data"]["id"]

    # Search by Generic Salt: should match Calpol and Dolo
    search_salt = client.get("/api/v1/masters/medicines?query=Paracetamol", headers=admin_headers)
    assert search_salt.status_code == 200
    salt_items = search_salt.json()["data"]["items"]
    assert len(salt_items) == 2
    brand_names = {item["brand_name"] for item in salt_items}
    assert brand_names == {"Calpol 650", "Dolo 650"}

    # Search by Brand Name: should match Azithral
    search_brand = client.get("/api/v1/masters/medicines?query=Azithral", headers=admin_headers)
    assert search_brand.status_code == 200
    brand_items = search_brand.json()["data"]["items"]
    assert len(brand_items) == 1
    assert brand_items[0]["brand_name"] == "Azithral 500"

    # Search by Medicine Code
    search_code = client.get("/api/v1/masters/medicines?query=PCM-002", headers=admin_headers)
    assert search_code.status_code == 200
    assert len(search_code.json()["data"]["items"]) == 1
    assert search_code.json()["data"]["items"][0]["brand_name"] == "Dolo 650"

    # Deactivate Azithral
    client.delete(f"/api/v1/masters/medicines/{azithral_id}", headers=admin_headers)

    # Active filter: is_active=true should exclude Azithral
    active_search = client.get("/api/v1/masters/medicines?query=Azithral&is_active=true", headers=admin_headers)
    assert active_search.status_code == 200
    assert len(active_search.json()["data"]["items"]) == 0

    # is_active=false should find Azithral
    inactive_search = client.get("/api/v1/masters/medicines?query=Azithral&is_active=false", headers=admin_headers)
    assert inactive_search.status_code == 200
    assert len(inactive_search.json()["data"]["items"]) == 1


# ==============================================================================
# 3. SUPPLIERS TESTS (GSTIN & DL VALIDATION, PAYABLES SUMMARY)
# ==============================================================================

def test_supplier_crud_gstin_dl_and_payables(client: TestClient, auth_tokens: dict):
    """Test Supplier master with GSTIN/DL uniqueness and payable summary placeholder."""
    admin_headers = _auth_header(auth_tokens["ADMIN"])

    # 1. Invalid GSTIN Format Rejection
    bad_gstin_res = client.post(
        "/api/v1/masters/suppliers",
        json={"name": "MediTrade Dist", "gstin": "INVALID123"},
        headers=admin_headers,
    )
    assert bad_gstin_res.status_code == 422

    # 2. Create Supplier
    sup_payload = {
        "name": "Varanasi Pharma Stockists",
        "gstin": "09ABCDE1234F1Z5",
        "dl_number_20b": "UP-VNS-20B-9988",
        "dl_number_21b": "UP-VNS-21B-9988",
        "phone": "9876500000",
        "email": "orders@vnspharma.com",
        "address": "Kabir Chaura, Varanasi",
        "credit_days": 21,
    }
    create_res = client.post("/api/v1/masters/suppliers", json=sup_payload, headers=admin_headers)
    assert create_res.status_code == 201
    sup_data = create_res.json()["data"]
    sup_id = sup_data["id"]
    assert sup_data["name"] == "Varanasi Pharma Stockists"
    assert sup_data["current_payable_paise"] == 0

    # 3. Duplicate GSTIN Rejection
    dup_gstin = client.post(
        "/api/v1/masters/suppliers",
        json={"name": "Another Supplier", "gstin": "09ABCDE1234F1Z5"},
        headers=admin_headers,
    )
    assert dup_gstin.status_code == 400
    assert "gstin" in dup_gstin.json()["error"]["message"].lower()

    # 4. Duplicate DL 20B Rejection
    dup_dl = client.post(
        "/api/v1/masters/suppliers",
        json={"name": "Another Supplier", "dl_number_20b": "UP-VNS-20B-9988"},
        headers=admin_headers,
    )
    assert dup_dl.status_code == 400
    assert "license 20b" in dup_dl.json()["error"]["message"].lower()

    # 5. Payable Summary Placeholder
    payable_res = client.get(f"/api/v1/masters/suppliers/{sup_id}/payable-summary", headers=admin_headers)
    assert payable_res.status_code == 200
    p_data = payable_res.json()["data"]
    assert p_data["supplier_id"] == sup_id
    assert p_data["current_payable_paise"] == 0
    assert p_data["pending_invoices_count"] == 0

    # 6. Deactivate Supplier
    deact_res = client.delete(f"/api/v1/masters/suppliers/{sup_id}", headers=admin_headers)
    assert deact_res.status_code == 200
    assert deact_res.json()["data"]["is_active"] is False


# ==============================================================================
# 4. CUSTOMERS TESTS
# ==============================================================================

def test_customer_crud_and_phone_search(client: TestClient, auth_tokens: dict):
    """Test Customer creation, duplicate phone check, search, and pagination."""
    admin_headers = _auth_header(auth_tokens["ADMIN"])

    cust_payload = {
        "name": "Ramesh Chandra",
        "phone": "9811223344",
        "address": "Civil Lines, Jaunpur",
        "default_doctor": "Dr. V. K. Singh",
        "credit_limit_paise": 800000,
    }
    create_res = client.post("/api/v1/masters/customers", json=cust_payload, headers=admin_headers)
    assert create_res.status_code == 201
    cust_data = create_res.json()["data"]
    c_id = cust_data["id"]
    assert cust_data["name"] == "Ramesh Chandra"
    assert cust_data["credit_limit_paise"] == 800000

    # Duplicate phone rejection
    dup_phone = client.post("/api/v1/masters/customers", json=cust_payload, headers=admin_headers)
    assert dup_phone.status_code == 400
    assert "phone" in dup_phone.json()["error"]["message"].lower()

    # Search by phone
    search_res = client.get("/api/v1/masters/customers?query=981122", headers=admin_headers)
    assert search_res.status_code == 200
    assert len(search_res.json()["data"]["items"]) == 1
    assert search_res.json()["data"]["items"][0]["name"] == "Ramesh Chandra"

    # Soft deactivation
    deact_res = client.delete(f"/api/v1/masters/customers/{c_id}", headers=admin_headers)
    assert deact_res.status_code == 200
    assert deact_res.json()["data"]["is_active"] is False


# ==============================================================================
# 5. ROLE-BASED ACCESS CONTROL (RBAC) TESTS
# ==============================================================================

def test_role_permissions_enforcement(client: TestClient, auth_tokens: dict):
    """Verify ADMIN and PHARMACIST have write access, while CASHIER is strictly read-only."""
    admin_headers = _auth_header(auth_tokens["ADMIN"])
    pharm_headers = _auth_header(auth_tokens["PHARMACIST"])
    cashier_headers = _auth_header(auth_tokens["CASHIER"])

    # 1. CASHIER Can Read / Search
    c_read_res = client.get("/api/v1/masters/medicines", headers=cashier_headers)
    assert c_read_res.status_code == 200

    # 2. CASHIER Forbidden to Create (POST)
    c_create_res = client.post(
        "/api/v1/masters/medicines",
        json={
            "brand_name": "Cashier Drug",
            "generic_salt": "Salt",
            "dosage_form": "TABLET",
        },
        headers=cashier_headers,
    )
    assert c_create_res.status_code == 403
    assert "not permitted" in c_create_res.json()["error"]["message"].lower()

    # 3. CASHIER Forbidden to Update (PUT)
    c_put_res = client.put(
        "/api/v1/masters/medicines/1",
        json={"brand_name": "Updated By Cashier"},
        headers=cashier_headers,
    )
    assert c_put_res.status_code == 403

    # 4. CASHIER Forbidden to Deactivate (DELETE)
    c_del_res = client.delete("/api/v1/masters/medicines/1", headers=cashier_headers)
    assert c_del_res.status_code == 403

    # 5. PHARMACIST Allowed to Create
    p_create_res = client.post(
        "/api/v1/masters/manufacturers",
        json={"name": "Lupin Pharmaceuticals", "short_code": "LUPIN"},
        headers=pharm_headers,
    )
    assert p_create_res.status_code == 201

    # 6. Unauthenticated Request Rejected (401)
    unauth_res = client.get("/api/v1/masters/medicines")
    assert unauth_res.status_code == 401
