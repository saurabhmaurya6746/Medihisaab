"""Client management endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from licensing_service.api.schemas import (
    ApiEnvelope,
    ClientCreateRequest,
    ClientResponse,
    ClientStatusChangeRequest,
    ClientUpdateRequest,
    LicenseResponse,
    SubscriptionResponse,
)
from licensing_service.db.models import Client, ClientStatus, VendorRole, VendorUser
from licensing_service.db.session import get_db
from licensing_service.security.auth import get_current_vendor_user, require_role
from licensing_service.services.audit import log_audit_event
from licensing_service.services.client_service import (
    create_client,
    get_client,
    search_clients,
    update_client,
)

router = APIRouter(prefix="/clients", tags=["Clients"])


@router.get("", response_model=ApiEnvelope)
def list_clients(
    q: Optional[str] = Query(None, description="Search term"),
    status: Optional[str] = Query(None, description="Client status filter"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: VendorUser = Depends(get_current_vendor_user),
):
    """Search and paginate client accounts."""
    results = search_clients(db, query=q, status=status, limit=limit, offset=offset)
    data = [ClientResponse.model_validate(c) for c in results]
    return ApiEnvelope(data=[d.model_dump() for d in data])


@router.post("", response_model=ApiEnvelope, status_code=status.HTTP_201_CREATED)
def create_new_client(
    req: ClientCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: VendorUser = Depends(require_role(VendorRole.OWNER, VendorRole.ADMIN, VendorRole.SUPPORT)),
):
    """Register a new pharmacy client."""
    client = create_client(db, req.model_dump())
    client_ip = request.client.host if request.client else None

    log_audit_event(
        db=db,
        user_email=user.email,
        action="CREATE_CLIENT",
        entity_type="CLIENT",
        entity_id=str(client.id),
        ip_address=client_ip,
        metadata={"client_code": client.client_code, "business_name": client.business_name},
    )

    data = ClientResponse.model_validate(client)
    return ApiEnvelope(data=data.model_dump(), message="Client registered successfully.")


@router.get("/{client_id}", response_model=ApiEnvelope)
def get_client_profile(
    client_id: int,
    db: Session = Depends(get_db),
    user: VendorUser = Depends(get_current_vendor_user),
):
    """Retrieve full client profile including active subscriptions and licenses."""
    client = get_client(db, client_id)
    if not client:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found.")

    client_data = ClientResponse.model_validate(client).model_dump()
    subs_data = [SubscriptionResponse.model_validate(s).model_dump() for s in client.subscriptions]
    lics_data = [LicenseResponse.model_validate(l).model_dump() for l in client.licenses]

    return ApiEnvelope(
        data={
            "client": client_data,
            "subscriptions": subs_data,
            "licenses": lics_data,
        }
    )


@router.put("/{client_id}", response_model=ApiEnvelope)
def update_client_profile(
    client_id: int,
    req: ClientUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: VendorUser = Depends(require_role(VendorRole.OWNER, VendorRole.ADMIN, VendorRole.SUPPORT)),
):
    """Update existing client contact and business details."""
    client = update_client(db, client_id, req.model_dump(exclude_unset=True))
    if not client:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found.")

    client_ip = request.client.host if request.client else None
    log_audit_event(
        db=db,
        user_email=user.email,
        action="UPDATE_CLIENT",
        entity_type="CLIENT",
        entity_id=str(client_id),
        ip_address=client_ip,
        metadata={"updated_fields": list(req.model_dump(exclude_unset=True).keys())},
    )

    data = ClientResponse.model_validate(client)
    return ApiEnvelope(data=data.model_dump(), message="Client updated successfully.")


@router.post("/{client_id}/status", response_model=ApiEnvelope)
@router.patch("/{client_id}/status", response_model=ApiEnvelope)
def change_client_status(
    client_id: int,
    body: Optional[ClientStatusChangeRequest] = None,
    new_status: Optional[str] = Query(None, description="Target status: ACTIVE, SUSPENDED, CLOSED, TRIAL"),
    reason: Optional[str] = Query(None),
    request: Request = None,
    db: Session = Depends(get_db),
    user: VendorUser = Depends(require_role(VendorRole.OWNER, VendorRole.ADMIN)),
):
    """Transition client operational status."""
    status_to_set = (body.status if body and body.status else new_status)
    if not status_to_set:
        raise HTTPException(status_code=400, detail="Target status must be provided.")
    reason_to_set = (body.reason if body and body.reason else reason)

    client = get_client(db, client_id)
    if not client:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found.")

    old_status = client.status
    client.status = status_to_set.upper()
    if reason_to_set:
        client.notes = (client.notes or "") + f"\n[Status {old_status}->{client.status}]: {reason_to_set}"
    db.commit()
    db.refresh(client)

    client_ip = request.client.host if request and request.client else None
    log_audit_event(
        db=db,
        user_email=user.email,
        action="CHANGE_CLIENT_STATUS",
        entity_type="CLIENT",
        entity_id=str(client_id),
        ip_address=client_ip,
        metadata={"old_status": old_status, "new_status": client.status, "reason": reason_to_set},
    )

    data = ClientResponse.model_validate(client)
    return ApiEnvelope(data=data.model_dump(), message=f"Status changed to {client.status}.")
