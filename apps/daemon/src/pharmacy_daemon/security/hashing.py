"""Password and PIN hashing utilities using passlib (pbkdf2_sha256 / bcrypt)."""

from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["pbkdf2_sha256", "bcrypt"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    """Compute secure one-way hash for user password."""
    if not password or len(password) < 6:
        raise ValueError("Password must be at least 6 characters long")
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against stored hash using constant-time comparison."""
    if not plain_password or not hashed_password:
        return False
    return pwd_context.verify(plain_password, hashed_password)


def hash_pin(pin: str) -> str:
    """Compute secure hash for 4-digit numeric PIN."""
    if not pin or not pin.isdigit() or len(pin) != 4:
        raise ValueError("PIN must be exactly 4 numeric digits")
    return pwd_context.hash(pin)


def verify_pin(plain_pin: str, hashed_pin: str) -> bool:
    """Verify 4-digit PIN against stored hash."""
    if not plain_pin or not hashed_pin:
        return False
    return pwd_context.verify(plain_pin, hashed_pin)
