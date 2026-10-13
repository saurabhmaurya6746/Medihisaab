"""System settings API endpoints (configurable trial durations, grace periods, etc.)."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from licensing_service.api.schemas import (
    ApiEnvelope,
    SupportContactsResponse,
    SupportContactsUpdateRequest,
    SystemSettingResponse,
    UpdateTrialDurationRequest,
)
from licensing_service.db.models import VendorRole, VendorUser
from licensing_service.db.session import get_db
from licensing_service.security.auth import get_current_vendor_user, require_role
from licensing_service.services.audit import log_audit_event
from licensing_service.services.setting_service import (
    get_default_grace_days,
    get_default_trial_days,
    get_support_contacts,
    list_settings,
    set_setting,
    set_support_contacts,
)

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("", response_model=ApiEnvelope)
def get_system_settings(
    db: Session = Depends(get_db),
    user: VendorUser = Depends(get_current_vendor_user),
):
    """Retrieve all configurable system settings and support contacts."""
    settings = list_settings(db)
    data = [SystemSettingResponse.model_validate(s).model_dump() for s in settings]
    return ApiEnvelope(
        data={
            "settings": data,
            "default_trial_days": get_default_trial_days(db),
            "default_grace_days": get_default_grace_days(db),
            "support_contacts": get_support_contacts(db),
        }
    )


@router.put("/trial-duration", response_model=ApiEnvelope)
def update_trial_duration_setting(
    req: UpdateTrialDurationRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: VendorUser = Depends(require_role(VendorRole.OWNER, VendorRole.ADMIN)),
):
    """Update system default trial duration and optional grace period days with validation."""
    if req.default_trial_days < 1 or req.default_trial_days > 365:
        raise HTTPException(
            status_code=400,
            detail="Default trial duration must be between 1 and 365 days.",
        )
    if req.default_grace_days is not None and (req.default_grace_days < 0 or req.default_grace_days > 90):
        raise HTTPException(
            status_code=400,
            detail="Grace period must be between 0 and 90 days.",
        )

    s_trial = set_setting(
        db=db,
        key="default_trial_days",
        value=str(req.default_trial_days),
        description="Default trial duration in days for new evaluations",
    )
    res_data = {"default_trial_days": int(s_trial.value)}

    if req.default_grace_days is not None:
        s_grace = set_setting(
            db=db,
            key="default_grace_days",
            value=str(req.default_grace_days),
            description="Default grace period in days before restricted features lock",
        )
        res_data["default_grace_days"] = int(s_grace.value)

    client_ip = request.client.host if request.client else None
    log_audit_event(
        db=db,
        user_email=user.email,
        action="TRIAL_SETTINGS_UPDATED",
        entity_type="SYSTEM_SETTING",
        entity_id="default_trial_days",
        ip_address=client_ip,
        metadata=res_data,
    )

    return ApiEnvelope(
        data=res_data,
        message=f"Default trial duration updated to {req.default_trial_days} days.",
    )


@router.put("/support-contacts", response_model=ApiEnvelope)
def update_support_contact_settings(
    req: SupportContactsUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: VendorUser = Depends(require_role(VendorRole.OWNER, VendorRole.ADMIN)),
):
    """Update vendor support contact details (phone, WhatsApp, support email, notification email)."""
    if req.email and ("@" not in req.email or "." not in req.email):
        raise HTTPException(status_code=400, detail="A valid support email address is required.")
    if req.vendor_notification_email and ("@" not in req.vendor_notification_email or "." not in req.vendor_notification_email):
        raise HTTPException(status_code=400, detail="A valid vendor notification email address is required.")

    contacts = set_support_contacts(
        db=db,
        phone=req.phone,
        whatsapp=req.whatsapp,
        email=req.email,
        vendor_notification_email=req.vendor_notification_email,
    )

    client_ip = request.client.host if request.client else None
    log_audit_event(
        db=db,
        user_email=user.email,
        action="UPDATE_SUPPORT_CONTACT_SETTINGS",
        entity_type="SYSTEM_SETTING",
        entity_id="support_contacts",
        ip_address=client_ip,
        metadata={"updated_contacts": contacts},
    )

    return ApiEnvelope(
        data=contacts,
        message="Support contact details updated successfully.",
    )
