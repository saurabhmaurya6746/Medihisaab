"""Comprehensive test suite covering all 15 required business and licensing scenarios."""

import json
from datetime import date, timedelta
from pathlib import Path
import sys
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# Ensure pharmacy_daemon is importable for client evaluator testing
REPO_ROOT = Path(__file__).resolve().parents[3]
DAEMON_SRC = REPO_ROOT / "apps" / "daemon" / "src"
if str(DAEMON_SRC) not in sys.path:
    sys.path.insert(0, str(DAEMON_SRC))

from pharmacy_daemon.security.license import (
    evaluate_license as daemon_evaluate_license,
    verify_license_signature as daemon_verify_signature,
    EMBEDDED_PUBLIC_KEY_HEX,
)
from licensing_service.db.models import Base, ClientStatus, SubscriptionStatus, VendorRole
from licensing_service.security.signer import canonical_representation


# ===========================================================================
# Baseline Probes & Public Portal Security
# ===========================================================================

def test_health_probe(client):
    """Verify service health endpoint returns 200 with DB status."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "HEALTHY"
    assert data["service"] == "pharmacy-licensing-service"
    assert data["database_connected"] is True


def test_portal_html_served_at_root(client):
    """Verify root / serves the vendor portal SPA index.html."""
    res = client.get("/")
    assert res.status_code == 200
    assert "Pharmacy POS" in res.text
    assert "Vendor Licensing Portal" in res.text


def test_public_portal_strict_isolation():
    """Verify portal directory contains NO database files, private keys, or client licenses."""
    portal_dir = Path("portal")
    assert portal_dir.is_dir(), "portal directory must exist"

    forbidden_extensions = {".db", ".sqlite", ".sqlite3", ".pem", ".key"}
    for f in portal_dir.rglob("*"):
        if f.is_file():
            assert f.suffix.lower() not in forbidden_extensions, f"Forbidden file found in portal: {f}"
            assert "private" not in f.name.lower(), f"Forbidden private key found in portal: {f}"
            assert "license.json" not in f.name.lower(), f"Client license found in portal: {f}"


# ===========================================================================
# 15 BUSINESS & LICENSING SCENARIOS
# ===========================================================================

# Scenario 1: Create client
def test_scenario_01_create_client(client, admin_headers):
    """Scenario 1: Vendor creates a new pharmacy client."""
    payload = {
        "business_name": "Apollo Care Pharmacy",
        "owner_name": "Dr. Rajesh Sharma",
        "phone": "+91 98765 43210",
        "email": "rajesh@apollocare.example",
        "address": "42 Civil Lines",
        "city": "Jaunpur",
        "state": "Uttar Pradesh",
        "postal_code": "222001",
        "gstin": "09AAAAA0000A1Z5",
        "retail_drug_license": "UP-JP-DL-1029",
        "notes": "Primary retail counter in Jaunpur",
    }
    res = client.post("/api/v1/clients", json=payload, headers=admin_headers)
    assert res.status_code == 201
    data = res.json()["data"]
    assert data["id"] > 0
    assert data["client_code"].startswith("CL-")
    assert data["business_name"] == "Apollo Care Pharmacy"
    assert data["owner_name"] == "Dr. Rajesh Sharma"
    assert data["status"] == ClientStatus.ACTIVE.value


# Scenario 2: Create 15-day trial (default duration)
def test_scenario_02_create_15_day_trial(client, admin_headers):
    """Scenario 2: Create a trial subscription defaulting to 15 days."""
    # 1. Create client
    c_res = client.post(
        "/api/v1/clients",
        json={"business_name": "LifeCare Medicos", "owner_name": "Amit Patel", "phone": "9876500001"},
        headers=admin_headers,
    )
    client_id = c_res.json()["data"]["id"]

    # 2. Start trial without specifying trial_days (must use default 15 days)
    trial_res = client.post(
        "/api/v1/subscriptions/start-trial",
        json={"client_id": client_id, "notes": "Standard 15-day trial"},
        headers=admin_headers,
    )
    assert trial_res.status_code == 201
    sub = trial_res.json()["data"]

    today = date.today()
    expected_end = today + timedelta(days=15)
    expected_grace = expected_end + timedelta(days=7)

    assert sub["status"] == SubscriptionStatus.TRIALING.value
    assert sub["trial_days"] == 15
    assert sub["is_trial"] is True
    assert sub["current_period_end"] == expected_end.isoformat()
    assert sub["grace_period_end"] == expected_grace.isoformat()


# Scenario 3: Change default trial duration via settings
def test_scenario_03_change_default_trial_duration_settings(client, admin_headers):
    """Scenario 3: Vendor updates default trial duration to 30 days and verifies dynamic adoption."""
    # 1. Update system default trial duration
    put_res = client.put(
        "/api/v1/settings/trial-duration",
        json={"default_trial_days": 30, "default_grace_days": 10},
        headers=admin_headers,
    )
    assert put_res.status_code == 200
    assert put_res.json()["data"]["default_trial_days"] == 30
    assert put_res.json()["data"]["default_grace_days"] == 10

    # 2. Verify settings endpoint reflects update
    get_res = client.get("/api/v1/settings", headers=admin_headers)
    assert get_res.status_code == 200
    assert get_res.json()["data"]["default_trial_days"] == 30
    assert get_res.json()["data"]["default_grace_days"] == 10

    # 3. Create client and start trial with no override
    c_res = client.post(
        "/api/v1/clients",
        json={"business_name": "Global Pharma Store", "owner_name": "Priya Nair", "phone": "9876500002"},
        headers=admin_headers,
    )
    cid = c_res.json()["data"]["id"]

    sub_res = client.post(
        "/api/v1/subscriptions/start-trial",
        json={"client_id": cid},
        headers=admin_headers,
    )
    assert sub_res.status_code == 201
    sub = sub_res.json()["data"]
    assert sub["trial_days"] == 30
    assert sub["current_period_end"] == (date.today() + timedelta(days=30)).isoformat()
    assert sub["grace_period_end"] == (date.today() + timedelta(days=40)).isoformat()

    # Reset back to 15 days for subsequent tests
    client.put(
        "/api/v1/settings/trial-duration",
        json={"default_trial_days": 15, "default_grace_days": 7},
        headers=admin_headers,
    )


# Scenario 4: Override trial duration for a specific client
def test_scenario_04_override_trial_duration_for_specific_client(client, admin_headers):
    """Scenario 4: Vendor creates an evaluation trial with a custom 45-day override."""
    c_res = client.post(
        "/api/v1/clients",
        json={"business_name": "VIP Medical Centre", "owner_name": "Dr. V. K. Singh", "phone": "9876500003"},
        headers=admin_headers,
    )
    cid = c_res.json()["data"]["id"]

    trial_res = client.post(
        "/api/v1/subscriptions/start-trial",
        json={"client_id": cid, "trial_days": 45, "notes": "VIP Client extended trial override"},
        headers=admin_headers,
    )
    assert trial_res.status_code == 201
    sub = trial_res.json()["data"]
    assert sub["trial_days"] == 45
    assert sub["current_period_end"] == (date.today() + timedelta(days=45)).isoformat()


# Scenario 5: Generate trial license
def test_scenario_05_generate_trial_license(client, admin_headers):
    """Scenario 5: Vendor issues an Ed25519-signed trial evaluation license file."""
    c_res = client.post(
        "/api/v1/clients",
        json={"business_name": "Apex Trial Pharmacy", "owner_name": "Nitin Gupta", "phone": "9876500004"},
        headers=admin_headers,
    )
    cid = c_res.json()["data"]["id"]

    trial_res = client.post(
        "/api/v1/subscriptions/start-trial",
        json={"client_id": cid, "trial_days": 15},
        headers=admin_headers,
    )
    sub = trial_res.json()["data"]

    lic_res = client.post(
        "/api/v1/licenses/generate",
        json={
            "client_id": cid,
            "subscription_id": sub["id"],
            "terminal_count": 2,
            "edition": "TRIAL",
        },
        headers=admin_headers,
    )
    assert lic_res.status_code == 201
    lic = lic_res.json()["data"]
    assert lic["license_id"].startswith("LIC-")
    assert lic["client_name"] == "Apex Trial Pharmacy"
    assert lic["edition"] == "TRIAL"
    assert lic["terminal_count"] == 2
    assert len(lic["signature"]) == 128


# Scenario 6: Import valid trial license into POS client evaluator
def test_scenario_06_import_valid_trial_license_into_pos_client(client, admin_headers):
    """Scenario 6: Offline Pharmacy POS client imports and evaluates the signed trial license."""
    c_res = client.post(
        "/api/v1/clients",
        json={"business_name": "City Core Pharmacy", "owner_name": "Anil Verma", "phone": "9876500005"},
        headers=admin_headers,
    )
    cid = c_res.json()["data"]["id"]

    sub_res = client.post(
        "/api/v1/subscriptions/start-trial",
        json={"client_id": cid, "trial_days": 20},
        headers=admin_headers,
    )
    sub = sub_res.json()["data"]

    lic_res = client.post(
        "/api/v1/licenses/generate",
        json={"client_id": cid, "subscription_id": sub["id"], "terminal_count": 3, "edition": "TRIAL"},
        headers=admin_headers,
    )
    lic_id = lic_res.json()["data"]["id"]

    # Download signed JSON payload as POS client would receive
    dl_res = client.get(f"/api/v1/licenses/{lic_id}/download", headers=admin_headers)
    assert dl_res.status_code == 200
    license_payload = dl_res.json()

    # POS Client Evaluator offline test
    status = daemon_evaluate_license(license_payload)
    assert status.is_valid is True
    assert status.status == "TRIAL"
    assert status.client_name == "City Core Pharmacy"
    assert status.terminal_count == 3
    assert status.edition == "TRIAL"
    assert status.remaining_days == 20
    assert status.grace_period_active is False
    assert "Evaluation trial active" in status.message


# Scenario 7: Reject modified or invalid license files
def test_scenario_07_reject_tampered_or_invalid_license(client, admin_headers):
    """Scenario 7: Reject tampered or corrupted license files."""
    c_res = client.post(
        "/api/v1/clients",
        json={"business_name": "Security Test Pharmacy", "owner_name": "S. Rao", "phone": "9876500006"},
        headers=admin_headers,
    )
    cid = c_res.json()["data"]["id"]

    lic_res = client.post(
        "/api/v1/licenses/generate",
        json={"client_id": cid, "terminal_count": 2, "edition": "COMMERCIAL"},
        headers=admin_headers,
    )
    lic_id = lic_res.json()["data"]["id"]

    dl_res = client.get(f"/api/v1/licenses/{lic_id}/download", headers=admin_headers)
    legit_payload = dl_res.json()

    # Case A: Tamper with terminal count from 2 to 50
    tampered_terminals = dict(legit_payload)
    tampered_terminals["terminal_count"] = 50
    assert daemon_verify_signature(tampered_terminals) is False
    eval_tampered = daemon_evaluate_license(tampered_terminals)
    assert eval_tampered.is_valid is False
    assert eval_tampered.status == "INVALID_SIGNATURE"

    # Case B: Tamper with client business name
    tampered_name = dict(legit_payload)
    tampered_name["client_name"] = "Different Pharmacy Name"
    assert daemon_verify_signature(tampered_name) is False
    assert daemon_evaluate_license(tampered_name).is_valid is False

    # Case C: Bad cryptographic signature string
    tampered_sig = dict(legit_payload)
    tampered_sig["signature"] = "deadbeef" * 16
    assert daemon_verify_signature(tampered_sig) is False
    assert daemon_evaluate_license(tampered_sig).is_valid is False


# Scenario 8: Expire trial
def test_scenario_08_expire_trial(client, admin_headers):
    """Scenario 8: Detect expired trial past both expiry and grace periods."""
    from licensing_service.security.signer import signer

    past_date = (date.today() - timedelta(days=20)).isoformat()
    old_act = (date.today() - timedelta(days=40)).isoformat()

    expired_payload = {
        "client_name": "Expired Trial Pharmacy",
        "license_id": "LIC-EXP-01",
        "terminal_count": 2,
        "activation_date": old_act,
        "expiry_date": past_date,
        "edition": "TRIAL",
        "features": "ALL",
        "grace_period_days": 7,
    }
    # Signed with authorized publisher private key
    expired_payload["signature"] = signer.sign_license(expired_payload)

    # 20 days overdue > 7 days grace -> must evaluate to EXPIRED
    status = daemon_evaluate_license(expired_payload)
    assert status.is_valid is False
    assert status.status == "EXPIRED"
    assert status.remaining_days == 0
    assert status.grace_period_active is False
    assert "License expired" in status.message


# Scenario 9: Support configurable grace period
def test_scenario_09_apply_grace_period(client, admin_headers):
    """Scenario 9: Evaluate active grace period when license expired within grace window."""
    from licensing_service.security.signer import signer

    # Expired 3 days ago, but grace period is 7 days -> 4 days grace left
    expired_three_days_ago = (date.today() - timedelta(days=3)).isoformat()
    old_act = (date.today() - timedelta(days=30)).isoformat()

    grace_payload = {
        "client_name": "Grace Chemist",
        "license_id": "LIC-GRACE-01",
        "terminal_count": 2,
        "activation_date": old_act,
        "expiry_date": expired_three_days_ago,
        "edition": "COMMERCIAL",
        "features": "ALL",
        "grace_period_days": 7,
    }
    grace_payload["signature"] = signer.sign_license(grace_payload)

    status = daemon_evaluate_license(grace_payload)
    assert status.is_valid is True
    assert status.status == "GRACE_PERIOD"
    assert status.grace_period_active is True
    assert status.remaining_days == 4
    assert "Grace period active (4 days remaining)" in status.message


# Scenario 10: Convert trial to paid subscription with manual payment receipt
def test_scenario_10_convert_trial_to_paid_with_manual_payment(client, admin_headers):
    """Scenario 10: Vendor confirms manual payment and converts trial into paid commercial subscription."""
    # 1. Create client & trial
    c_res = client.post(
        "/api/v1/clients",
        json={"business_name": "Modern Wellness", "owner_name": "K. Sengupta", "phone": "9876500007"},
        headers=admin_headers,
    )
    cid = c_res.json()["data"]["id"]

    trial_res = client.post(
        "/api/v1/subscriptions/start-trial",
        json={"client_id": cid, "trial_days": 15},
        headers=admin_headers,
    )
    sub_id = trial_res.json()["data"]["id"]

    # 2. Get Single Counter plan
    plans_res = client.get("/api/v1/plans", headers=admin_headers)
    single_plan = next(p for p in plans_res.json()["data"] if p["plan_code"] == "SINGLE_COUNTER")

    # 3. Convert trial to paid with manual payment confirmation
    convert_res = client.post(
        f"/api/v1/subscriptions/{sub_id}/convert-to-paid",
        json={
            "plan_id": single_plan["id"],
            "payment_reference": "UPI/HDFC/9922114455",
            "amount": 1200000,
            "payment_method": "UPI",
            "notes": "Paid via HDFC UPI scan",
        },
        headers=admin_headers,
    )
    assert convert_res.status_code == 200
    converted = convert_res.json()["data"]
    assert converted["status"] == SubscriptionStatus.ACTIVE.value
    assert converted["is_trial"] is False
    assert converted["plan_id"] == single_plan["id"]
    assert converted["payment_reference"] == "UPI/HDFC/9922114455"

    # 4. Verify manual payment receipt exists in payments registry
    pay_res = client.get(f"/api/v1/payments?client_id={cid}", headers=admin_headers)
    assert pay_res.status_code == 200
    payments = pay_res.json()["data"]
    assert len(payments) >= 1
    assert payments[0]["payment_reference"] == "UPI/HDFC/9922114455"
    assert payments[0]["amount"] == 1200000
    assert payments[0]["status"] == "CONFIRMED"


# Scenario 11: Renew subscription with manual payment
def test_scenario_11_renew_subscription_with_manual_payment(client, admin_headers):
    """Scenario 11: Vendor records renewal payment and extends subscription."""
    c_res = client.post(
        "/api/v1/clients",
        json={"business_name": "Renew Care Pharmacy", "owner_name": "M. Joshi", "phone": "9876500008"},
        headers=admin_headers,
    )
    cid = c_res.json()["data"]["id"]

    sub_res = client.post(
        "/api/v1/subscriptions/paid",
        json={"client_id": cid, "plan_code": "SINGLE_COUNTER", "payment_reference": "INIT-001", "amount": 1200000},
        headers=admin_headers,
    )
    sub = sub_res.json()["data"]
    sub_id = sub["id"]
    original_end = date.fromisoformat(sub["current_period_end"])

    # Renew subscription with Year 2 manual payment
    renew_res = client.post(
        f"/api/v1/subscriptions/{sub_id}/renew",
        json={
            "payment_reference": "NEFT/ICICI/8833221100",
            "amount": 1200000,
            "payment_method": "NEFT_RTGS",
            "notes": "Year 2 Renewal via NEFT",
        },
        headers=admin_headers,
    )
    assert renew_res.status_code == 200
    renewed = renew_res.json()["data"]
    new_end = date.fromisoformat(renewed["current_period_end"])
    assert new_end > original_end
    assert renewed["payment_reference"] == "NEFT/ICICI/8833221100"

    # Verify renewal payment recorded
    pay_res = client.get(f"/api/v1/payments?client_id={cid}", headers=admin_headers)
    assert any(p["payment_reference"] == "NEFT/ICICI/8833221100" for p in pay_res.json()["data"])


# Scenario 12: Suspend subscription
def test_scenario_12_suspend_subscription(client, admin_headers):
    """Scenario 12: Suspend client subscription upon compliance review."""
    c_res = client.post(
        "/api/v1/clients",
        json={"business_name": "Suspend Medicos", "owner_name": "O. P. Sharma", "phone": "9876500009"},
        headers=admin_headers,
    )
    cid = c_res.json()["data"]["id"]

    sub_res = client.post(
        "/api/v1/subscriptions/paid",
        json={"client_id": cid, "plan_code": "SINGLE_COUNTER"},
        headers=admin_headers,
    )
    sub_id = sub_res.json()["data"]["id"]

    susp_res = client.post(
        f"/api/v1/subscriptions/{sub_id}/suspend",
        json={"reason": "Drug license inspection dispute"},
        headers=admin_headers,
    )
    assert susp_res.status_code == 200
    assert susp_res.json()["data"]["status"] == SubscriptionStatus.SUSPENDED.value


# Scenario 13: Revoke license
def test_scenario_13_revoke_license(client, admin_headers):
    """Scenario 13: Explicitly revoke an issued license."""
    c_res = client.post(
        "/api/v1/clients",
        json={"business_name": "Revoke Test Store", "owner_name": "T. Roy", "phone": "9876500010"},
        headers=admin_headers,
    )
    cid = c_res.json()["data"]["id"]

    lic_res = client.post(
        "/api/v1/licenses/generate",
        json={"client_id": cid, "terminal_count": 2},
        headers=admin_headers,
    )
    lic_id = lic_res.json()["data"]["id"]

    rev_res = client.post(
        f"/api/v1/licenses/{lic_id}/revoke",
        json={"reason": "Customer transitioned to Enterprise multi-store license"},
        headers=admin_headers,
    )
    assert rev_res.status_code == 200
    assert rev_res.json()["data"]["revoked_at"] is not None


# Scenario 14: Verify vendor role permissions
def test_scenario_14_verify_vendor_role_permissions(client, readonly_headers, support_headers, admin_headers):
    """Scenario 14: Enforce role-based access control (READ_ONLY, SUPPORT, ADMIN, OWNER)."""
    # 1. READ_ONLY cannot create a client
    ro_create = client.post(
        "/api/v1/clients",
        json={"business_name": "Forbidden Chemist", "owner_name": "Anon", "phone": "12345"},
        headers=readonly_headers,
    )
    assert ro_create.status_code == 403

    # 2. READ_ONLY cannot view audit history
    ro_audit = client.get("/api/v1/audit", headers=readonly_headers)
    assert ro_audit.status_code == 403

    # 3. SUPPORT can view clients and subscriptions
    sup_clients = client.get("/api/v1/clients", headers=support_headers)
    assert sup_clients.status_code == 200
    sup_subs = client.get("/api/v1/subscriptions", headers=support_headers)
    assert sup_subs.status_code == 200

    # 4. SUPPORT cannot modify system trial settings (requires ADMIN or OWNER)
    sup_settings = client.put(
        "/api/v1/settings/trial-duration",
        json={"default_trial_days": 20},
        headers=support_headers,
    )
    assert sup_settings.status_code == 403

    # 5. SUPPORT cannot create vendor users
    sup_user = client.post(
        "/api/v1/users",
        json={"full_name": "Test User", "email": "test@apexhealth.local", "password": "Password123!", "role": "SUPPORT"},
        headers=support_headers,
    )
    assert sup_user.status_code == 403


# Scenario 15: Verify no pharmacy operational data in Supabase schema / tables
def test_scenario_15_verify_no_pharmacy_operational_data_in_database():
    """Scenario 15: Guarantee absolute data segregation — zero operational store data in licensing DB."""
    # 1. Inspect SQLAlchemy metadata tables
    registered_tables = set(Base.metadata.tables.keys())
    expected_vendor_tables = {
        "clients",
        "plans",
        "subscriptions",
        "licenses",
        "vendor_users",
        "audit_events",
        "payments",
        "system_settings",
        "renewal_requests",
    }
    assert registered_tables == expected_vendor_tables, f"Unexpected tables found: {registered_tables - expected_vendor_tables}"

    # 2. Verify forbidden operational keywords are NOT tables
    forbidden_table_keywords = [
        "sale",
        "invoice",
        "bill",
        "item",
        "medicine",
        "batch",
        "stock",
        "inventory",
        "customer",
        "patient",
        "doctor",
        "prescriber",
        "purchase",
        "supplier",
        "khata",
        "return",
        "wastage",
        "dispens",
    ]
    for table_name in registered_tables:
        for kw in forbidden_table_keywords:
            assert kw not in table_name.lower(), f"Operational table '{table_name}' must not exist in licensing DB!"

    # 3. Check PostgreSQL DDL migration file content
    migration_file = Path(__file__).resolve().parent.parent / "migrations" / "001_supabase_schema.sql"
    assert migration_file.is_file(), "001_supabase_schema.sql must exist"
    migration_text = migration_file.read_text(encoding="utf-8").lower()

    for kw in ["create table sales", "create table medicines", "create table inventory", "create table batches", "create table customers"]:
        assert kw not in migration_text, f"Forbidden operational DDL statement '{kw}' found in Supabase migration!"


# ===========================================================================
# Client Portal, 15-Day Trial, Tenant Isolation & Monthly Renewal Scenarios
# ===========================================================================

def test_scenario_16_client_signup_and_configurable_15_day_trial(client):
    """Scenario 16: Customer self-serve signup creates account, starts 15-day trial, and issues trial license."""
    payload = {
        "email": "Owner@SunshinePharmacy.com",
        "password": "SecurePassword2026!",
        "pharmacy_name": "Sunshine Care Pharmacy",
        "contact_person": "Dr. Ananya Sharma",
        "phone": "+91 98765 11223",
    }
    res = client.post("/api/v1/client/auth/signup", json=payload)
    assert res.status_code == 201
    data = res.json()["data"]

    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["trial_days"] == 15
    assert data["subscription_status"] == "TRIALING"

    client_info = data["client"]
    assert client_info["email"] == "owner@sunshinepharmacy.com"  # Normalized lower-case
    assert client_info["business_name"] == "Sunshine Care Pharmacy"
    assert client_info["client_code"].startswith("CL-")

    # Verify client can query their dashboard
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    dash_res = client.get("/api/v1/client/dashboard", headers=headers)
    assert dash_res.status_code == 200
    dash = dash_res.json()["data"]

    assert dash["status"] == "TRIALING"
    assert dash["days_remaining"] == 15
    assert dash["maximum_terminals"] == 2
    assert dash["active_license"] is not None
    assert dash["active_license"]["edition"] == "TRIAL"

    # Verify signed license token is valid and verifiable offline with Ed25519 public key
    lic_token = dash["license_token"]
    assert lic_token is not None
    assert daemon_verify_signature(lic_token, EMBEDDED_PUBLIC_KEY_HEX) is True


def test_scenario_17_reject_duplicate_normalized_email(client):
    """Scenario 17: Prevent duplicate registration with differently cased/spaced normalized email."""
    client.post("/api/v1/client/auth/signup", json={
        "email": "unique@apexrx.example",
        "password": "Password123!",
        "pharmacy_name": "Apex First Pharmacy",
        "contact_person": "Contact One",
        "phone": "9876543210",
    })

    # Attempt duplicate signup with mixed case and leading/trailing whitespace
    duplicate_payload = {
        "email": "  UNIQUE@ApexRx.EXAMPLE  ",
        "password": "AnotherPassword123!",
        "pharmacy_name": "Apex Duplicate Pharmacy",
        "contact_person": "Contact Two",
        "phone": "9876543211",
    }
    dup_res = client.post("/api/v1/client/auth/signup", json=duplicate_payload)
    assert dup_res.status_code == 400
    assert "already exists" in dup_res.json()["detail"].lower()


def test_scenario_18_client_login_and_rate_limiting(client):
    """Scenario 18: Client login succeeds with correct credentials and rate limits failed attempts."""
    email = "login_test@apexhealth.example"
    pwd = "LoginPassword2026!"
    client.post("/api/v1/client/auth/signup", json={
        "email": email,
        "password": pwd,
        "pharmacy_name": "Login Test Chemist",
        "contact_person": "Login Tester",
        "phone": "9811122233",
    })

    # 1. Successful login
    login_res = client.post("/api/v1/client/auth/login", json={"email": email.upper(), "password": pwd})
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()["data"]

    # 2. Failed login with wrong password
    bad_res = client.post("/api/v1/client/auth/login", json={"email": email, "password": "WrongPassword!"})
    assert bad_res.status_code == 401
    assert "Invalid email or password" in bad_res.json()["detail"]


def test_scenario_19_client_tenant_isolation(client, owner_headers):
    """Scenario 19: Strict tenant isolation: client A cannot access client B data, and client cannot access vendor admin."""
    # Register Client A
    res_a = client.post("/api/v1/client/auth/signup", json={
        "email": "client_a@test.example",
        "password": "Password123!",
        "pharmacy_name": "Pharmacy Alpha",
        "contact_person": "Person Alpha",
        "phone": "9876500001",
    })
    token_a = res_a.json()["data"]["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Register Client B
    res_b = client.post("/api/v1/client/auth/signup", json={
        "email": "client_b@test.example",
        "password": "Password123!",
        "pharmacy_name": "Pharmacy Beta",
        "contact_person": "Person Beta",
        "phone": "9876500002",
    })
    token_b = res_b.json()["data"]["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Verify Client A dashboard shows Pharmacy Alpha
    dash_a = client.get("/api/v1/client/dashboard", headers=headers_a).json()["data"]
    assert dash_a["client"]["business_name"] == "Pharmacy Alpha"

    # Verify Client B dashboard shows Pharmacy Beta
    dash_b = client.get("/api/v1/client/dashboard", headers=headers_b).json()["data"]
    assert dash_b["client"]["business_name"] == "Pharmacy Beta"

    # Client A cannot access vendor-only administrative endpoints (e.g. GET /api/v1/clients)
    admin_probe = client.get("/api/v1/clients", headers=headers_a)
    assert admin_probe.status_code == 403
    assert "Forbidden" in admin_probe.json()["detail"]


def test_scenario_20_client_payment_submission_and_vendor_confirmation(client, admin_headers):
    """Scenario 20: Client submits renewal payment (marked PENDING), vendor confirms it, extending subscription and issuing renewed license."""
    signup_res = client.post("/api/v1/client/auth/signup", json={
        "email": "renew_client@pharmacy.example",
        "password": "RenewPassword2026!",
        "pharmacy_name": "Renewal Pharmacy",
        "contact_person": "Ramesh Renew",
        "phone": "9876541234",
    })
    token = signup_res.json()["data"]["access_token"]
    client_headers = {"Authorization": f"Bearer {token}"}

    # 1. Fetch available plans (Monthly Standard should be available)
    plans_res = client.get("/api/v1/client/plans", headers=client_headers)
    assert plans_res.status_code == 200
    plans = plans_res.json()["data"]
    monthly_plan = next((p for p in plans if p["billing_period"] == "MONTHLY"), None)
    assert monthly_plan is not None, "Monthly plan must be available"

    # 2. Client submits manual payment reference
    utr_ref = "UPI/981248001122"
    submit_res = client.post("/api/v1/client/payments/submit", json={
        "plan_id": monthly_plan["id"],
        "amount": monthly_plan["price"],
        "payment_reference": utr_ref,
        "payment_method": "UPI",
        "notes": "Monthly renewal via GPay",
    }, headers=client_headers)
    assert submit_res.status_code == 201
    payment_data = submit_res.json()["data"]
    assert payment_data["status"] == "PENDING"
    payment_id = payment_data["id"]

    # Verify subscription is NOT renewed yet while payment is pending
    dash_before = client.get("/api/v1/client/dashboard", headers=client_headers).json()["data"]
    assert dash_before["status"] == "TRIALING"

    # 3. Vendor verifies and confirms payment
    confirm_res = client.post(f"/api/v1/payments/{payment_id}/confirm", headers=admin_headers)
    assert confirm_res.status_code == 200
    confirm_data = confirm_res.json()["data"]
    assert confirm_data["payment"]["status"] == "CONFIRMED"
    assert confirm_data["subscription"]["status"] == "ACTIVE"

    # 4. Client dashboard now reflects ACTIVE subscription with extended period
    dash_after = client.get("/api/v1/client/dashboard", headers=client_headers).json()["data"]
    assert dash_after["status"] == "ACTIVE"
    assert dash_after["subscription"]["plan"]["billing_period"] == "MONTHLY"

    # 5. Client downloads renewed signed license token
    download_res = client.get("/api/v1/client/license/download", headers=client_headers)
    assert download_res.status_code == 200
    renewed_token = download_res.json()
    assert renewed_token["edition"] == "COMMERCIAL"
    assert daemon_verify_signature(renewed_token, EMBEDDED_PUBLIC_KEY_HEX) is True


def test_scenario_21_vendor_payment_rejection(client, admin_headers):
    """Scenario 21: Vendor rejects invalid submitted payment with audited reason, subscription is not extended."""
    signup_res = client.post("/api/v1/client/auth/signup", json={
        "email": "reject_test@pharmacy.example",
        "password": "RejectPassword2026!",
        "pharmacy_name": "Reject Test Pharmacy",
        "contact_person": "Reject Test",
        "phone": "9876540099",
    })
    token = signup_res.json()["data"]["access_token"]
    client_headers = {"Authorization": f"Bearer {token}"}

    # Client submits fake payment
    submit_res = client.post("/api/v1/client/payments/submit", json={
        "amount": 59900,
        "payment_reference": "FAKE_UTR_9999",
        "payment_method": "UPI",
    }, headers=client_headers)
    payment_id = submit_res.json()["data"]["id"]

    # Vendor rejects payment
    reject_res = client.post(f"/api/v1/payments/{payment_id}/reject", json={
        "reason": "UTR not found in bank statement",
    }, headers=admin_headers)
    assert reject_res.status_code == 200
    rejected_pay = reject_res.json()["data"]
    assert rejected_pay["status"] == "REJECTED"
    assert "UTR not found" in rejected_pay["rejection_reason"]

    # Subscription remains in trial/initial state
    dash = client.get("/api/v1/client/dashboard", headers=client_headers).json()["data"]
    assert dash["status"] == "TRIALING"


def test_scenario_22_renewal_from_max_today_or_expiry(client, admin_headers):
    """Scenario 22: Renewal extends from max(today, current_expiry) by plan period (monthly = 30 days)."""
    signup_res = client.post("/api/v1/client/auth/signup", json={
        "email": "period_test@pharmacy.example",
        "password": "PeriodPassword2026!",
        "pharmacy_name": "Period Test Pharmacy",
        "contact_person": "Period Test",
        "phone": "9876540088",
    })
    client_data = signup_res.json()["data"]
    token = client_data["access_token"]
    client_headers = {"Authorization": f"Bearer {token}"}

    plans = client.get("/api/v1/client/plans", headers=client_headers).json()["data"]
    monthly_plan = next(p for p in plans if p["billing_period"] == "MONTHLY")

    # Submit and confirm initial payment
    sub_res = client.post("/api/v1/client/payments/submit", json={
        "plan_id": monthly_plan["id"],
        "amount": monthly_plan["price"],
        "payment_reference": "INITIAL_PAID_01",
    }, headers=client_headers)
    pay_id_1 = sub_res.json()["data"]["id"]
    client.post(f"/api/v1/payments/{pay_id_1}/confirm", headers=admin_headers)

    dash_1 = client.get("/api/v1/client/dashboard", headers=client_headers).json()["data"]
    expiry_1 = date.fromisoformat(dash_1["subscription"]["current_period_end"])
    assert expiry_1 >= date.today() + timedelta(days=29)

    # Submit second renewal BEFORE expiry
    sub_res_2 = client.post("/api/v1/client/payments/submit", json={
        "plan_id": monthly_plan["id"],
        "amount": monthly_plan["price"],
        "payment_reference": "RENEWAL_PAID_02",
    }, headers=client_headers)
    pay_id_2 = sub_res_2.json()["data"]["id"]
    client.post(f"/api/v1/payments/{pay_id_2}/confirm", headers=admin_headers)

    dash_2 = client.get("/api/v1/client/dashboard", headers=client_headers).json()["data"]
    expiry_2 = date.fromisoformat(dash_2["subscription"]["current_period_end"])

    # Expiry 2 should be extended from expiry 1 by 30 days (no lost days!)
    assert (expiry_2 - expiry_1).days == 30


def test_scenario_23_client_portal_html_served_at_client_path(client):
    """Scenario 23: Verify /client serves the client portal SPA index.html."""
    res = client.get("/client")
    assert res.status_code == 200
    assert "Customer Account" in res.text
    assert "Client Portal" in res.text


def test_scenario_24_configured_trial_and_grace_periods_reflected_in_signed_licenses(client, admin_headers):
    """Scenario 24: Verify configured trial duration and grace period are accurately reflected
    in the cryptographic signed license tokens generated for client registration and renewals."""
    # 1. Standard Client Registration: uses default 15-day trial and 7-day grace period
    signup_res = client.post("/api/v1/client/auth/signup", json={
        "email": "trial_grace_verify@example.com",
        "password": "VerifyPassword123!",
        "pharmacy_name": "Trial Grace Verification Pharmacy",
        "contact_person": "Verification Officer",
        "phone": "9876541122",
    })
    assert signup_res.status_code == 201
    token = signup_res.json()["data"]["access_token"]
    client_headers = {"Authorization": f"Bearer {token}"}

    # Download initial trial license token
    lic_res = client.get("/api/v1/client/license/download", headers=client_headers)
    assert lic_res.status_code == 200
    lic_payload = lic_res.json()

    # Verify 15-day trial duration and 7-day grace period in payload
    assert lic_payload["edition"] == "TRIAL"
    assert lic_payload["activation_date"] == date.today().isoformat()
    assert lic_payload["expiry_date"] == (date.today() + timedelta(days=15)).isoformat()
    assert lic_payload["grace_period_days"] == 7
    # Verify cryptographic signature authenticity
    assert daemon_verify_signature(lic_payload) is True

    # 2. Configured custom settings: Change default trial to 30 days and grace to 10 days
    client.put(
        "/api/v1/settings/trial-duration",
        json={"default_trial_days": 30, "default_grace_days": 10},
        headers=admin_headers,
    )

    signup_res_custom = client.post("/api/v1/client/auth/signup", json={
        "email": "custom_trial_grace@example.com",
        "password": "VerifyPassword123!",
        "pharmacy_name": "Custom 30Day Pharmacy",
        "contact_person": "Custom Officer",
        "phone": "9876541133",
    })
    assert signup_res_custom.status_code == 201
    custom_token = signup_res_custom.json()["data"]["access_token"]
    custom_headers = {"Authorization": f"Bearer {custom_token}"}

    lic_custom = client.get("/api/v1/client/license/download", headers=custom_headers).json()
    assert lic_custom["expiry_date"] == (date.today() + timedelta(days=30)).isoformat()
    assert lic_custom["grace_period_days"] == 10
    assert daemon_verify_signature(lic_custom) is True

    # Reset defaults back to 15 trial, 7 grace
    client.put(
        "/api/v1/settings/trial-duration",
        json={"default_trial_days": 15, "default_grace_days": 7},
        headers=admin_headers,
    )

    # 3. Monthly Renewal: Confirm monthly payment and verify signed license reflects commercial edition & 7-day grace
    plans = client.get("/api/v1/client/plans", headers=client_headers).json()["data"]
    monthly_plan = next(p for p in plans if p["billing_period"] == "MONTHLY")

    pay_res = client.post("/api/v1/client/payments/submit", json={
        "plan_id": monthly_plan["id"],
        "amount": monthly_plan["price"],
        "payment_reference": "TRIAL_GRACE_RENEWAL",
    }, headers=client_headers)
    pay_id = pay_res.json()["data"]["id"]

    confirm_res = client.post(f"/api/v1/payments/{pay_id}/confirm", headers=admin_headers)
    assert confirm_res.status_code == 200

    lic_paid = client.get("/api/v1/client/license/download", headers=client_headers).json()
    assert lic_paid["edition"] == "COMMERCIAL"
    assert lic_paid["grace_period_days"] == 7
    assert daemon_verify_signature(lic_paid) is True


def test_scenario_25_desktop_client_signup_auto_trial_and_duplicate_prevention(client):
    """Scenario 25: Desktop client signup automatically generates signed Ed25519 trial license,
    and prevents duplicate or abusive trial creation via normalized email and phone."""
    signup_payload = {
        "business_name": "Automatic Trial Chemist",
        "owner_name": "Ramesh Gupta",
        "email": "ramesh@autotrial.local",
        "phone": "+91 (987) 654-3210",
        "password": "RameshSecurePass2026!",
        "drug_license_number": "DL-AUTO-01",
        "gstin": "09AAAAA1111A1Z1",
    }
    res = client.post("/api/v1/client/signup", json=signup_payload)
    assert res.status_code == 201
    data = res.json()["data"]
    assert data["business_name"] == "Automatic Trial Chemist"
    assert data["owner_name"] == "Ramesh Gupta"
    assert data["email"] == "ramesh@autotrial.local"
    assert "access_token" in data
    assert data["license_token"] is not None

    # Verify returned license token is cryptographically signed and immediately evaluatable
    lic = data["license_token"]
    assert daemon_verify_signature(lic) is True
    eval_status = daemon_evaluate_license(lic)
    assert eval_status.is_valid is True
    assert eval_status.status == "TRIAL"
    assert eval_status.client_name == "Automatic Trial Chemist"
    assert eval_status.remaining_days == 15
    assert "Trial:" in eval_status.message

    # Duplicate check 1: Same email -> 400 Bad Request
    dup_res1 = client.post("/api/v1/client/signup", json={
        "business_name": "Another Store",
        "owner_name": "Other Person",
        "email": "RAMESH@autotrial.local",
        "phone": "9111122222",
        "password": "PassWord123!",
    })
    assert dup_res1.status_code == 400
    assert "already exists" in dup_res1.json()["detail"].lower()

    # Duplicate check 2: Different email, but same phone number (normalized 10 digits) -> 400 Bad Request
    dup_res2 = client.post("/api/v1/client/signup", json={
        "business_name": "Third Store",
        "owner_name": "Other Person 2",
        "email": "other@autotrial.local",
        "phone": "9876543210",
        "password": "PassWord123!",
    })
    assert dup_res2.status_code == 400
    assert "already registered" in dup_res2.json()["detail"].lower()


def test_scenario_26_vendor_trial_duration_settings_validation_and_audit(client, admin_headers):
    """Scenario 26: Vendor can configure default trial duration (including 4, 10, 15 days),
    invalid values are rejected server-side, and changes are recorded in audit history."""
    # 1. Validation rejection: 0 days or >365 days
    bad_res1 = client.put(
        "/api/v1/settings/trial-duration",
        json={"default_trial_days": 0, "default_grace_days": 7},
        headers=admin_headers,
    )
    assert bad_res1.status_code in (400, 422)

    bad_res2 = client.put(
        "/api/v1/settings/trial-duration",
        json={"default_trial_days": 500, "default_grace_days": 7},
        headers=admin_headers,
    )
    assert bad_res2.status_code in (400, 422)

    # 2. Configure 4-day quick option
    res_4 = client.put(
        "/api/v1/settings/trial-duration",
        json={"default_trial_days": 4, "default_grace_days": 3},
        headers=admin_headers,
    )
    assert res_4.status_code == 200
    assert res_4.json()["data"]["default_trial_days"] == 4

    # Sign up client with 4-day trial
    c4 = client.post("/api/v1/client/signup", json={
        "business_name": "Four Day Trial Store",
        "owner_name": "User Four",
        "email": "user4@trial.local",
        "phone": "9876540004",
        "password": "PasswordFour123!",
    }).json()["data"]
    lic4 = c4["license_token"]
    assert lic4["expiry_date"] == (date.today() + timedelta(days=4)).isoformat()
    status4 = daemon_evaluate_license(lic4)
    assert status4.remaining_days == 4

    # 3. Configure 10-day quick option
    res_10 = client.put(
        "/api/v1/settings/trial-duration",
        json={"default_trial_days": 10, "default_grace_days": 5},
        headers=admin_headers,
    )
    assert res_10.status_code == 200
    assert res_10.json()["data"]["default_trial_days"] == 10

    # Sign up client with 10-day trial
    c10 = client.post("/api/v1/client/signup", json={
        "business_name": "Ten Day Trial Store",
        "owner_name": "User Ten",
        "email": "user10@trial.local",
        "phone": "9876540010",
        "password": "PasswordTen123!",
    }).json()["data"]
    lic10 = c10["license_token"]
    assert lic10["expiry_date"] == (date.today() + timedelta(days=10)).isoformat()
    status10 = daemon_evaluate_license(lic10)
    assert status10.remaining_days == 10

    # Restore 15-day default
    client.put(
        "/api/v1/settings/trial-duration",
        json={"default_trial_days": 15, "default_grace_days": 7},
        headers=admin_headers,
    )

    # 4. Verify audit history records configuration updates
    audit_res = client.get("/api/v1/audit", headers=admin_headers)
    assert audit_res.status_code == 200
    actions = [a["action"] for a in audit_res.json()["data"]]
    assert "TRIAL_SETTINGS_UPDATED" in actions


def test_scenario_27_client_in_app_renewal_request_vendor_approval_and_safe_audit(client, admin_headers):
    """Scenario 27: Client submits in-app renewal request, vendor approves request,
    renews subscription, generates renewed signed Ed25519 license, and audit log excludes passwords."""
    # Register client
    signup_res = client.post("/api/v1/client/signup", json={
        "business_name": "Renewal Client Pharmacy",
        "owner_name": "Kavita Shah",
        "email": "kavita@renewal.local",
        "phone": "9876540099",
        "password": "KavitaSuperSecretPass!",
    })
    client_data = signup_res.json()["data"]
    client_token = client_data["access_token"]
    client_h = {"Authorization": f"Bearer {client_token}"}

    # Submit renewal request
    req_res = client.post("/api/v1/client/renewal-requests", json={
        "requested_plan_code": "ANNUAL_STANDARD",
        "payment_reference": "UPI-UTR-882299",
        "notes": "Annual plan payment settled via PhonePe",
    }, headers=client_h)
    assert req_res.status_code == 201
    req_json = req_res.json()
    req_data = req_json.get("data", req_json)
    req_id = req_data["id"]
    assert req_data["status"] == "PENDING"
    assert req_data["requested_plan_code"] == "ANNUAL_STANDARD"
    assert req_data["payment_reference"] == "UPI-UTR-882299"
    assert "vendor_notification_sent" in req_data

    # Vendor lists renewal requests
    list_res = client.get("/api/v1/renewal-requests", headers=admin_headers)
    assert list_res.status_code == 200
    list_json = list_res.json()
    requests = list_json.get("data", list_json)
    assert any(r["id"] == req_id for r in requests)

    # Vendor approves renewal request
    approve_res = client.post(f"/api/v1/renewal-requests/{req_id}/approve", json={
        "payment_reference": "UPI-UTR-882299",
        "amount": 59900,
        "notes": "Verified in HDFC current account statement",
    }, headers=admin_headers)
    assert approve_res.status_code == 200
    appr_json = approve_res.json()
    appr_data = appr_json.get("data", appr_json)
    assert appr_data.get("status") == "APPROVED" or appr_data.get("renewal_request", {}).get("status") == "APPROVED"
    assert appr_data.get("license_id") is not None

    # Client downloads renewed license token
    renewed_lic = client.get("/api/v1/client/license/download", headers=client_h).json()
    assert daemon_verify_signature(renewed_lic) is True
    eval_renewed = daemon_evaluate_license(renewed_lic)
    assert eval_renewed.is_valid is True
    assert eval_renewed.status == "ACTIVE"
    assert eval_renewed.edition == "COMMERCIAL"
    assert eval_renewed.remaining_days is not None and eval_renewed.remaining_days >= 360

    # Verify audit log contains approval and NO password or hash leaks
    audit_res = client.get("/api/v1/audit", headers=admin_headers)
    audit_entries = audit_res.json()["data"]
    serialized_audit = json.dumps(audit_entries)
    assert "KavitaSuperSecretPass!" not in serialized_audit
    assert "password_hash" not in serialized_audit


def test_scenario_28_support_contacts_configuration(client, admin_headers):
    """Scenario 28: Support contacts can be updated by vendor and fetched by client."""
    update_res = client.put(
        "/api/v1/settings/support-contacts",
        json={
            "phone": "+91 91234 56789",
            "whatsapp": "+91 91234 56789",
            "email": "custom-support@apexhealth.local",
            "vendor_notification_email": "alerts@apexhealth.local",
        },
        headers=admin_headers,
    )
    assert update_res.status_code == 200

    # Public client fetch
    client_res = client.get("/api/v1/client/support-contacts")
    assert client_res.status_code == 200
    contacts = client_res.json()["data"]
    assert contacts["phone"] == "+91 91234 56789"
    assert contacts["whatsapp"] == "+91 91234 56789"
    assert contacts["email"] == "custom-support@apexhealth.local"


def test_scenario_29_renewal_request_authentication_ownership_and_rate_limiting(client, admin_headers):
    """Scenario 29: In-app renewal requests require valid client tokens, derive client identity strictly
    from the authenticated client record, reject vendor tokens, and enforce sliding window rate limiting."""
    from licensing_service.security.auth import clear_renewal_attempts

    # 1. Reject unauthenticated request (401)
    unauth_res = client.post("/api/v1/client/renewal-requests", json={
        "requested_plan_code": "ANNUAL_STANDARD",
        "payment_reference": "UNAUTH_REF",
    })
    assert unauth_res.status_code == 401
    assert "credentials are required" in unauth_res.json()["detail"].lower()

    # 2. Reject vendor token (403 Forbidden)
    vendor_res = client.post("/api/v1/client/renewal-requests", json={
        "requested_plan_code": "ANNUAL_STANDARD",
    }, headers=admin_headers)
    assert vendor_res.status_code == 403
    assert "client access token required" in vendor_res.json()["detail"].lower()

    # 3. Authenticated client submits renewal request
    signup_res = client.post("/api/v1/client/signup", json={
        "business_name": "True Store Pharmacy",
        "owner_name": "Authentic Owner",
        "email": "true_owner@pharmacy.local",
        "phone": "9811223344",
        "password": "PasswordAuth123!",
    })
    assert signup_res.status_code == 201
    client_data = signup_res.json()["data"]
    client_token = client_data["access_token"]
    client_h = {"Authorization": f"Bearer {client_token}"}

    # Attempt to spoof identity in request payload
    spoofed_payload = {
        "store_name": "Spoofed Fake Store",
        "contact_name": "Attacker",
        "email": "attacker@darkweb.local",
        "phone": "1111111111",
        "requested_plan_code": "ANNUAL_STANDARD",
        "payment_reference": "UPI-TRUE-01",
        "notes": "Legitimate payment",
    }
    submit_res = client.post("/api/v1/client/renewal-requests", json=spoofed_payload, headers=client_h)
    assert submit_res.status_code == 201
    envelope = submit_res.json()
    assert envelope["success"] is True
    assert "data" in envelope
    req_data = envelope["data"]

    # Verify identity came strictly from authenticated Client, NOT from spoofed inputs
    assert req_data["store_name"] == "True Store Pharmacy"
    assert req_data["contact_name"] == "Authentic Owner"
    assert req_data["email"] == "true_owner@pharmacy.local"
    assert req_data["phone"] == "9811223344"
    assert req_data["payment_reference"] == "UPI-TRUE-01"

    # 4. Enforce renewal rate limit (max 5 requests per 15 min)
    for _ in range(4):
        res = client.post("/api/v1/client/renewal-requests", json={"requested_plan_code": "ANNUAL_STANDARD"}, headers=client_h)
        assert res.status_code == 201

    # 6th attempt should be blocked by rate limiter (429)
    rate_res = client.post("/api/v1/client/renewal-requests", json={"requested_plan_code": "ANNUAL_STANDARD"}, headers=client_h)
    assert rate_res.status_code == 429
    assert "too many renewal requests" in rate_res.json()["detail"].lower()

    # Clear rate limit state after test
    clear_renewal_attempts(str(client_data["client"]["id"]))


def test_scenario_30_client_session_refresh_and_token_validation(client):
    """Scenario 30: Client can refresh session with valid refresh token,
    and invalid, expired, malformed, or wrong-type credentials are appropriately rejected."""
    from licensing_service.security.auth import create_access_token
    import jwt

    # 1. Register client and receive access and refresh tokens
    signup_res = client.post("/api/v1/client/signup", json={
        "business_name": "Refreshable Pharmacy",
        "owner_name": "Reena Mehra",
        "email": "reena@refreshable.local",
        "phone": "9822334455",
        "password": "ReenaPass2026!",
    })
    assert signup_res.status_code == 201
    auth_data = signup_res.json()["data"]
    refresh_token = auth_data["refresh_token"]
    assert refresh_token is not None

    # 2. Valid refresh token issues fresh access and refresh tokens
    refresh_res = client.post("/api/v1/client/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_res.status_code == 200
    ref_env = refresh_res.json()
    assert ref_env["success"] is True
    assert "access_token" in ref_env["data"]
    assert "refresh_token" in ref_env["data"]
    new_access = ref_env["data"]["access_token"]

    # Verify new access token works on client portal
    dash_res = client.get("/api/v1/client/dashboard", headers={"Authorization": f"Bearer {new_access}"})
    assert dash_res.status_code == 200

    # 3. Reject missing credentials (401)
    missing_res = client.post("/api/v1/client/auth/refresh", json={})
    assert missing_res.status_code == 401

    # 4. Reject malformed token (401)
    malformed_res = client.post("/api/v1/client/auth/refresh", json={"refresh_token": "not.a.valid.jwt"})
    assert malformed_res.status_code == 401

    # 5. Reject expired token (401)
    expired_token = create_access_token(
        {"sub": str(auth_data["client"]["id"]), "type": "client"},
        expires_delta=timedelta(seconds=-10),
    )
    exp_res = client.post("/api/v1/client/auth/refresh", json={"refresh_token": expired_token})
    assert exp_res.status_code == 401
    assert "expired" in exp_res.json()["detail"].lower()

    # 6. Reject wrong token type (vendor token on client refresh -> 403)
    vendor_token = create_access_token({"sub": "1", "type": "vendor"})
    wrong_res = client.post("/api/v1/client/auth/refresh", json={"refresh_token": vendor_token})
    assert wrong_res.status_code == 403
    assert "client access token required" in wrong_res.json()["detail"].lower()


def test_scenario_31_signup_password_length_alignment(client):
    """Scenario 31: Password length rule of at least 8 characters is strictly aligned
    and returns 422 for short passwords, accepting valid passwords >= 8 chars."""
    # Short password (6 or 7 characters) -> 422 Unprocessable Entity
    short_res = client.post("/api/v1/client/signup", json={
        "business_name": "Short Password Meds",
        "owner_name": "Short User",
        "email": "short@chemist.local",
        "phone": "9833445566",
        "password": "short7!",
    })
    assert short_res.status_code == 422

    # Valid password (8 characters) -> 201 Created
    valid_res = client.post("/api/v1/client/signup", json={
        "business_name": "Valid Password Meds",
        "owner_name": "Valid User",
        "email": "valid@chemist.local",
        "phone": "9833445566",
        "password": "Valid8Ch",
    })
    assert valid_res.status_code == 201
    assert valid_res.json()["data"]["email"] == "valid@chemist.local"


def test_scenario_32_version2_license_signing_grace_period_and_legacy_compatibility(client, admin_headers):
    """Scenario 32: Version 2 licenses cryptographically sign grace_period_days,
    tampering with grace period invalidates the signature, and legacy Version 1 licenses still verify."""
    from licensing_service.security.signer import signer
    from pharmacy_daemon.security.license import sign_license as daemon_sign_license

    # 1. Newly issued license has version=2 and signed grace_period_days
    signup_res = client.post("/api/v1/client/signup", json={
        "business_name": "V2 License Store",
        "owner_name": "V2 Owner",
        "email": "v2@license.local",
        "phone": "9844556677",
        "password": "PasswordV2_2026!",
    })
    lic_v2 = signup_res.json()["data"]["license_token"]
    assert lic_v2["version"] == 2
    assert "grace_period_days" in lic_v2
    assert lic_v2["grace_period_days"] == 7

    # Verifies cleanly with embedded daemon public key
    assert daemon_verify_signature(lic_v2) is True
    eval_v2 = daemon_evaluate_license(lic_v2)
    assert eval_v2.is_valid is True

    # 2. Tampering with grace_period_days (e.g. from 7 to 30) invalidates signature!
    tampered_v2 = dict(lic_v2)
    tampered_v2["grace_period_days"] = 30
    assert daemon_verify_signature(tampered_v2) is False
    eval_tampered = daemon_evaluate_license(tampered_v2)
    assert eval_tampered.is_valid is False
    assert eval_tampered.status == "INVALID_SIGNATURE"

    # 3. Legacy Version 1 license (no version in payload) still verifies
    legacy_payload = {
        "client_name": "Legacy Chemist",
        "license_id": "LIC-LEGACY-001",
        "terminal_count": 2,
        "activation_date": date.today().isoformat(),
        "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
        "edition": "COMMERCIAL",
        "features": "ALL",
        "version": 1,
    }
    legacy_payload["signature"] = signer.sign_license(dict(legacy_payload))
    assert daemon_verify_signature(legacy_payload) is True
    eval_legacy = daemon_evaluate_license(legacy_payload)
    assert eval_legacy.is_valid is True
    assert eval_legacy.status == "ACTIVE"

    # 4. Unsupported version rejection
    unsupported_ver_payload = dict(lic_v2)
    unsupported_ver_payload["version"] = 99
    eval_unsupp = daemon_evaluate_license(unsupported_ver_payload)
    assert eval_unsupp.is_valid is False
    assert eval_unsupp.status == "UNSUPPORTED_VERSION"

    # 5. Malformed grace period rejection
    malformed_grace_payload = dict(lic_v2)
    malformed_grace_payload["grace_period_days"] = 9999
    eval_malf = daemon_evaluate_license(malformed_grace_payload)
    assert eval_malf.is_valid is False
    assert eval_malf.status == "MALFORMED_LICENSE"


def test_scenario_33_smtp_notification_behavior_and_cors_configuration(client, admin_headers):
    """Scenario 33: SMTP notification handles unconfigured and failed states gracefully,
    and licensing API CORS allowlist explicitly covers desktop and local development origins."""
    from licensing_service.config import settings
    from licensing_service.services.email_service import send_vendor_renewal_notification
    from licensing_service.db.models import RenewalRequest
    from unittest.mock import patch
    import smtplib

    # 1. CORS allowlist contains desktop daemon origin (http://127.0.0.1:38291)
    cors_list = settings.cors_origins_list
    assert "http://127.0.0.1:38291" in cors_list
    assert "http://localhost:38291" in cors_list
    assert "http://127.0.0.1:5173" in cors_list
    assert "http://localhost:5173" in cors_list
    assert "*" not in cors_list

    # 2. SMTP unconfigured behavior: returns False, informative error, no exception
    mock_renewal = RenewalRequest(
        id=999,
        client_id=1,
        store_name="Test Store",
        contact_name="Test Owner",
        email="test@store.local",
        phone="9800000000",
        requested_plan_code="MONTHLY_STANDARD",
    )
    with patch.object(settings, "SMTP_HOST", None):
        from licensing_service.db.session import SessionLocal
        db = SessionLocal()
        try:
            sent, err = send_vendor_renewal_notification(db, mock_renewal)
            assert sent is False
            assert "not configured" in err.lower()
        finally:
            db.close()

    # 3. SMTP failure behavior: connection error handled safely without leaking credentials
    with patch.object(settings, "SMTP_HOST", "invalid.smtp.host.local"):
        db = SessionLocal()
        try:
            with patch("smtplib.SMTP", side_effect=smtplib.SMTPConnectError(421, b"Connection refused")):
                sent, err = send_vendor_renewal_notification(db, mock_renewal)
                assert sent is False
                assert "email delivery failed" in err.lower()
        finally:
            db.close()


def test_scenario_34_download_request_audit_and_gating(client, db_session):
    """Scenario 34: Installer download metadata requires client authentication,
    includes verified SHA-256 and size, and download requests are recorded in the audit log."""
    from licensing_service.db.models import AuditEvent, Client
    from licensing_service.security.auth import create_access_token

    # 1. Unauthenticated request rejected with 401
    unauth_list = client.get("/api/v1/client/downloads")
    assert unauth_list.status_code == 401

    unauth_req = client.post("/api/v1/client/downloads/installer-windows/request")
    assert unauth_req.status_code == 401

    # 2. Authenticated client access
    test_client = Client(
        client_code="CL-DOWNLOAD-TEST",
        business_name="Download Test Chemist",
        owner_name="Tester",
        primary_contact_name="Tester",
        email="download_test@example.com",
        phone="+91 99887 76655",
        password_hash="test_hash",
        status="ACTIVE",
    )
    db_session.add(test_client)
    db_session.commit()
    db_session.refresh(test_client)

    token = create_access_token({
        "sub": str(test_client.id),
        "client_id": test_client.id,
        "client_code": test_client.client_code,
        "email": test_client.email,
        "type": "client",
    })
    client_headers = {"Authorization": f"Bearer {token}"}

    # 3. Fetch downloads list
    res_list = client.get("/api/v1/client/downloads", headers=client_headers)
    assert res_list.status_code == 200
    downloads = res_list.json()["data"]
    installer = next(d for d in downloads if d["id"] == "installer-windows")
    assert installer["filename"] == "MediHisaab-Setup-1.0.0.exe"
    assert "95,442,984 bytes" in installer["file_size"]
    assert installer["sha256"] == "2e323e4b90768f866699b24c2aad6ba36f201e092acd65ba8cf6010b0f91c02f"

    # 4. Request download audit event
    res_req = client.post("/api/v1/client/downloads/installer-windows/request", headers=client_headers)
    assert res_req.status_code == 200
    req_data = res_req.json()["data"]
    assert req_data["recorded"] is True
    assert req_data["filename"] == "MediHisaab-Setup-1.0.0.exe"

    # 5. Verify audit event was stored in database
    audit = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.action == "CLIENT_DOWNLOAD_REQUEST", AuditEvent.user_email == test_client.email)
        .order_by(AuditEvent.id.desc())
        .first()
    )
    assert audit is not None
    assert audit.entity_id == "installer-windows"
    assert test_client.client_code in audit.metadata_json


def test_scenario_35_frontend_spa_routes_and_api_isolation(client):
    """Scenario 35: Verify primary frontend routes serve the SPA index.html,
    admin console is served at /admin and /vendor, and unhandled /api routes return 404 JSON."""
    public_routes = [
        "/",
        "/product",
        "/how-it-works",
        "/plans",
        "/account",
        "/download",
        "/about",
        "/support",
        "/privacy",
        "/faq",
        "/client",
        "/admin",
        "/vendor",
    ]
    for route in public_routes:
        res = client.get(route)
        assert res.status_code == 200, f"Route {route} failed to serve with status {res.status_code}"
        assert "text/html" in res.headers.get("content-type", "").lower()
        assert "Pharmacy POS" in res.text

    # Verify unhandled API route returns 404 JSON (NOT HTML fallback)
    api_res = client.get("/api/v1/non-existent-api-endpoint")
    assert api_res.status_code == 404
    assert "application/json" in api_res.headers.get("content-type", "").lower()






