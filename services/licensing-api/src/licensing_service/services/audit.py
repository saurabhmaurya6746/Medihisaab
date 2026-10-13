"""Audit logging service for tracking vendor portal events and administrative actions."""

import json
import logging
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from licensing_service.db.models import AuditEvent

logger = logging.getLogger("licensing_service.services.audit")

SENSITIVE_KEYS = {"password", "password_hash", "confirm_password", "token", "secret", "private_key", "secret_key"}


def sanitize_metadata(meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Sanitize metadata by stripping any passwords, secrets, or private keys."""
    if not meta:
        return {}
    sanitized = {}
    for k, v in meta.items():
        if any(sens in k.lower() for sens in SENSITIVE_KEYS):
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, dict):
            sanitized[k] = sanitize_metadata(v)
        else:
            sanitized[k] = v
    return sanitized


def log_audit_event(
    db: Session,
    user_email: str,
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> AuditEvent:
    """Record an immutable audit event in the database."""
    safe_meta = sanitize_metadata(metadata)
    event = AuditEvent(
        user_email=user_email,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        ip_address=ip_address,
        metadata_json=json.dumps(safe_meta) if safe_meta else None,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    logger.info("Audit: [%s] by %s on %s:%s", action, user_email, entity_type, entity_id)
    return event
