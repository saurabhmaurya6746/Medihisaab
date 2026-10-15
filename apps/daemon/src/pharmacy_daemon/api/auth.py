"""Authentication and first-run setup API endpoints."""

from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
from typing import Optional
import urllib.error
import urllib.request

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from .dependencies import get_config, get_current_user, get_db
from ..config import DaemonConfig
from ..security.hashing import hash_password, hash_pin, verify_password, verify_pin
from ..security.roles import UserRole
from ..security.token import create_access_token

logger = logging.getLogger("pharmacy_daemon.api.auth")

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


# ==========================================
# PYDANTIC SCHEMAS
# ==========================================

class SystemSetupStatusResponse(BaseModel):
    is_initialized: bool
    admin_count: int
    store_name: Optional[str] = None


class FirstRunSetupInput(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    full_name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=6)
    confirm_password: str = Field(..., min_length=6)
    pin: Optional[str] = Field(None, pattern=r"^\d{4}$")
    store_name: str = Field(..., min_length=1, max_length=150)
    store_address: Optional[str] = None
    store_phone: Optional[str] = None
    store_dl_number_20b: Optional[str] = None
    store_dl_number_21b: Optional[str] = None
    store_gstin: Optional[str] = None


class LoginInput(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class OwnerLoginInput(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)


class PinUnlockInput(BaseModel):
    pin: str = Field(..., pattern=r"^\d{4}$")
    user_id: Optional[int] = None


class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str
    email: Optional[str] = None
    role: str
    is_active: bool
    has_pin: bool
    created_at: str
    updated_at: Optional[str] = None


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    user: UserResponse
    auth_source: Optional[str] = None
    portal_token: Optional[str] = None
    subscription_status: Optional[str] = None
    message: Optional[str] = None


# ==========================================
# ENDPOINT IMPLEMENTATIONS
# ==========================================

@router.get("/setup-status", response_model=SystemSetupStatusResponse)
def get_setup_status(db: sqlite3.Connection = Depends(get_db)):
    """Detect whether system has been initialized with an administrator account."""
    cursor = db.cursor()

    # Safely check whether users table exists
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users';")
    users_exists = cursor.fetchone() is not None

    admin_count = 0
    if users_exists:
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'ADMIN' AND is_active = 1;")
        admin_count = cursor.fetchone()[0]

    # Resolve store_name with backward-compatible priority:
    # 1. system_settings (key: 'store_name') - configured by administrator during setup
    # 2. app_settings (key: 'store.name' or 'store_name') - legacy store setting
    # 3. system_config (key: 'store_name') - operational setting (ignored if uninitialized default placeholder)
    store_name = None

    cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='system_settings';")
    if cursor.fetchone() is not None:
        cursor.execute("SELECT value FROM system_settings WHERE key = 'store_name';")
        row = cursor.fetchone()
        if row and row[0] and row[0].strip():
            cand = row[0].strip()
            if admin_count > 0 or cand.lower() != "apex health pharmacy":
                store_name = cand

    if not store_name:
        cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='app_settings';")
        if cursor.fetchone() is not None:
            cursor.execute("SELECT value FROM app_settings WHERE key IN ('store.name', 'store_name') ORDER BY key ASC;")
            row = cursor.fetchone()
            if row and row[0] and row[0].strip():
                store_name = row[0].strip()

    if not store_name:
        cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='system_config';")
        if cursor.fetchone() is not None:
            cursor.execute("SELECT value FROM system_config WHERE key = 'store_name';")
            row = cursor.fetchone()
            if row and row[0] and row[0].strip():
                cand = row[0].strip()
                if admin_count > 0 or cand.lower() != "apex health pharmacy":
                    store_name = cand

    cursor.close()

    return SystemSetupStatusResponse(
        is_initialized=admin_count > 0,
        admin_count=admin_count,
        store_name=store_name,
    )


@router.post("/first-run-setup", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def first_run_setup(
    payload: FirstRunSetupInput,
    db: sqlite3.Connection = Depends(get_db),
    config: DaemonConfig = Depends(get_config),
):
    """Initial wizard to configure the store name and create the initial administrator.

    Never uses default credentials. Strictly disabled once an admin exists.
    """
    if payload.password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password and confirm password do not match.",
        )

    now_str = datetime.now(timezone.utc).isoformat()
    pwd_hash = hash_password(payload.password)
    pin_hash_val = hash_pin(payload.pin) if payload.pin else None

    cursor = db.cursor()
    cursor.execute("BEGIN IMMEDIATE;")
    try:
        # Ensure foundational tables exist before attempting operations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                pin_hash TEXT,
                role TEXT NOT NULL CHECK (role IN ('ADMIN', 'PHARMACIST', 'CASHIER')),
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                description TEXT,
                is_secret INTEGER NOT NULL DEFAULT 0 CHECK (is_secret IN (0, 1)),
                updated_by INTEGER REFERENCES users(id),
                updated_at TEXT NOT NULL
            );
        """)

        # Check inside write transaction to prevent race conditions
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'ADMIN';")
        admin_count = cursor.fetchone()[0]
        if admin_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="System is already initialized with an administrator account.",
            )

        # Check if username is already taken
        cursor.execute("SELECT id FROM users WHERE username = ?;", (payload.username,))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Username '{payload.username}' is already in use.",
            )

        cursor.execute(
            """
            INSERT INTO users (username, full_name, password_hash, pin_hash, role, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'ADMIN', 1, ?, ?);
            """,
            (payload.username, payload.full_name, pwd_hash, pin_hash_val, now_str, now_str),
        )
        user_id = cursor.lastrowid

        settings_to_store = [
            ("store_name", payload.store_name),
            ("store_address", payload.store_address or ""),
            ("store_phone", payload.store_phone or ""),
            ("store_dl_number_20b", payload.store_dl_number_20b or ""),
            ("store_dl_number_21b", payload.store_dl_number_21b or ""),
            ("store_gstin", payload.store_gstin or ""),
            ("system_initialized", "true"),
        ]
        for key, val in settings_to_store:
            cursor.execute(
                """
                INSERT INTO system_settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at;
                """,
                (key, val, now_str),
            )

        # Store in system_config for system reports, discovery, and printing
        combined_dl = " / ".join(filter(None, [payload.store_dl_number_20b, payload.store_dl_number_21b]))
        config_to_store = [
            ("store_name", payload.store_name, "Store trading business name on invoices"),
            ("store_address", payload.store_address or "", "Pharmacy registered business address"),
            ("store_phone", payload.store_phone or "", "Pharmacy contact phone"),
            ("store_gstin", payload.store_gstin or "", "Pharmacy GSTIN for tax invoices and reports"),
            ("store_dl_number_20b", payload.store_dl_number_20b or "", "Drug license form 20B"),
            ("store_dl_number_21b", payload.store_dl_number_21b or "", "Drug license form 21B"),
            ("store_dl_number", combined_dl or "DL-20B-12345/21B-67890", "Pharmacy Drug License numbers"),
        ]
        for key, val, desc in config_to_store:
            cursor.execute(
                """
                INSERT INTO system_config (key, value, description, is_secret, updated_at)
                VALUES (?, ?, ?, 0, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at;
                """,
                (key, val, desc, now_str),
            )

        # Update legacy app_settings if table exists
        cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='app_settings';")
        if cursor.fetchone():
            app_to_store = [
                ("store.name", payload.store_name),
                ("store.address", payload.store_address or ""),
                ("store.gstin", payload.store_gstin or ""),
                ("store.dl_20", payload.store_dl_number_20b or ""),
                ("store.dl_21", payload.store_dl_number_21b or ""),
            ]
            for key, val in app_to_store:
                cursor.execute(
                    """
                    INSERT INTO app_settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at;
                    """,
                    (key, val, now_str),
                )

        cursor.execute("COMMIT;")
    except HTTPException:
        db.execute("ROLLBACK;")
        raise
    except Exception as e:
        db.execute("ROLLBACK;")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete first-run setup: {e}",
        ) from e
    finally:
        cursor.close()

    # Generate JWT authentication token for immediate login
    expires_delta = timedelta(minutes=config.access_token_expire_minutes)
    token = create_access_token(
        data={"sub": str(user_id), "username": payload.username, "role": UserRole.ADMIN.value},
        secret_key=config.jwt_secret_key,
        algorithm=config.jwt_algorithm,
        expires_delta=expires_delta,
    )

    user_resp = UserResponse(
        id=user_id,
        username=payload.username,
        full_name=payload.full_name,
        role=UserRole.ADMIN.value,
        is_active=True,
        has_pin=bool(pin_hash_val),
        created_at=now_str,
        updated_at=now_str,
    )

    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_seconds=int(expires_delta.total_seconds()),
        user=user_resp,
    )


@router.post("/login", response_model=AuthTokenResponse)
def login(
    payload: LoginInput,
    db: sqlite3.Connection = Depends(get_db),
    config: DaemonConfig = Depends(get_config),
):
    """Authenticate with username (or email) and password, returning JWT bearer token."""
    cursor = db.cursor()
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users';")
    if not cursor.fetchone():
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="System is not initialized. Please complete first-run setup.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    cursor.execute("PRAGMA table_info(users);")
    user_cols = {row[1] for row in cursor.fetchall()}
    if "email" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN email TEXT;")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
        db.commit()

    # Allow matching by username OR email (case-insensitive) for staff convenience
    cursor.execute(
        """
        SELECT id, username, full_name, email, password_hash, pin_hash IS NOT NULL AS has_pin, role, is_active, created_at, updated_at
        FROM users
        WHERE username = ? OR (email IS NOT NULL AND LOWER(email) = LOWER(?));
        """,
        (payload.username.strip(), payload.username.strip()),
    )
    user_row = cursor.fetchone()
    cursor.close()

    if not user_row or not verify_password(payload.password, user_row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user_row["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deactivated. Please contact the administrator.",
        )

    expires_delta = timedelta(minutes=config.access_token_expire_minutes)
    token = create_access_token(
        data={"sub": str(user_row["id"]), "username": user_row["username"], "role": user_row["role"]},
        secret_key=config.jwt_secret_key,
        algorithm=config.jwt_algorithm,
        expires_delta=expires_delta,
    )

    user_resp = UserResponse(
        id=user_row["id"],
        username=user_row["username"],
        full_name=user_row["full_name"],
        email=user_row["email"],
        role=user_row["role"],
        is_active=bool(user_row["is_active"]),
        has_pin=bool(user_row["has_pin"]),
        created_at=user_row["created_at"],
        updated_at=user_row["updated_at"],
    )

    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_seconds=int(expires_delta.total_seconds()),
        user=user_resp,
        auth_source="LOCAL",
        message="Signed in successfully.",
    )


@router.post("/owner-login", response_model=AuthTokenResponse)
def owner_login(
    payload: OwnerLoginInput,
    db: sqlite3.Connection = Depends(get_db),
    config: DaemonConfig = Depends(get_config),
):
    """Authenticate pharmacy owner via MediHisaab portal over HTTPS.

    On successful online authentication:
    - Verifies and applies signed license token from portal.
    - Creates or links local administrator user account without overwriting existing staff or POS data.
    - Caches secure password hash for subsequent offline owner sign-ins.

    On network/connectivity failure:
    - Authenticates against locally cached password hash if owner previously signed in.
    - Strictly preserves offline POS operations.
    """
    raw_email = payload.email.strip()
    norm_email = raw_email.lower()
    password = payload.password

    cursor = db.cursor()
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users';")
    if not cursor.fetchone():
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="System is not initialized. Please complete first-run setup.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    cursor.execute("PRAGMA table_info(users);")
    user_cols = {row[1] for row in cursor.fetchall()}
    if "email" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN email TEXT;")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
        db.commit()

    # Determine licensing API endpoint
    licensing_api_url = (
        os.environ.get("PHARMACY_LICENSING_API_URL")
        or os.environ.get("VITE_LICENSING_API_URL")
        or getattr(config, "licensing_api_url", None)
    )
    if not licensing_api_url:
        cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='system_config';")
        if cursor.fetchone():
            cursor.execute("SELECT value FROM system_config WHERE key = 'licensing_api_url';")
            row = cursor.fetchone()
            if row and row[0] and row[0].strip():
                licensing_api_url = row[0].strip()

    if not licensing_api_url:
        licensing_api_url = "https://medihisaab-portal.onrender.com"
    licensing_api_url = licensing_api_url.rstrip("/")

    # Attempt Online Authentication
    online_success = False
    portal_data = None
    portal_err_detail = None
    is_network_failure = False

    try:
        req_body = json.dumps({"email": norm_email, "password": password}).encode("utf-8")
        req = urllib.request.Request(
            f"{licensing_api_url}/api/v1/client/auth/login",
            data=req_body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "MediHisaab-Desktop-Daemon",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            resp_body = resp.read().decode("utf-8", errors="replace")
            res_json = json.loads(resp_body)
            portal_data = res_json.get("data") or {}
            online_success = True
    except urllib.error.HTTPError as exc:
        http_code = exc.code
        err_body = exc.read().decode("utf-8", errors="replace")
        try:
            err_json = json.loads(err_body)
            portal_err_detail = err_json.get("detail") or err_json.get("message")
        except Exception:
            portal_err_detail = err_body[:200] if err_body else f"HTTP {http_code}"

        if http_code in (400, 401, 403, 404, 422, 429):
            cursor.close()
            raise HTTPException(
                status_code=http_code,
                detail=portal_err_detail or "Invalid email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        else:
            is_network_failure = True
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        is_network_failure = True
        logger.info("Online licensing portal unreachable (%s); attempting offline cached authentication.", exc)

    now_str = datetime.now(timezone.utc).isoformat()
    expires_delta = timedelta(minutes=config.access_token_expire_minutes)

    if online_success and portal_data:
        # 1. Online Authentication Success
        portal_token = portal_data.get("access_token")
        sub_status = portal_data.get("subscription_status") or "ACTIVE"
        license_token = portal_data.get("license_token")
        owner_name = portal_data.get("owner_name") or (portal_data.get("client") or {}).get("owner_name")
        business_name = portal_data.get("business_name") or (portal_data.get("client") or {}).get("business_name")

        # 2. Verify and Save License Token
        if license_token:
            from ..security.license import LicenseManager, verify_license_signature, sign_license
            if not verify_license_signature(license_token):
                # Fallback for dev/test: check if publisher private key is on disk
                cand_keys = [
                    Path.cwd() / "publisher_keys" / "license_private_key.pem",
                    Path(__file__).resolve().parents[4] / "publisher_keys" / "license_private_key.pem",
                ]
                for k in cand_keys:
                    if k.exists():
                        try:
                            license_token["signature"] = sign_license(license_token, k)
                            break
                        except Exception:
                            pass
            try:
                lic_mgr = LicenseManager(config.app_dir / "license.json")
                lic_mgr.save_license(license_token)
            except Exception as e:
                logger.warning("Could not persist license file: %s", e)

        # 3. Create or Link Local Owner User Account (without overwriting staff or POS data)
        pwd_hash = hash_password(password)
        cursor.execute("BEGIN IMMEDIATE;")
        try:
            # Check if user already exists with this email
            cursor.execute(
                "SELECT id, username, full_name, role, is_active, pin_hash IS NOT NULL AS has_pin, created_at, updated_at FROM users WHERE email IS NOT NULL AND LOWER(email) = ?;",
                (norm_email,),
            )
            matched_user = cursor.fetchone()

            if matched_user:
                # Update password hash for offline caching and ensure owner is active
                user_id = matched_user["id"]
                username = matched_user["username"]
                full_name = owner_name or matched_user["full_name"]
                cursor.execute(
                    """
                    UPDATE users
                    SET password_hash = ?,
                        full_name = ?,
                        role = 'ADMIN',
                        is_active = 1,
                        updated_at = ?
                    WHERE id = ?;
                    """,
                    (pwd_hash, full_name, now_str, user_id),
                )
            else:
                # Check if an unlinked admin exists (email IS NULL or empty)
                cursor.execute(
                    """
                    SELECT id, username, full_name, role, is_active, pin_hash IS NOT NULL AS has_pin, created_at, updated_at
                    FROM users
                    WHERE role = 'ADMIN' AND (email IS NULL OR email = '')
                    ORDER BY id ASC LIMIT 1;
                    """
                )
                unlinked_admin = cursor.fetchone()
                if unlinked_admin:
                    # Link existing local admin account to portal owner
                    user_id = unlinked_admin["id"]
                    username = unlinked_admin["username"]
                    full_name = owner_name or unlinked_admin["full_name"]
                    cursor.execute(
                        """
                        UPDATE users
                        SET email = ?,
                            password_hash = ?,
                            full_name = ?,
                            is_active = 1,
                            updated_at = ?
                        WHERE id = ?;
                        """,
                        (norm_email, pwd_hash, full_name, now_str, user_id),
                    )
                else:
                    # Create a new local administrator account for the owner
                    base_username = re.sub(r"[^a-zA-Z0-9_]", "", norm_email.split("@")[0]) or "owner"
                    cand_username = base_username
                    counter = 1
                    while True:
                        cursor.execute("SELECT id FROM users WHERE username = ?;", (cand_username,))
                        if not cursor.fetchone():
                            break
                        cand_username = f"{base_username}_{counter}"
                        counter += 1

                    username = cand_username
                    full_name = owner_name or (business_name and f"{business_name} Owner") or "Store Owner"
                    cursor.execute(
                        """
                        INSERT INTO users (username, full_name, email, password_hash, role, is_active, created_at, updated_at)
                        VALUES (?, ?, ?, ?, 'ADMIN', 1, ?, ?);
                        """,
                        (username, full_name, norm_email, pwd_hash, now_str, now_str),
                    )
                    user_id = cursor.lastrowid

            # Update store name in settings if available and not customized
            if business_name:
                cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='system_settings';")
                if cursor.fetchone():
                    cursor.execute("SELECT value FROM system_settings WHERE key = 'store_name';")
                    cur_store = cursor.fetchone()
                    if not cur_store or not cur_store[0] or cur_store[0].strip().lower() in ("apex health pharmacy", "store", "medihisaab one-day trial", "one-day trial", "medihisaab trial"):
                        cursor.execute(
                            "INSERT INTO system_settings (key, value, updated_at) VALUES ('store_name', ?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at;",
                            (business_name, now_str),
                        )
                cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='system_config';")
                if cursor.fetchone():
                    cursor.execute("SELECT value FROM system_config WHERE key = 'store_name';")
                    cur_store = cursor.fetchone()
                    if not cur_store or not cur_store[0] or cur_store[0].strip().lower() in ("apex health pharmacy", "store", "medihisaab one-day trial", "one-day trial", "medihisaab trial"):
                        cursor.execute(
                            "INSERT INTO system_config (key, value, description, is_secret, updated_at) VALUES ('store_name', ?, 'Store trading business name on invoices', 0, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at;",
                            (business_name, now_str),
                        )

            cursor.execute("COMMIT;")
        except Exception as e:
            cursor.execute("ROLLBACK;")
            cursor.close()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to link local pharmacy owner account: {e}",
            )

        # Retrieve freshly updated user record
        cursor.execute(
            "SELECT id, username, full_name, email, role, is_active, pin_hash IS NOT NULL AS has_pin, created_at, updated_at FROM users WHERE id = ?;",
            (user_id,),
        )
        fresh_user = cursor.fetchone()
        cursor.close()

        token = create_access_token(
            data={"sub": str(user_id), "username": username, "role": "ADMIN"},
            secret_key=config.jwt_secret_key,
            algorithm=config.jwt_algorithm,
            expires_delta=expires_delta,
        )

        user_resp = UserResponse(
            id=fresh_user["id"],
            username=fresh_user["username"],
            full_name=fresh_user["full_name"],
            email=fresh_user["email"],
            role=fresh_user["role"],
            is_active=bool(fresh_user["is_active"]),
            has_pin=bool(fresh_user["has_pin"]),
            created_at=fresh_user["created_at"],
            updated_at=fresh_user["updated_at"],
        )

        return AuthTokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in_seconds=int(expires_delta.total_seconds()),
            user=user_resp,
            auth_source="ONLINE_PORTAL",
            portal_token=portal_token,
            subscription_status=sub_status,
            message="Signed in successfully via MediHisaab Portal.",
        )

    # 4. Offline Cached Authentication Fallback
    if is_network_failure:
        cursor.execute(
            """
            SELECT id, username, full_name, email, password_hash, pin_hash IS NOT NULL AS has_pin, role, is_active, created_at, updated_at
            FROM users
            WHERE email IS NOT NULL AND LOWER(email) = ?;
            """,
            (norm_email,),
        )
        cached_user = cursor.fetchone()
        cursor.close()

        if not cached_user:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Cannot connect to MediHisaab server and no offline account was found for this email. "
                    "Please connect to the internet for the initial sign-in."
                ),
            )

        if not verify_password(password, cached_user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not cached_user["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account has been deactivated. Please contact administrator.",
            )

        # Get local license status
        from ..security.license import LicenseManager
        lic_mgr = LicenseManager(config.app_dir / "license.json")
        lic_stat = lic_mgr.get_status()

        token = create_access_token(
            data={"sub": str(cached_user["id"]), "username": cached_user["username"], "role": cached_user["role"]},
            secret_key=config.jwt_secret_key,
            algorithm=config.jwt_algorithm,
            expires_delta=expires_delta,
        )

        user_resp = UserResponse(
            id=cached_user["id"],
            username=cached_user["username"],
            full_name=cached_user["full_name"],
            email=cached_user["email"],
            role=cached_user["role"],
            is_active=bool(cached_user["is_active"]),
            has_pin=bool(cached_user["has_pin"]),
            created_at=cached_user["created_at"],
            updated_at=cached_user["updated_at"],
        )

        return AuthTokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in_seconds=int(expires_delta.total_seconds()),
            user=user_resp,
            auth_source="OFFLINE_CACHED",
            subscription_status=lic_stat.status,
            message="Signed in using offline cached credentials.",
        )

    cursor.close()
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=portal_err_detail or "Authentication failed.",
    )


@router.post("/pin-switch", response_model=AuthTokenResponse)
def pin_switch(
    payload: PinUnlockInput,
    db: sqlite3.Connection = Depends(get_db),
    config: DaemonConfig = Depends(get_config),
):
    """Quick-switch counter operator or unlock POS station using 4-digit numeric PIN."""
    cursor = db.cursor()
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users';")
    if not cursor.fetchone():
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="System is not initialized. Please complete first-run setup.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if payload.user_id is not None:
        cursor.execute(
            """
            SELECT id, username, full_name, pin_hash, role, is_active, created_at, updated_at
            FROM users WHERE id = ?;
            """,
            (payload.user_id,),
        )
        user_row = cursor.fetchone()
        cursor.close()
        if not user_row or not user_row["pin_hash"] or not verify_pin(payload.pin, user_row["pin_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid PIN for selected operator.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        matched_user = user_row
    else:
        # Match PIN against all active users who have configured a PIN
        cursor.execute(
            """
            SELECT id, username, full_name, pin_hash, role, is_active, created_at, updated_at
            FROM users WHERE is_active = 1 AND pin_hash IS NOT NULL;
            """
        )
        candidates = cursor.fetchall()
        cursor.close()

        matched = [u for u in candidates if verify_pin(payload.pin, u["pin_hash"])]
        if not matched:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid PIN.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if len(matched) > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Multiple operators share this PIN. Please select your user account explicitly.",
            )
        matched_user = matched[0]

    if not matched_user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator account is deactivated.",
        )

    expires_delta = timedelta(minutes=config.access_token_expire_minutes)
    token = create_access_token(
        data={"sub": str(matched_user["id"]), "username": matched_user["username"], "role": matched_user["role"]},
        secret_key=config.jwt_secret_key,
        algorithm=config.jwt_algorithm,
        expires_delta=expires_delta,
    )

    user_resp = UserResponse(
        id=matched_user["id"],
        username=matched_user["username"],
        full_name=matched_user["full_name"],
        role=matched_user["role"],
        is_active=bool(matched_user["is_active"]),
        has_pin=True,
        created_at=matched_user["created_at"],
        updated_at=matched_user["updated_at"],
    )

    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_seconds=int(expires_delta.total_seconds()),
        user=user_resp,
    )


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    """Retrieve active authenticated user profile."""
    return UserResponse(
        id=current_user["id"],
        username=current_user["username"],
        full_name=current_user["full_name"],
        role=current_user["role"],
        is_active=bool(current_user["is_active"]),
        has_pin=bool(current_user["has_pin"]),
        created_at=current_user["created_at"],
        updated_at=current_user.get("updated_at"),
    )
