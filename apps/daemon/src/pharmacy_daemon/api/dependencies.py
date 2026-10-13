"""FastAPI dependencies for database connections, authentication, and role authorization."""

from typing import Callable, Generator
import sqlite3
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..config import DaemonConfig
from ..security.roles import UserRole
from ..security.token import decode_access_token, TokenExpiredError, InvalidTokenError

security_bearer = HTTPBearer(auto_error=False)


def get_db(request: Request) -> Generator[sqlite3.Connection, None, None]:
    """Provide a scoped SQLite connection with WAL pragmas."""
    engine = request.app.state.db_engine
    conn = engine.get_connection()
    try:
        yield conn
    finally:
        conn.close()


def get_config(request: Request) -> DaemonConfig:
    """Retrieve daemon runtime configuration from app state."""
    return request.app.state.config


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_bearer),
    db: sqlite3.Connection = Depends(get_db),
    config: DaemonConfig = Depends(get_config),
) -> dict:
    """Validate Bearer JWT and return active user profile."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = decode_access_token(token, secret_key=config.jwt_secret_key, algorithm=config.jwt_algorithm)
    except TokenExpiredError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token claims.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    cursor = db.cursor()
    cursor.execute(
        "SELECT id, username, full_name, role, is_active, pin_hash IS NOT NULL AS has_pin, created_at, updated_at FROM users WHERE id = ?;",
        (user_id,),
    )
    user_row = cursor.fetchone()
    cursor.close()

    if not user_row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with token no longer exists.",
        )

    if not user_row["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated. Contact store administrator.",
        )

    return dict(user_row)


def require_role(*allowed_roles: UserRole) -> Callable:
    """Dependency factory checking that active user belongs to one of allowed roles."""

    def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        user_role = current_user.get("role")
        role_values = [r.value if isinstance(r, UserRole) else str(r) for r in allowed_roles]
        if user_role not in role_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted for role '{user_role}'. Required roles: {role_values}",
            )
        return current_user

    return role_checker


def verify_license_allows_writes(request: Request) -> None:
    """Ensure the system has an active signed license or valid grace period before allowing commercial/master writes.

    Blocks writes if:
    - Status is EXPIRED (license and grace period elapsed)
    - Status is UNLICENSED_COMMUNITY (absent license cannot enable commercial writes)
    - Status is INVALID_SIGNATURE (tampered/corrupt license)
    - Status is NOT_YET_ACTIVE (future activation date)

    Allows writes ONLY if:
    - Status is ACTIVE (active commercial license)
    - Status is TRIAL (active 15-day evaluation trial)
    - Status is GRACE_PERIOD (active grace window)
    """
    config = getattr(request.app.state, "config", None) if request and hasattr(request, "app") else None
    if not config:
        from ..config import DaemonConfig
        config = DaemonConfig.load()

    from ..security.license import LicenseManager
    lic_mgr = LicenseManager(config.app_dir / "license.json")
    lic_status = lic_mgr.get_status()

    if lic_status.status not in ("ACTIVE", "TRIAL", "GRACE_PERIOD"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Commercial operations and master-data writes are restricted: License status is {lic_status.status}. "
                f"{lic_status.message} "
                "All historical records, reports, ledgers, and database backups remain fully accessible."
            ),
        )


license_write_guard = Depends(verify_license_allows_writes)


def require_write_role(*allowed_roles: UserRole) -> Callable:
    """Dependency factory checking both role authorization and active license status for write operations."""
    role_checker = require_role(*allowed_roles)

    def guard(request: Request, current_user: dict = Depends(role_checker)) -> dict:
        verify_license_allows_writes(request)
        return current_user

    return guard

