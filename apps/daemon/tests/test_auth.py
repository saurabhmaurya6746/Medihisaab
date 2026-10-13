"""Tests for password hashing, JWT token expiration, first-run setup, authentication, and RBAC."""

from datetime import timedelta
import pytest
from fastapi.testclient import TestClient

from pharmacy_daemon.security.hashing import (
    hash_password,
    verify_password,
    hash_pin,
    verify_pin,
)
from pharmacy_daemon.security.roles import UserRole, has_permission
from pharmacy_daemon.security.token import (
    create_access_token,
    decode_access_token,
    TokenExpiredError,
)


# ==========================================
# 1. HASHING & PIN TESTS
# ==========================================

def test_password_hashing_and_verification():
    """Verify secure password hashing and constant-time verification."""
    password = "MySecurePassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False
    assert verify_password("", hashed) is False


def test_password_hashing_length_validation():
    """Verify short passwords are systematically rejected."""
    with pytest.raises(ValueError, match="at least 6 characters"):
        hash_password("12345")


def test_pin_hashing_and_verification():
    """Verify 4-digit PIN hashing and strict digit validation."""
    pin = "4829"
    hashed = hash_pin(pin)

    assert hashed != pin
    assert verify_pin(pin, hashed) is True
    assert verify_pin("9999", hashed) is False

    with pytest.raises(ValueError, match="exactly 4 numeric digits"):
        hash_pin("123")  # Too short

    with pytest.raises(ValueError, match="exactly 4 numeric digits"):
        hash_pin("12345")  # Too long

    with pytest.raises(ValueError, match="exactly 4 numeric digits"):
        hash_pin("abcd")  # Non-numeric


# ==========================================
# 2. JWT TOKEN & EXPIRATION TESTS
# ==========================================

def test_jwt_token_creation_and_payload_decoding():
    """Verify JWT bearer token contains correct user claims and expiration."""
    secret = "test_super_secret_jwt_key_with_at_least_32_bytes_length!"
    data = {"sub": "1", "username": "owner", "role": "ADMIN"}
    token = create_access_token(data, secret_key=secret, expires_delta=timedelta(minutes=15))

    payload = decode_access_token(token, secret_key=secret)
    assert payload["sub"] == "1"
    assert payload["username"] == "owner"
    assert payload["role"] == "ADMIN"
    assert "exp" in payload
    assert "iat" in payload


def test_jwt_token_expiration_rejection():
    """Verify expired JWT bearer tokens are rejected."""
    secret = "test_super_secret_jwt_key_with_at_least_32_bytes_length!"
    data = {"sub": "1", "username": "owner", "role": "ADMIN"}
    # Token expired 1 second ago
    expired_token = create_access_token(data, secret_key=secret, expires_delta=timedelta(seconds=-1))

    with pytest.raises(TokenExpiredError):
        decode_access_token(expired_token, secret_key=secret)


# ==========================================
# 3. RBAC ROLE CHECKS
# ==========================================

def test_role_permission_matrix():
    """Verify roles enforce operational boundary distinctions."""
    assert has_permission(UserRole.ADMIN.value, "MANAGE_USERS") is True
    assert has_permission(UserRole.ADMIN.value, "RESTORE_BACKUP") is True
    assert has_permission(UserRole.ADMIN.value, "VIEW_PROFIT_MARGINS") is True

    # Pharmacist has dispensing and stock audit permissions, but cannot restore backups or view profit margins
    assert has_permission(UserRole.PHARMACIST.value, "DISPENSE_SCHEDULE_H1") is True
    assert has_permission(UserRole.PHARMACIST.value, "STOCK_AUDIT") is True
    assert has_permission(UserRole.PHARMACIST.value, "MANAGE_USERS") is False
    assert has_permission(UserRole.PHARMACIST.value, "RESTORE_BACKUP") is False
    assert has_permission(UserRole.PHARMACIST.value, "VIEW_PROFIT_MARGINS") is False

    # Cashier has billing and deposits only
    assert has_permission(UserRole.CASHIER.value, "COUNTER_BILLING") is True
    assert has_permission(UserRole.CASHIER.value, "RECORD_KHATA_DEPOSIT") is True
    assert has_permission(UserRole.CASHIER.value, "DISPENSE_SCHEDULE_H1") is False
    assert has_permission(UserRole.CASHIER.value, "MANAGE_USERS") is False


# ==========================================
# 4. FIRST-RUN SETUP & AUTH API TESTS
# ==========================================

def test_setup_status_on_clean_database(client: TestClient):
    """Verify initial clean database indicates system is not initialized."""
    res = client.get("/api/v1/auth/setup-status")
    assert res.status_code == 200
    data = res.json()
    assert data["is_initialized"] is False
    assert data["admin_count"] == 0
    assert data["store_name"] is None


def test_first_run_setup_happy_path_and_duplicate_prevention(client: TestClient):
    """Verify first-run setup creates admin, store settings, and prevents duplicate setup."""
    payload = {
        "username": "superadmin",
        "full_name": "Dr. Rajesh Sharma",
        "password": "StrongPassword789!",
        "confirm_password": "StrongPassword789!",
        "pin": "7711",
        "store_name": "Sharma Medical & Surgical",
        "store_address": "Station Road, Jaunpur, UP",
        "store_phone": "9876543210",
        "store_dl_number_20b": "UP-JNP-20B-12345",
        "store_dl_number_21b": "UP-JNP-21B-67890",
        "store_gstin": "09ABCDE1234F1Z5",
    }

    # 1. Successful first-run setup
    res = client.post("/api/v1/auth/first-run-setup", json=payload)
    assert res.status_code == 201
    auth_data = res.json()
    assert "access_token" in auth_data
    assert auth_data["user"]["username"] == "superadmin"
    assert auth_data["user"]["role"] == "ADMIN"
    assert auth_data["user"]["has_pin"] is True

    # 2. Setup status should now show initialized
    status_res = client.get("/api/v1/auth/setup-status")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["is_initialized"] is True
    assert status_data["admin_count"] == 1
    assert status_data["store_name"] == "Sharma Medical & Surgical"

    # 3. Duplicate setup attempt MUST be blocked with HTTP 400
    duplicate_res = client.post("/api/v1/auth/first-run-setup", json=payload)
    assert duplicate_res.status_code == 400
    assert "already initialized" in duplicate_res.json()["detail"].lower()


def test_first_run_setup_password_mismatch(client: TestClient):
    """Verify first-run setup rejects mismatched password and confirmation."""
    payload = {
        "username": "admin2",
        "full_name": "Test Admin",
        "password": "PasswordOne123!",
        "confirm_password": "PasswordTwo456!",
        "store_name": "Test Pharmacy",
    }
    res = client.post("/api/v1/auth/first-run-setup", json=payload)
    assert res.status_code == 422
    assert "do not match" in res.json()["detail"].lower()


def test_login_success_and_failure(client: TestClient):
    """Verify login with correct credentials succeeds and bad credentials fail."""
    # First setup the store
    setup_payload = {
        "username": "chemist_owner",
        "full_name": "Suresh Gupta",
        "password": "OwnerSecretPassword99!",
        "confirm_password": "OwnerSecretPassword99!",
        "store_name": "Gupta Medical Hall",
    }
    client.post("/api/v1/auth/first-run-setup", json=setup_payload)

    # Valid Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": "chemist_owner", "password": "OwnerSecretPassword99!"},
    )
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert "access_token" in login_data
    assert login_data["user"]["username"] == "chemist_owner"

    # Invalid Password
    bad_pwd_res = client.post(
        "/api/v1/auth/login",
        json={"username": "chemist_owner", "password": "WrongPassword!"},
    )
    assert bad_pwd_res.status_code == 401

    # Non-existent User
    no_user_res = client.post(
        "/api/v1/auth/login",
        json={"username": "ghost_user", "password": "SomePassword!"},
    )
    assert no_user_res.status_code == 401


def test_pin_switch_success_and_failure(client: TestClient):
    """Verify quick PIN unlock and operator switching."""
    setup_payload = {
        "username": "cashier1",
        "full_name": "Mohan Singh",
        "password": "CashierPassword123!",
        "confirm_password": "CashierPassword123!",
        "pin": "5522",
        "store_name": "Singh Chemist",
    }
    client.post("/api/v1/auth/first-run-setup", json=setup_payload)

    # Valid PIN unlock
    pin_res = client.post("/api/v1/auth/pin-switch", json={"pin": "5522"})
    assert pin_res.status_code == 200
    pin_data = pin_res.json()
    assert "access_token" in pin_data
    assert pin_data["user"]["username"] == "cashier1"

    # Invalid PIN
    bad_pin_res = client.post("/api/v1/auth/pin-switch", json={"pin": "9999"})
    assert bad_pin_res.status_code == 401


def test_get_current_user_me_endpoint(client: TestClient):
    """Verify GET /api/v1/auth/me requires valid Bearer token and returns profile."""
    setup_payload = {
        "username": "pharmacist_me",
        "full_name": "Amit Verma",
        "password": "PharmPassword123!",
        "confirm_password": "PharmPassword123!",
        "store_name": "Verma Pharmacy",
    }
    res = client.post("/api/v1/auth/first-run-setup", json=setup_payload)
    token = res.json()["access_token"]

    # Authenticated call
    me_res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["username"] == "pharmacist_me"
    assert me_data["full_name"] == "Amit Verma"
    assert me_data["role"] == "ADMIN"

    # Unauthenticated call
    unauth_res = client.get("/api/v1/auth/me")
    assert unauth_res.status_code == 401

    # Bad token call
    bad_token_res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid_garbage_token"},
    )
    assert bad_token_res.status_code == 401
