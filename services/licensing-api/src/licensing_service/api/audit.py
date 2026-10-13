"""Audit log query endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from licensing_service.api.schemas import ApiEnvelope
from licensing_service.db.models import AuditEvent, VendorRole, VendorUser
from licensing_service.db.session import get_db
from licensing_service.security.auth import require_role

router = APIRouter(prefix="/audit", tags=["Audit Log"])


@router.get("", response_model=ApiEnvelope)
def list_audit_events(
    entity_type: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    user_email: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: VendorUser = Depends(require_role(VendorRole.OWNER, VendorRole.ADMIN)),
):
    """Retrieve immutable audit log events (OWNER and ADMIN only)."""
    q = db.query(AuditEvent)
    if entity_type:
        q = q.filter(AuditEvent.entity_type == entity_type)
    if action:
        q = q.filter(AuditEvent.action == action)
    if user_email:
        q = q.filter(AuditEvent.user_email == user_email)

    events = q.order_by(AuditEvent.id.desc()).offset(offset).limit(limit).all()

    data = [
        {
            "id": e.id,
            "user_email": e.user_email,
            "action": e.action,
            "entity_type": e.entity_type,
            "entity_id": e.entity_id,
            "timestamp": e.timestamp.isoformat(),
            "ip_address": e.ip_address,
            "metadata": e.get_metadata(),
        }
        for e in events
    ]
    return ApiEnvelope(data=data)
