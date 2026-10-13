"""Offline asymmetric cryptographic licensing engine for Pharmacy POS.

Uses Ed25519 public/private key digital signatures (Edwards-curve Digital Signature Algorithm).
The private key is held exclusively by the publisher/vendor to issue and sign licenses.
The public key is embedded in the application to verify signatures offline.
"""

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import json
import logging
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, Optional, Union

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

logger = logging.getLogger("pharmacy_daemon.security.license")

# Embedded Ed25519 Public Key for offline client verification
# (The private signing key is NEVER embedded in application binaries or distributed to clients)
EMBEDDED_PUBLIC_KEY_HEX = "ba7a4f28067b0d4d4e7d90128c48f9316ba5c3069a0cb88fcc5a24b081b3632b"


@dataclass
class LicensePayload:
    client_name: str
    license_id: str
    terminal_count: int
    activation_date: str  # YYYY-MM-DD
    expiry_date: Optional[str] = None  # YYYY-MM-DD or None for perpetual
    edition: str = "COMMERCIAL"
    features: str = "ALL"
    signature: str = ""


@dataclass
class LicenseStatus:
    is_valid: bool
    status: str  # "ACTIVE", "TRIAL", "EXPIRED", "GRACE_PERIOD", "INVALID_SIGNATURE", "NOT_YET_ACTIVE", "UNLICENSED_COMMUNITY"
    client_name: str
    license_id: str
    terminal_count: int
    activation_date: str
    expiry_date: Optional[str]
    edition: str
    message: str
    remaining_days: Optional[int] = None
    grace_period_active: bool = False


def canonical_representation(payload: Dict[str, Any]) -> bytes:
    """Generate deterministic byte sequence for digital signing.

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


def load_private_key(private_key_spec: Union[ed25519.Ed25519PrivateKey, bytes, str, Path]) -> ed25519.Ed25519PrivateKey:
    """Load an Ed25519 private key from instance, PEM bytes, or file path."""
    if isinstance(private_key_spec, ed25519.Ed25519PrivateKey):
        return private_key_spec

    if isinstance(private_key_spec, Path):
        key_data = private_key_spec.read_bytes()
    elif isinstance(private_key_spec, str):
        p = Path(private_key_spec)
        if p.exists():
            key_data = p.read_bytes()
        else:
            key_data = private_key_spec.encode("utf-8")
    elif isinstance(private_key_spec, bytes):
        key_data = private_key_spec
    else:
        raise ValueError(f"Unsupported private key format: {type(private_key_spec)}")

    return serialization.load_pem_private_key(key_data, password=None)  # type: ignore


def sign_license(
    payload: Dict[str, Any],
    private_key_spec: Union[ed25519.Ed25519PrivateKey, bytes, str, Path],
) -> str:
    """Compute Ed25519 digital signature for license payload using publisher's private key."""
    if "version" not in payload:
        payload["version"] = 2
    priv = load_private_key(private_key_spec)
    raw = canonical_representation(payload)
    sig_bytes = priv.sign(raw)
    return sig_bytes.hex()


def verify_license_signature(
    payload: Dict[str, Any],
    public_key_hex: str = EMBEDDED_PUBLIC_KEY_HEX,
) -> bool:
    """Verify cryptographic authenticity of the license signature using embedded public key."""
    provided_sig = payload.get("signature", "")
    if not provided_sig or not isinstance(provided_sig, str):
        return False

    try:
        sig_bytes = bytes.fromhex(provided_sig.strip())
        if len(sig_bytes) != 64:
            return False

        pub_bytes = bytes.fromhex(public_key_hex.strip())
        pub = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)

        raw = canonical_representation(payload)
        pub.verify(sig_bytes, raw)
        return True
    except (InvalidSignature, ValueError, Exception) as exc:
        logger.debug("License signature verification rejected: %s", exc)
        return False


def evaluate_license(
    payload: Optional[Dict[str, Any]],
    public_key_hex: str = EMBEDDED_PUBLIC_KEY_HEX,
    current_date: Optional[date] = None,
    last_verified_date: Optional[date] = None,
) -> LicenseStatus:
    """Evaluate license validity against digital signature, device date constraints, and clock anomalies."""
    today = current_date or date.today()

    # Clock anomaly check: Device clock turned backward compared to previously recorded runs
    if last_verified_date and today < last_verified_date:
        return LicenseStatus(
            is_valid=False,
            status="CLOCK_ANOMALY",
            client_name=payload.get("client_name", "Unknown") if payload else "Unknown",
            license_id=payload.get("license_id", "Unknown") if payload else "Unknown",
            terminal_count=int(payload.get("terminal_count", 1)) if payload else 1,
            activation_date=payload.get("activation_date", "") if payload else "",
            expiry_date=payload.get("expiry_date") if payload else None,
            edition=payload.get("edition", "UNKNOWN") if payload else "UNKNOWN",
            message="System clock anomaly detected. Device date appears earlier than previous verified runs. Please correct system date and time.",
            remaining_days=0,
            grace_period_active=False,
        )

    if not payload:
        return LicenseStatus(
            is_valid=True,
            status="UNLICENSED_COMMUNITY",
            client_name="Community / Trial Workstation",
            license_id="COMMUNITY-DEFAULT",
            terminal_count=2,
            activation_date=today.isoformat(),
            expiry_date=None,
            edition="COMMUNITY",
            message="Operating in offline standard mode (up to 2 terminals).",
        )

    # 0. Version & schema validation
    raw_ver = payload.get("version")
    if raw_ver is not None and str(raw_ver) not in ("1", "2"):
        return LicenseStatus(
            is_valid=False,
            status="UNSUPPORTED_VERSION",
            client_name=payload.get("client_name", "Unknown"),
            license_id=payload.get("license_id", "Unknown"),
            terminal_count=int(payload.get("terminal_count", 1)) if str(payload.get("terminal_count", "1")).isdigit() else 1,
            activation_date=payload.get("activation_date", ""),
            expiry_date=payload.get("expiry_date"),
            edition=payload.get("edition", "UNKNOWN"),
            message=f"Unsupported license schema version: {raw_ver}.",
            remaining_days=0,
            grace_period_active=False,
        )

    if raw_ver in (2, "2"):
        grace_val = payload.get("grace_period_days", 0)
        try:
            grace_int = int(grace_val if grace_val is not None else 0)
            if grace_int < 0 or grace_int > 365:
                raise ValueError()
        except (ValueError, TypeError):
            return LicenseStatus(
                is_valid=False,
                status="MALFORMED_LICENSE",
                client_name=payload.get("client_name", "Unknown"),
                license_id=payload.get("license_id", "Unknown"),
                terminal_count=int(payload.get("terminal_count", 1)) if str(payload.get("terminal_count", "1")).isdigit() else 1,
                activation_date=payload.get("activation_date", ""),
                expiry_date=payload.get("expiry_date"),
                edition=payload.get("edition", "UNKNOWN"),
                message="License contains an invalid or malformed grace_period_days value.",
                remaining_days=0,
                grace_period_active=False,
            )

    # 1. Asymmetric signature check via public key
    if not verify_license_signature(payload, public_key_hex):
        return LicenseStatus(
            is_valid=False,
            status="INVALID_SIGNATURE",
            client_name=payload.get("client_name", "Unknown"),
            license_id=payload.get("license_id", "Unknown"),
            terminal_count=payload.get("terminal_count", 1),
            activation_date=payload.get("activation_date", ""),
            expiry_date=payload.get("expiry_date"),
            edition=payload.get("edition", "UNKNOWN"),
            message="Cryptographic signature verification failed. The license file has been modified or corrupted.",
        )

    # 2. Activation date check
    try:
        act_date = date.fromisoformat(payload["activation_date"])
        if today < act_date:
            return LicenseStatus(
                is_valid=False,
                status="NOT_YET_ACTIVE",
                client_name=payload.get("client_name", ""),
                license_id=payload.get("license_id", ""),
                terminal_count=payload.get("terminal_count", 1),
                activation_date=payload.get("activation_date", ""),
                expiry_date=payload.get("expiry_date"),
                edition=payload.get("edition", ""),
                message=f"License is not yet active. Activation date: {payload['activation_date']}",
            )
    except Exception:
        return LicenseStatus(
            is_valid=False,
            status="INVALID_DATE_FORMAT",
            client_name=payload.get("client_name", ""),
            license_id=payload.get("license_id", ""),
            terminal_count=payload.get("terminal_count", 1),
            activation_date=payload.get("activation_date", ""),
            expiry_date=payload.get("expiry_date"),
            edition=payload.get("edition", ""),
            message="License activation date is invalid.",
        )

    remaining_days: Optional[int] = None
    edition_val = payload.get("edition", "COMMERCIAL").upper()
    is_trial = edition_val in ("TRIAL", "TRIALING", "EVALUATION")

    # 3. Expiry date check (optional)
    if payload.get("expiry_date"):
        try:
            exp_date = date.fromisoformat(payload["expiry_date"])
            diff = (exp_date - today).days
            if diff >= 0:
                remaining_days = diff
            else:
                # Only Version 2 licenses cryptographically sign and enforce grace periods.
                # Legacy Version 1 licenses did not sign grace periods.
                grace_days = int(payload.get("grace_period_days", 0)) if str(payload.get("version", "")) == "2" else 0
                days_overdue = (today - exp_date).days
                if grace_days > 0 and days_overdue <= grace_days:
                    rem_grace = max(0, grace_days - days_overdue)
                    return LicenseStatus(
                        is_valid=True,
                        status="GRACE_PERIOD",
                        client_name=payload.get("client_name", ""),
                        license_id=payload.get("license_id", ""),
                        terminal_count=payload.get("terminal_count", 1),
                        activation_date=payload.get("activation_date", ""),
                        expiry_date=payload.get("expiry_date"),
                        edition=payload.get("edition", "COMMERCIAL"),
                        message=f"License expired on {payload['expiry_date']}. Grace period active ({rem_grace} days remaining). Please renew your subscription.",
                        remaining_days=rem_grace,
                        grace_period_active=True,
                    )
                else:
                    exp_msg = (
                        f"License expired on {payload['expiry_date']}. Trial expired — contact support to renew"
                        if is_trial
                        else f"License expired on {payload['expiry_date']}. Please renew your support subscription."
                    )
                    return LicenseStatus(
                        is_valid=False,
                        status="EXPIRED",
                        client_name=payload.get("client_name", ""),
                        license_id=payload.get("license_id", ""),
                        terminal_count=payload.get("terminal_count", 1),
                        activation_date=payload.get("activation_date", ""),
                        expiry_date=payload.get("expiry_date"),
                        edition=payload.get("edition", ""),
                        message=exp_msg,
                        remaining_days=0,
                        grace_period_active=False,
                    )
        except Exception:
            return LicenseStatus(
                is_valid=False,
                status="INVALID_DATE_FORMAT",
                client_name=payload.get("client_name", ""),
                license_id=payload.get("license_id", ""),
                terminal_count=payload.get("terminal_count", 1),
                activation_date=payload.get("activation_date", ""),
                expiry_date=payload.get("expiry_date"),
                edition=payload.get("edition", ""),
                message="License expiry date format is invalid.",
            )

    status_label = "TRIAL" if is_trial else "ACTIVE"
    if is_trial:
        days_str = f"{remaining_days} days" if remaining_days != 1 else "1 day"
        msg = f"Evaluation trial active (Trial: {days_str} remaining)." if remaining_days is not None else "Evaluation trial active."
    else:
        days_str = f"{remaining_days} days" if remaining_days != 1 else "1 day"
        msg = f"Subscription: {days_str} remaining" if remaining_days is not None else "Subscription: Perpetual license active"

    # All checks passed
    return LicenseStatus(
        is_valid=True,
        status=status_label,
        client_name=payload["client_name"],
        license_id=payload["license_id"],
        terminal_count=int(payload.get("terminal_count", 1)),
        activation_date=payload["activation_date"],
        expiry_date=payload.get("expiry_date"),
        edition=payload.get("edition", "COMMERCIAL"),
        message=msg,
        remaining_days=remaining_days,
        grace_period_active=False,
    )


class LicenseManager:
    """Manages reading, caching, and installing offline license files."""

    def __init__(self, license_path: Path):
        self.license_path = license_path
        self.state_path = license_path.parent / "license_state.json"

    def load_license(self) -> Optional[Dict[str, Any]]:
        """Load license payload from disk if present."""
        if not self.license_path.exists():
            return None
        try:
            raw = self.license_path.read_text(encoding="utf-8")
            return json.loads(raw)
        except Exception as exc:
            logger.warning("Could not parse license file at %s: %s", self.license_path, exc)
            return None

    def save_license(self, payload: Dict[str, Any]) -> None:
        """Atomically persist license file to disk."""
        self.license_path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.license_path.parent,
                prefix="license_tmp_",
                suffix=".json",
                delete=False,
            ) as tf:
                temp_file = Path(tf.name)
                json.dump(payload, tf, indent=2)
                tf.flush()
                os.fsync(tf.fileno())
            os.replace(temp_file, self.license_path)
        except Exception:
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass
            raise
        self._record_verified_date(date.today())

    def _get_last_verified_date(self) -> Optional[date]:
        if not self.state_path.exists():
            return None
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            dt_str = data.get("last_verified_date")
            if dt_str:
                return date.fromisoformat(dt_str)
        except Exception as exc:
            logger.warning("Could not parse license state at %s: %s", self.state_path, exc)
        return None

    def _record_verified_date(self, current_date: date) -> None:
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(
                json.dumps({"last_verified_date": current_date.isoformat()}, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("Could not save license state at %s: %s", self.state_path, exc)

    def get_status(self, current_date: Optional[date] = None) -> LicenseStatus:
        """Inspect and evaluate current active license state, tracking device dates to detect clock tampering."""
        today = current_date or date.today()
        last_verified = self._get_last_verified_date()

        payload = self.load_license()
        status = evaluate_license(
            payload,
            current_date=today,
            last_verified_date=last_verified,
        )

        if status.status != "CLOCK_ANOMALY":
            if last_verified is None or today >= last_verified:
                self._record_verified_date(today)

        return status
