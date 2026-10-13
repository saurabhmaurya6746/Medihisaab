"""Asymmetric Ed25519 digital signature engine for issuing client licenses."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from licensing_service.config import settings

logger = logging.getLogger("licensing_service.security.signer")


def canonical_representation(payload: Dict[str, Any]) -> bytes:
    """Generate deterministic byte sequence for digital signing (exact match with client daemon).

    Supports versioned formats:
    - Version 1 (legacy / unversioned): 7 standard fields without grace_period_days.
    - Version 2 (current): 9 standard fields including grace_period_days and version.
    """
    raw_ver = payload.get("version")
    if raw_ver is None or raw_ver == 1 or raw_ver == "1":
        fields = [
            ("activation_date", str(payload.get("activation_date", ""))),
            ("client_name", str(payload.get("client_name", "")).strip()),
            ("edition", str(payload.get("edition", "COMMERCIAL"))),
            ("expiry_date", str(payload.get("expiry_date") or "")),
            ("features", str(payload.get("features", "ALL"))),
            ("license_id", str(payload.get("license_id", "")).strip()),
            ("terminal_count", str(payload.get("terminal_count", 1))),
        ]
    elif raw_ver == 2 or raw_ver == "2":
        try:
            grace_val = payload.get("grace_period_days", 0)
            if grace_val is None:
                grace_val = 0
            grace = int(grace_val)
            if grace < 0 or grace > 365:
                raise ValueError(f"grace_period_days must be between 0 and 365, got {grace}")
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Malformed grace_period_days in license payload: {exc}")

        fields = [
            ("activation_date", str(payload.get("activation_date", ""))),
            ("client_name", str(payload.get("client_name", "")).strip()),
            ("edition", str(payload.get("edition", "COMMERCIAL"))),
            ("expiry_date", str(payload.get("expiry_date") or "")),
            ("features", str(payload.get("features", "ALL"))),
            ("grace_period_days", str(grace)),
            ("license_id", str(payload.get("license_id", "")).strip()),
            ("terminal_count", str(payload.get("terminal_count", 1))),
            ("version", "2"),
        ]
    else:
        raise ValueError(f"Unsupported license schema version: {raw_ver}")

    canonical_str = "|".join(f"{k}={v}" for k, v in sorted(fields))
    return canonical_str.encode("utf-8")


class LicenseSigner:
    """Server-side license signer that uses the vendor's private key."""

    def __init__(self):
        self._private_key: Optional[ed25519.Ed25519PrivateKey] = None

    def get_private_key(self) -> ed25519.Ed25519PrivateKey:
        """Resolve private key from environment variable, file, or default repository path."""
        if self._private_key is not None:
            return self._private_key

        # 1. Environment variable LICENSE_PRIVATE_KEY_PEM (Render Web Service production)
        if settings.LICENSE_PRIVATE_KEY_PEM:
            key_data = settings.LICENSE_PRIVATE_KEY_PEM.encode("utf-8")
            self._private_key = serialization.load_pem_private_key(key_data, password=None)  # type: ignore
            return self._private_key

        # 2. Configured file path
        if settings.LICENSE_PRIVATE_KEY_PATH:
            p = Path(settings.LICENSE_PRIVATE_KEY_PATH)
            if p.exists():
                self._private_key = serialization.load_pem_private_key(p.read_bytes(), password=None)  # type: ignore
                return self._private_key

        # 3. Local development fallback: look in publisher_keys/license_private_key.pem
        for parent in Path(__file__).resolve().parents:
            cand = parent / "publisher_keys" / "license_private_key.pem"
            if cand.exists():
                self._private_key = serialization.load_pem_private_key(cand.read_bytes(), password=None)  # type: ignore
                return self._private_key

        # 4. If test/development and no key found, generate an ephemeral key with warning
        logger.warning("No Ed25519 private key found. Generating ephemeral key for testing.")
        self._private_key = ed25519.Ed25519PrivateKey.generate()
        return self._private_key

    def sign_license(self, payload: Dict[str, Any]) -> str:
        """Compute Ed25519 digital signature for license payload."""
        if "version" not in payload:
            payload["version"] = 2
        priv = self.get_private_key()
        raw = canonical_representation(payload)
        sig = priv.sign(raw)
        return sig.hex()

    def verify_license(self, payload: Dict[str, Any], public_key_hex: Optional[str] = None) -> bool:
        """Verify signature against given public key or configured public key."""
        sig_hex = payload.get("signature", "")
        if not sig_hex:
            return False

        pub_hex = public_key_hex or settings.LICENSE_PUBLIC_KEY_HEX
        try:
            sig_bytes = bytes.fromhex(sig_hex)
            pub_bytes = bytes.fromhex(pub_hex)
            pub = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
            raw = canonical_representation(payload)
            pub.verify(sig_bytes, raw)
            return True
        except (InvalidSignature, ValueError, Exception):
            return False


signer = LicenseSigner()
