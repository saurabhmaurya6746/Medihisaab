"""Automated integration tests for the Online Pharmacy Portal API."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import portal_service.db.session as session_module
from portal_service.app import app
from portal_service.db.session import Base, get_db
from portal_service.db.migrations import seed_default_data

# Use shared in-memory SQLite database for test execution
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Patch module engine and session
session_module.engine = test_engine
session_module.SessionLocal = TestingSessionLocal


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create schema and seed initial data once for the test session."""
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    try:
        seed_default_data(db)
    finally:
        db.close()
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    """Provide a database session fixture."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(db_session):
    """FastAPI test client with database override."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ==================== Health & Store Info Tests ====================


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert data["service"] == "pharmacy-online-portal-api"


def test_store_info(client):
    response = client.get("/api/v1/store-info")
    assert response.status_code == 200
    data = response.json()
    assert "Apex Healthcare" in data["store_name"]
    assert "Prescription medicines (Rx) cannot be dispensed" in data["rx_policy_notice"]
    assert data["delivery_fee_paise"] > 0


# ==================== Catalog Browsing Tests ====================


def test_list_categories(client):
    response = client.get("/api/v1/catalog/categories")
    assert response.status_code == 200
    categories = response.json()
    assert len(categories) >= 5
    slugs = [c["slug"] for c in categories]
    assert "prescription-medicines" in slugs
    assert "pain-relief-fever" in slugs


def test_list_products_and_search(client):
    # 1. All products
    response = client.get("/api/v1/catalog/products")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 10
    assert len(data["items"]) >= 10

    # 2. Search by name
    search_resp = client.get("/api/v1/catalog/products?search=Paracetamol")
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    assert any("Paracetamol" in p["name"] for p in search_data["items"])

    # 3. Filter by category
    cat_resp = client.get("/api/v1/catalog/products?category_slug=pain-relief-fever")
    assert cat_resp.status_code == 200
    cat_data = cat_resp.json()
    assert all(p["category_slug"] == "pain-relief-fever" for p in cat_data["items"])

    # 4. Filter by prescription required
    rx_resp = client.get("/api/v1/catalog/products?prescription_only=true")
    assert rx_resp.status_code == 200
    rx_data = rx_resp.json()
    assert all(p["is_prescription_required"] is True for p in rx_data["items"])


def test_get_product_by_slug(client):
    response = client.get("/api/v1/catalog/products/paracetamol-650mg-tablets")
    assert response.status_code == 200
    p = response.json()
    assert p["name"] == "Paracetamol 650mg Tablets"
    assert p["is_prescription_required"] is False
    assert p["selling_price_paise"] == 3000

    # Non-existent product
    notFound = client.get("/api/v1/catalog/products/unknown-tablet-xyz")
    assert notFound.status_code == 404


# ==================== Customer Auth & Isolation Tests ====================


def test_customer_registration_and_login(client):
    email = "new_customer_test@example.com"
    pwd = "MySecretPass2026!"

    # 1. Register
    reg_resp = client.post(
        "/api/v1/customer/register",
        json={
            "email": email,
            "password": pwd,
            "full_name": "Anita Desai",
            "phone": "+91 91234 56789",
            "delivery_address": "House 12, Lake View Colony, Hyderabad",
        },
    )
    assert reg_resp.status_code == 201
    reg_data = reg_resp.json()
    assert "access_token" in reg_data
    assert reg_data["customer"]["email"] == email

    # 2. Conflict on duplicate register
    dup_resp = client.post(
        "/api/v1/customer/register",
        json={
            "email": email,
            "password": pwd,
            "full_name": "Anita Duplicate",
            "phone": "+91 91234 56789",
        },
    )
    assert dup_resp.status_code == 409

    # 3. Login
    login_resp = client.post(
        "/api/v1/customer/login",
        json={"email": email, "password": pwd},
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    token = login_data["access_token"]
    assert token

    # 4. Access /me
    me_resp = client.get("/api/v1/customer/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == email

    # 5. Update /me profile
    up_resp = client.put(
        "/api/v1/customer/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"delivery_address": "Updated Address 404, Tech Park"},
    )
    assert up_resp.status_code == 200
    assert up_resp.json()["delivery_address"] == "Updated Address 404, Tech Park"


# ==================== Order Workflows & Rx Enforcement Tests ====================


def test_otc_order_starts_in_pending_confirmation(client):
    """OTC order should enter PENDING_CONFIRMATION awaiting staff inventory acceptance."""
    # Login as demo customer
    login_resp = client.post(
        "/api/v1/customer/login",
        json={"email": "customer@example.com", "password": "CustomerPass2026!"},
    )
    token = login_resp.json()["access_token"]

    # Fetch Paracetamol
    p_resp = client.get("/api/v1/catalog/products/paracetamol-650mg-tablets")
    para_id = p_resp.json()["id"]

    order_resp = client.post(
        "/api/v1/customer/orders",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "fulfillment_type": "PICKUP",
            "payment_method": "PAY_AT_PICKUP",
            "items": [{"product_id": para_id, "quantity": 2}],
        },
    )
    assert order_resp.status_code == 201
    order = order_resp.json()
    assert order["status"] == "PENDING_CONFIRMATION"
    assert order["has_prescription_items"] is False
    assert order["subtotal_paise"] == 6000
    assert order["delivery_fee_paise"] == 0  # Pickup order has zero delivery fee
    assert order["total_paise"] == 6000


def test_rx_order_requires_pharmacist_review(client):
    """Prescription item order must automatically enter PHARMACIST_REVIEW status."""
    login_resp = client.post(
        "/api/v1/customer/login",
        json={"email": "customer@example.com", "password": "CustomerPass2026!"},
    )
    token = login_resp.json()["access_token"]

    # Fetch Amoxicillin (Rx)
    p_resp = client.get("/api/v1/catalog/products/amoxicillin-500mg-capsules")
    amox_id = p_resp.json()["id"]

    order_resp = client.post(
        "/api/v1/customer/orders",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "fulfillment_type": "DELIVERY",
            "delivery_address": "Flat 302, Green Meadows, Hyderabad",
            "payment_method": "CASH_ON_DELIVERY",
            "customer_phone": "+91 98490 12345",
            "items": [{"product_id": amox_id, "quantity": 1}],
        },
    )
    assert order_resp.status_code == 201
    order = order_resp.json()
    assert order["status"] == "PHARMACIST_REVIEW"
    assert order["has_prescription_items"] is True
    assert order["delivery_fee_paise"] == 4000  # Subtotal 11000 < 50000 free threshold


def test_customer_order_isolation(client):
    """Customer A cannot view or manipulate Customer B's orders."""
    # 1. Customer A places order
    login_a = client.post(
        "/api/v1/customer/login",
        json={"email": "customer@example.com", "password": "CustomerPass2026!"},
    )
    token_a = login_a.json()["access_token"]

    p_resp = client.get("/api/v1/catalog/products/paracetamol-650mg-tablets")
    para_id = p_resp.json()["id"]

    order_a = client.post(
        "/api/v1/customer/orders",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "fulfillment_type": "PICKUP",
            "payment_method": "PAY_AT_PICKUP",
            "items": [{"product_id": para_id, "quantity": 1}],
        },
    ).json()

    # 2. Register Customer B
    client.post(
        "/api/v1/customer/register",
        json={
            "email": "customer_b@example.com",
            "password": "PasswordB2026!",
            "full_name": "Bhavani Rao",
            "phone": "+91 98765 00000",
        },
    )
    login_b = client.post(
        "/api/v1/customer/login",
        json={"email": "customer_b@example.com", "password": "PasswordB2026!"},
    )
    token_b = login_b.json()["access_token"]

    # 3. Customer B attempts to get Customer A's order -> Must return 404
    forbidden_resp = client.get(
        f"/api/v1/customer/orders/{order_a['id']}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert forbidden_resp.status_code == 404


# ==================== Staff Roles, Approvals & Audits Tests ====================


def test_staff_roles_and_rx_approval(client):
    """Regular staff cannot approve Rx review; only Pharmacist or Admin can."""
    # 1. Customer places Rx order
    login_cust = client.post(
        "/api/v1/customer/login",
        json={"email": "customer@example.com", "password": "CustomerPass2026!"},
    )
    cust_token = login_cust.json()["access_token"]

    amox_id = client.get("/api/v1/catalog/products/amoxicillin-500mg-capsules").json()["id"]
    rx_order = client.post(
        "/api/v1/customer/orders",
        headers={"Authorization": f"Bearer {cust_token}"},
        json={
            "fulfillment_type": "PICKUP",
            "payment_method": "PAY_AT_PICKUP",
            "items": [{"product_id": amox_id, "quantity": 1}],
        },
    ).json()
    assert rx_order["status"] == "PHARMACIST_REVIEW"

    # 2. Regular staff attempts to approve -> 403 Forbidden
    login_staff = client.post(
        "/api/v1/staff/login",
        json={"email": "staff@apexhealthcare.com", "password": "StaffPass2026!"},
    )
    assert login_staff.status_code == 200, login_staff.text
    staff_token = login_staff.json()["access_token"]

    fail_resp = client.put(
        f"/api/v1/staff/orders/{rx_order['id']}/status",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={"status": "CONFIRMED", "notes": "Fulfillment staff attempted approval"},
    )
    assert fail_resp.status_code == 403
    assert "Registered Pharmacist" in fail_resp.json()["detail"]

    # 3. Pharmacist approves -> 200 OK
    login_pharm = client.post(
        "/api/v1/staff/login",
        json={"email": "pharmacist@apexhealthcare.com", "password": "PharmSecure2026!"},
    )
    assert login_pharm.status_code == 200, login_pharm.text
    pharm_token = login_pharm.json()["access_token"]

    approve_resp = client.put(
        f"/api/v1/staff/orders/{rx_order['id']}/status",
        headers={"Authorization": f"Bearer {pharm_token}"},
        json={
            "status": "CONFIRMED",
            "pharmacist_notes": "Prescription verified with patient doctor; batch #B892 assigned.",
            "notes": "Prescription verified and approved for dispensing.",
        },
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "CONFIRMED"
    assert "Prescription verified" in approve_resp.json()["pharmacist_notes"]


def test_staff_dashboard_and_audit_trail(client):
    # Login as admin
    login_admin = client.post(
        "/api/v1/staff/login",
        json={"email": "admin@apexhealthcare.com", "password": "AdminPassword2026!"},
    )
    assert login_admin.status_code == 200, login_admin.text
    admin_token = login_admin.json()["access_token"]

    # Dashboard metrics
    metrics_resp = client.get(
        "/api/v1/staff/dashboard/metrics",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert metrics_resp.status_code == 200
    metrics = metrics_resp.json()
    assert metrics["total_orders"] > 0
    assert metrics["total_products_count"] > 0

    # Operational customer lookup
    cust_resp = client.get(
        "/api/v1/staff/customers",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert cust_resp.status_code == 200
    custs = cust_resp.json()
    assert len(custs) > 0
    # Verify no password hashes or tokens leaked
    for c in custs:
        assert "password" not in c
        assert "password_hash" not in c
        assert "email" in c
        assert "orders_count" in c

    # Audit logs
    audit_resp = client.get(
        "/api/v1/staff/audit-logs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert audit_resp.status_code == 200
    logs = audit_resp.json()
    assert len(logs) > 0
    assert any(log["action"] == "ORDER_STATUS_CHANGED" for log in logs)
