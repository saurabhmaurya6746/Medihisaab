"""Authentication, JWT tokens, RBAC permissions, and login rate limiting."""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import time
from typing import Any, Callable, Dict, List, Optional

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from licensing_service.config import settings
from licensing_service.db.models import VendorRole, VendorUser
from licensing_service.db.session import get_db

pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")
security_bearer = HTTPBearer(auto_error=False)

# In-memory sliding window rate limiter for login attempts: ip -> list of timestamps
_LOGIN_ATTEMPTS: Dict[str, List[float]] = defaultdict(list)
_SIGNUP_ATTEMPTS: Dict[str, List[float]] = defaultdict(list)
_RENEWAL_ATTEMPTS: Dict[str, List[float]] = defaultdict(list)


def hash_password(password: str) -> str:
    """Compute secure one-way hash for vendor user password."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against hash using constant-time comparison."""
    return pwd_context.verify(plain_password, hashed_password)


def check_login_rate_limit(client_ip: str) -> None:
    """Enforce login rate limiting (max attempts within window)."""
    now = time.time()
    cutoff = now - settings.RATE_LIMIT_WINDOW_SECONDS
    attempts = [t for t in _LOGIN_ATTEMPTS[client_ip] if t > cutoff]
    if len(attempts) >= settings.RATE_LIMIT_LOGIN_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Please wait {settings.RATE_LIMIT_WINDOW_SECONDS} seconds.",
        )


def record_failed_login_attempt(client_ip: str) -> None:
    """Record a failed login attempt timestamp."""
    _LOGIN_ATTEMPTS[client_ip].append(time.time())


def clear_login_attempts(client_ip: str) -> None:
    """Clear login attempts after successful authentication."""
    if client_ip in _LOGIN_ATTEMPTS:
        del _LOGIN_ATTEMPTS[client_ip]


def check_signup_rate_limit(client_ip: str) -> None:
    """Enforce signup rate limiting to prevent automated trial abuse."""
    now = time.time()
    window = 900  # 15 minutes window
    cutoff = now - window
    attempts = [t for t in _SIGNUP_ATTEMPTS[client_ip] if t > cutoff]
    if len(attempts) >= 10:  # max 10 signups per 15 mins per IP
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many trial registration attempts from this network. Please wait a few minutes or contact support.",
        )


def record_signup_attempt(client_ip: str) -> None:
    """Record a signup attempt timestamp."""
    _SIGNUP_ATTEMPTS[client_ip].append(time.time())


def clear_signup_attempts(client_ip: Optional[str] = None) -> None:
    """Clear signup attempts for an IP, or all IPs if not specified."""
    if client_ip:
        _SIGNUP_ATTEMPTS.pop(client_ip, None)
    else:
        _SIGNUP_ATTEMPTS.clear()


def check_renewal_rate_limit(client_key: str) -> None:
    """Enforce renewal request rate limiting (max 5 requests per 15 minutes)."""
    now = time.time()
    cutoff = now - 900
    attempts = [t for t in _RENEWAL_ATTEMPTS[client_key] if t > cutoff]
    if len(attempts) >= 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many renewal requests. Please wait a few minutes before submitting another request or contact vendor support directly.",
        )


def record_renewal_attempt(client_key: str) -> None:
    """Record a renewal request attempt timestamp."""
    _RENEWAL_ATTEMPTS[client_key].append(time.time())


def clear_renewal_attempts(client_key: Optional[str] = None) -> None:
    """Clear renewal attempts for a client key, or all keys if not specified."""
    if client_key:
        _RENEWAL_ATTEMPTS.pop(client_key, None)
    else:
        _RENEWAL_ATTEMPTS.clear()


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token with expiration claims."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"iat": now, "exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a long-lived signed JWT refresh token for renewing client portal sessions."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(days=30))
    to_encode.update({"iat": now, "exp": expire, "token_use": "refresh"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_vendor_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db),
) -> VendorUser:
    """FastAPI dependency to retrieve currently authenticated vendor user."""
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials are required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(auth.credentials)
    if payload.get("type") == "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Client accounts cannot access vendor administrative endpoints.",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject.")

    user = db.query(VendorUser).filter(VendorUser.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is inactive or not found.")

    return user


def get_current_client(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> Any:
    """FastAPI dependency to retrieve currently authenticated customer client."""
    from licensing_service.db.models import Client

    raw_token = auth.credentials if (auth and auth.credentials) else token
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Client authentication credentials are required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(raw_token)
    if payload.get("type") != "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Customer client access token required.",
        )

    client_id = payload.get("client_id") or payload.get("sub")
    if not client_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject.")

    client = db.query(Client).filter(Client.id == int(client_id)).first()
    if not client:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Client account not found.")

    if client.status in ("SUSPENDED", "CLOSED"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is {client.status.lower()}. Please contact vendor support.",
        )

    return client


def require_role(*allowed_roles: VendorRole) -> Callable:
    """Dependency factory to enforce RBAC permissions."""
    allowed_values = [r.value if isinstance(r, VendorRole) else r for r in allowed_roles]

    def role_checker(user: VendorUser = Depends(get_current_vendor_user)) -> VendorUser:
        if user.role not in allowed_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Action requires one of {allowed_values} roles.",
            )
        return user

    return role_checker
