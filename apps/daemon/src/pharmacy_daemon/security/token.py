"""JWT access token generation, validation, and payload decoding."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import jwt


class TokenExpiredError(Exception):
    """Raised when provided JWT has expired."""
    pass


class InvalidTokenError(Exception):
    """Raised when provided JWT cannot be decoded or has invalid signature."""
    pass


def create_access_token(
    data: Dict[str, Any],
    secret_key: str,
    algorithm: str = "HS256",
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generate signed JWT bearer token with expiration claims."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(hours=12)

    to_encode.update({
        "exp": expire,
        "iat": now,
    })
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    return encoded_jwt


def decode_access_token(
    token: str,
    secret_key: str,
    algorithm: str = "HS256",
) -> Dict[str, Any]:
    """Verify and decode signed JWT token into payload dictionary."""
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        return payload
    except jwt.ExpiredSignatureError as e:
        raise TokenExpiredError("Session token has expired. Please log in again.") from e
    except jwt.PyJWTError as e:
        raise InvalidTokenError("Invalid session token.") from e
