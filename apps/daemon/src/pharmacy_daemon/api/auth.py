"""Authentication and first-run setup API endpoints."""

from datetime import datetime, timedelta, timezone
import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from .dependencies import get_config, get_current_user, get_db
from ..config import DaemonConfig
from ..security.hashing import hash_password, hash_pin, verify_password, verify_pin
from ..security.roles import UserRole
from ..security.token import create_access_token

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


class PinUnlockInput(BaseModel):
    pin: str = Field(..., pattern=r"^\d{4}$")
    user_id: Optional[int] = None


class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str
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
    """Authenticate with username and password, returning JWT bearer token."""
    cursor = db.cursor()
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users';")
    if not cursor.fetchone():
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="System is not initialized. Please complete first-run setup.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    cursor.execute(
        """
        SELECT id, username, full_name, password_hash, pin_hash IS NOT NULL AS has_pin, role, is_active, created_at, updated_at
        FROM users WHERE username = ?;
        """,
        (payload.username,),
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
