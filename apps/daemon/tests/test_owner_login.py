"""Tests for pharmacy owner portal authentication, license synchronization, and offline fallback."""

from datetime import date, timedelta
import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import urllib.error
import pytest
from fastapi.testclient import TestClient

from pharmacy_daemon.config import DaemonConfig
from pharmacy_daemon.db.engine import DatabaseEngine
from pharmacy_daemon.security.license import sign_license, LicenseManager, evaluate_license
from pharmacy_daemon.security.hashing import hash_password


@pytest.fixture
def mock_portal_license():
    """Generate a cryptographically valid signed license payload for test assertions."""
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization

    # Publisher test private key corresponding to EMBEDDED_PUBLIC_KEY_HEX
    default_pem = (
        b"-----BEGIN PRIVATE KEY-----\n"
        b"MC4CAQAwBQYDK2VwBCIEIADr2Sp90MjKzOrWCMXg4umyFBhMEVM9C4p4SOolL91x\n"
        b"-----END PRIVATE KEY-----\n"
    )
    priv_key = serialization.load_pem_private_key(default_pem, password=None)

    payload = {
        "client_name": "Apex Super Chemist",
        "license_id": "LIC-TEST-PORTAL-001",
        "terminal_count": 2,
        "activation_date": date.today().isoformat(),
        "expiry_date": (date.today() + timedelta(days=15)).isoformat(),
        "edition": "TRIAL",
        "features": "ALL",
        "grace_period_days": 7,
        "version": 2,
    }
    payload["signature"] = sign_license(payload, priv_key)
    return payload


def test_owner_login_online_success_and_account_linking(client: TestClient, test_config: DaemonConfig, mock_portal_license):
    """Verify owner signs in via portal over HTTPS, links local admin, and saves license."""
    # 1. Initialize local system with first-run setup
    setup_payload = {
        "username": "local_admin",
        "full_name": "Local Admin User",
        "password": "InitialLocalPassword123!",
        "confirm_password": "InitialLocalPassword123!",
        "store_name": "Initial Store Name",
    }
    init_res = client.post("/api/v1/auth/first-run-setup", json=setup_payload)
    assert init_res.status_code == 201

    portal_response_data = {
        "success": True,
        "data": {
            "access_token": "mock_portal_jwt_access_token_123",
            "refresh_token": "mock_portal_jwt_refresh_token_456",
            "token_type": "bearer",
            "client": {
                "id": 101,
                "business_name": "Apex Super Chemist",
                "owner_name": "Ramesh Sharma",
                "email": "ramesh@superchemist.com",
            },
            "business_name": "Apex Super Chemist",
            "owner_name": "Ramesh Sharma",
            "email": "ramesh@superchemist.com",
            "trial_days": 15,
            "subscription_status": "TRIALING",
            "license_token": mock_portal_license,
        },
        "message": "Login successful.",
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(portal_response_data).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        login_res = client.post(
            "/api/v1/auth/owner-login",
            json={
                "email": "ramesh@superchemist.com",
                "password": "OwnerSecurePortalPass2026!",
            },
        )

    assert login_res.status_code == 200
    data = login_res.json()
    assert data["auth_source"] == "ONLINE_PORTAL"
    assert data["portal_token"] == "mock_portal_jwt_access_token_123"
    assert data["subscription_status"] == "TRIALING"
    assert data["user"]["email"] == "ramesh@superchemist.com"
    assert data["user"]["full_name"] == "Ramesh Sharma"
    assert data["user"]["role"] == "ADMIN"
    assert "access_token" in data

    # Verify license was written to disk
    lic_file = test_config.app_dir / "license.json"
    assert lic_file.exists()
    saved_lic = json.loads(lic_file.read_text("utf-8"))
    assert saved_lic["license_id"] == "LIC-TEST-PORTAL-001"

    # Verify license status evaluates to TRIAL with remaining days
    status = LicenseManager(lic_file).get_status()
    assert status.status == "TRIAL"
    assert status.is_valid is True
    assert status.remaining_days == 15


def test_owner_login_subsequent_offline_cached_login(client: TestClient, test_config: DaemonConfig, mock_portal_license):
    """Verify owner can sign in offline using cached PBKDF2/bcrypt hash when internet is disconnected."""
    # 1. First-time online setup
    setup_payload = {
        "username": "owner1",
        "full_name": "Initial Name",
        "password": "DummyPassword123!",
        "confirm_password": "DummyPassword123!",
        "store_name": "Store",
    }
    client.post("/api/v1/auth/first-run-setup", json=setup_payload)

    portal_response_data = {
        "success": True,
        "data": {
            "access_token": "token_online_1",
            "subscription_status": "ACTIVE",
            "license_token": mock_portal_license,
            "business_name": "Apex Super Chemist",
            "owner_name": "Ramesh Sharma",
            "email": "offline_owner@chemist.com",
        },
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(portal_response_data).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        online_res = client.post(
            "/api/v1/auth/owner-login",
            json={"email": "offline_owner@chemist.com", "password": "CachedPassword2026!"},
        )
    assert online_res.status_code == 200
    assert online_res.json()["auth_source"] == "ONLINE_PORTAL"

    # 2. Simulate complete internet loss (urllib raises URLError)
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused - No route to host")):
        offline_res = client.post(
            "/api/v1/auth/owner-login",
            json={"email": "offline_owner@chemist.com", "password": "CachedPassword2026!"},
        )

    assert offline_res.status_code == 200
    off_data = offline_res.json()
    assert off_data["auth_source"] == "OFFLINE_CACHED"
    assert off_data["user"]["email"] == "offline_owner@chemist.com"
    assert off_data["message"] == "Signed in using offline cached credentials."

    # 3. Simulate offline with incorrect password
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("No route to host")):
        bad_pwd_res = client.post(
            "/api/v1/auth/owner-login",
            json={"email": "offline_owner@chemist.com", "password": "WrongPassword!"},
        )
    assert bad_pwd_res.status_code == 401
    assert "Invalid email or password" in bad_pwd_res.json()["detail"]


def test_owner_login_online_rejection_no_offline_fallback(client: TestClient):
    """Verify online HTTP 401 credential rejection is not bypassed by offline fallback."""
    setup_payload = {
        "username": "owner2",
        "full_name": "Owner Two",
        "password": "Password123!",
        "confirm_password": "Password123!",
        "store_name": "Store",
    }
    client.post("/api/v1/auth/first-run-setup", json=setup_payload)

    # Server explicitly returns HTTP 401 with detail
    http_err = urllib.error.HTTPError(
        url="https://portal/login",
        code=401,
        msg="Unauthorized",
        hdrs={},
        fp=io.BytesIO(b'{"detail":"Invalid email or password."}'),
    )

    with patch("urllib.request.urlopen", side_effect=http_err):
        res = client.post(
            "/api/v1/auth/owner-login",
            json={"email": "some_user@chemist.com", "password": "WrongPassword!"},
        )

    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid email or password."


def test_owner_login_offline_unregistered_email_returns_503(client: TestClient):
    """Verify attempting offline sign-in for an email that was never cached returns 503."""
    setup_payload = {
        "username": "owner3",
        "full_name": "Owner Three",
        "password": "Password123!",
        "confirm_password": "Password123!",
        "store_name": "Store",
    }
    client.post("/api/v1/auth/first-run-setup", json=setup_payload)

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Network unreachable")):
        res = client.post(
            "/api/v1/auth/owner-login",
            json={"email": "never_logged_in@chemist.com", "password": "SomePassword123!"},
        )

    assert res.status_code == 503
    assert "no offline account was found" in res.json()["detail"]


def test_staff_login_with_username_and_email(client: TestClient, test_engine: DatabaseEngine):
    """Verify staff can log in using their username OR their email address."""
    setup_payload = {
        "username": "admin_staff",
        "full_name": "Admin Staff",
        "password": "AdminPassword123!",
        "confirm_password": "AdminPassword123!",
        "store_name": "Apex Store",
    }
    client.post("/api/v1/auth/first-run-setup", json=setup_payload)

    # Insert a staff cashier with an email
    pwd_hash = hash_password("StaffPass123!")
    conn = test_engine.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO users (username, full_name, email, password_hash, role, is_active, created_at, updated_at)
        VALUES ('cashier_raj', 'Raj Kumar', 'raj@apexstore.com', ?, 'CASHIER', 1, '2026-10-15T00:00:00Z', '2026-10-15T00:00:00Z');
        """,
        (pwd_hash,),
    )
    conn.commit()
    cursor.close()
    conn.close()

    # 1. Staff signs in with username
    res_user = client.post("/api/v1/auth/login", json={"username": "cashier_raj", "password": "StaffPass123!"})
    assert res_user.status_code == 200
    assert res_user.json()["user"]["username"] == "cashier_raj"
    assert res_user.json()["user"]["email"] == "raj@apexstore.com"

    # 2. Staff signs in with email
    res_email = client.post("/api/v1/auth/login", json={"username": "raj@apexstore.com", "password": "StaffPass123!"})
    assert res_email.status_code == 200
    assert res_email.json()["user"]["username"] == "cashier_raj"

    # 3. Staff signs in with uppercase email
    res_case = client.post("/api/v1/auth/login", json={"username": "RAJ@APEXSTORE.COM", "password": "StaffPass123!"})
    assert res_case.status_code == 200
    assert res_case.json()["user"]["username"] == "cashier_raj"
