"""Staff audit log inquiry endpoint."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from portal_service.db.models import PortalAuditLog, PortalStaffUser, StaffRole
from portal_service.db.session import get_db
from portal_service.security.dependencies import require_roles
from portal_service.schemas import StaffAuditLogResponse

router = APIRouter(prefix="/staff/audit-logs", tags=["Staff Audit Logs"])


@router.get("", response_model=List[StaffAuditLogResponse])
def get_audit_logs(
    action: Optional[str] = Query(None, description="Filter by action code"),
    staff_email: Optional[str] = Query(None, description="Filter by staff email"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_staff: PortalStaffUser = Depends(require_roles([StaffRole.ADMIN.value, StaffRole.PHARMACIST.value])),
    db: Session = Depends(get_db),
):
    """Retrieve system audit logs for administrative inspections."""
    query = db.query(PortalAuditLog)

    if action:
        query = query.filter(PortalAuditLog.action == action)

    if staff_email:
        query = query.filter(PortalAuditLog.staff_email.ilike(f"%{staff_email.strip()}%"))

    logs = query.order_by(PortalAuditLog.created_at.desc()).offset(offset).limit(limit).all()

    return [
        StaffAuditLogResponse(
            id=log.id,
            staff_user_id=log.staff_user_id,
            staff_email=log.staff_email,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            details_json=log.details_json,
            created_at=log.created_at,
        )
        for log in logs
    ]
