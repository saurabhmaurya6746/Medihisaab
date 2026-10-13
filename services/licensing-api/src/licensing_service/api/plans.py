"""Subscription plans endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from licensing_service.api.schemas import ApiEnvelope, PlanCreateRequest, PlanResponse, PlanUpdateRequest
from licensing_service.db.models import VendorRole, VendorUser
from licensing_service.db.session import get_db
from licensing_service.security.auth import get_current_vendor_user, require_role
from licensing_service.services.audit import log_audit_event
from licensing_service.services.plan_service import (
    create_plan,
    get_plan,
    list_plans,
    update_plan,
)

router = APIRouter(prefix="/plans", tags=["Plans"])


@router.get("", response_model=ApiEnvelope)
def get_plans(
    active_only: bool = True,
    db: Session = Depends(get_db),
    user: VendorUser = Depends(get_current_vendor_user),
):
    """List subscription plans."""
    plans = list_plans(db, active_only=active_only)
    data = [PlanResponse.model_validate(p) for p in plans]
    return ApiEnvelope(data=[d.model_dump() for d in data])


@router.post("", response_model=ApiEnvelope, status_code=status.HTTP_201_CREATED)
def create_new_plan(
    req: PlanCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: VendorUser = Depends(require_role(VendorRole.OWNER, VendorRole.ADMIN)),
):
    """Create a new subscription plan (OWNER and ADMIN only)."""
    plan = create_plan(db, req.model_dump())
    client_ip = request.client.host if request.client else None

    log_audit_event(
        db=db,
        user_email=user.email,
        action="CREATE_PLAN",
        entity_type="PLAN",
        entity_id=str(plan.id),
        ip_address=client_ip,
        metadata={"plan_code": plan.plan_code, "price": plan.price, "terminals": plan.maximum_terminals},
    )

    data = PlanResponse.model_validate(plan)
    return ApiEnvelope(data=data.model_dump(), message="Plan created successfully.")


@router.put("/{plan_id}", response_model=ApiEnvelope)
def update_plan_details(
    plan_id: int,
    req: PlanUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: VendorUser = Depends(require_role(VendorRole.OWNER, VendorRole.ADMIN)),
):
    """Modify subscription plan parameters (OWNER and ADMIN only)."""
    plan = update_plan(db, plan_id, req.model_dump(exclude_unset=True))
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found.")

    client_ip = request.client.host if request.client else None
    log_audit_event(
        db=db,
        user_email=user.email,
        action="UPDATE_PLAN",
        entity_type="PLAN",
        entity_id=str(plan_id),
        ip_address=client_ip,
        metadata={"updated_fields": list(req.model_dump(exclude_unset=True).keys())},
    )

    data = PlanResponse.model_validate(plan)
    return ApiEnvelope(data=data.model_dump(), message="Plan updated successfully.")
