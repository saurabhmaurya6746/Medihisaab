"""Customer order placement, history, and status tracking endpoints."""

import random
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from portal_service.config import settings
from portal_service.db.models import (
    Customer,
    Order,
    OrderItem,
    OrderStatusEnum,
    OrderStatusHistory,
    Product,
)
from portal_service.db.session import get_db
from portal_service.security.dependencies import get_current_customer
from portal_service.schemas import (
    CreateOrderRequest,
    OrderItemDetailResponse,
    OrderResponse,
    OrderStatusHistoryResponse,
)

router = APIRouter(prefix="/customer", tags=["Customer Orders"])


def generate_order_number() -> str:
    """Generate a readable order identifier e.g. ORD-2026-84920."""
    year = datetime.now(timezone.utc).year
    rand_num = random.randint(10000, 99999)
    return f"ORD-{year}-{rand_num}"


def format_order_response(order: Order) -> OrderResponse:
    """Helper to convert Order DB model to OrderResponse schema."""
    items = [
        OrderItemDetailResponse(
            id=item.id,
            product_id=item.product_id,
            product_name=item.product_name,
            generic_name=item.generic_name,
            dosage_form=item.dosage_form,
            pack_size=item.pack_size,
            unit_price_paise=item.unit_price_paise,
            quantity=item.quantity,
            total_paise=item.total_paise,
            is_prescription_required=item.is_prescription_required,
        )
        for item in order.items
    ]

    history = [
        OrderStatusHistoryResponse(
            id=h.id,
            order_id=h.order_id,
            from_status=h.from_status,
            to_status=h.to_status,
            changed_by_type=h.changed_by_type,
            changed_by_name=h.changed_by_name,
            notes=h.notes,
            created_at=h.created_at,
        )
        for h in (order.status_history or [])
    ]

    return OrderResponse(
        id=order.id,
        order_number=order.order_number,
        customer_id=order.customer_id,
        customer_name=order.customer_name,
        customer_email=order.customer_email,
        customer_phone=order.customer_phone,
        fulfillment_type=order.fulfillment_type,
        delivery_address=order.delivery_address,
        payment_method=order.payment_method,
        status=order.status,
        subtotal_paise=order.subtotal_paise,
        delivery_fee_paise=order.delivery_fee_paise,
        total_paise=order.total_paise,
        has_prescription_items=order.has_prescription_items,
        pharmacist_notes=order.pharmacist_notes,
        rejection_reason=order.rejection_reason,
        created_at=order.created_at,
        updated_at=order.updated_at,
        items=items,
        status_history=history,
    )


@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def place_order(
    payload: CreateOrderRequest,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    """Place a new online order for in-store pickup or local delivery."""
    if not payload.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order must contain at least one item.",
        )

    # 1. Fetch & validate products
    product_ids = [item.product_id for item in payload.items]
    products = db.query(Product).filter(Product.id.in_(product_ids)).all()
    products_by_id = {p.id: p for p in products}

    for item in payload.items:
        prod = products_by_id.get(item.product_id)
        if not prod:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product ID '{item.product_id}' was not found.",
            )
        if not prod.is_available or prod.stock_status == "OUT_OF_STOCK":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product '{prod.name}' is currently out of stock.",
            )

    # 2. Fulfillment and address validation
    delivery_addr = ""
    if payload.fulfillment_type == "DELIVERY":
        delivery_addr = (payload.delivery_address or current_customer.delivery_address or "").strip()
        if not delivery_addr:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Delivery address is required for home delivery orders.",
            )
    else:
        delivery_addr = "In-Store Pickup"

    customer_phone = (payload.customer_phone or current_customer.phone or "").strip()
    if not customer_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contact phone number is required to confirm your order.",
        )

    # 3. Calculate financial totals and detect prescription items
    subtotal_paise = 0
    has_prescription = False
    order_items_to_create = []

    for item_input in payload.items:
        p = products_by_id[item_input.product_id]
        line_total = p.selling_price_paise * item_input.quantity
        subtotal_paise += line_total

        if p.is_prescription_required:
            has_prescription = True

        order_items_to_create.append(
            {
                "product_id": p.id,
                "product_name": p.name,
                "generic_name": p.generic_name,
                "dosage_form": p.dosage_form,
                "pack_size": p.pack_size,
                "unit_price_paise": p.selling_price_paise,
                "quantity": item_input.quantity,
                "total_paise": line_total,
                "is_prescription_required": p.is_prescription_required,
            }
        )

    # Calculate delivery fee
    delivery_fee_paise = 0
    if payload.fulfillment_type == "DELIVERY":
        if subtotal_paise < settings.FREE_DELIVERY_THRESHOLD_PAISE:
            delivery_fee_paise = settings.DELIVERY_FEE_PAISE
        else:
            delivery_fee_paise = 0

    total_paise = subtotal_paise + delivery_fee_paise

    # 4. Determine initial status
    # Prescription items MUST enter PHARMACIST_REVIEW.
    # Non-Rx items enter PENDING_CONFIRMATION so staff can confirm physical stock before dispatch.
    if has_prescription:
        initial_status = OrderStatusEnum.PHARMACIST_REVIEW.value
        status_note = "Order contains prescription items. Awaiting registered pharmacist verification."
    else:
        initial_status = OrderStatusEnum.PENDING_CONFIRMATION.value
        status_note = "Order placed online. Awaiting pharmacy physical stock confirmation."

    # 5. Persist order
    order = Order(
        order_number=generate_order_number(),
        customer_id=current_customer.id,
        customer_name=current_customer.full_name,
        customer_email=current_customer.email,
        customer_phone=customer_phone,
        fulfillment_type=payload.fulfillment_type,
        delivery_address=delivery_addr,
        payment_method=payload.payment_method,
        status=initial_status,
        subtotal_paise=subtotal_paise,
        delivery_fee_paise=delivery_fee_paise,
        total_paise=total_paise,
        has_prescription_items=has_prescription,
        pharmacist_notes="",
        rejection_reason="",
    )
    db.add(order)
    db.flush()

    # Persist line items
    for item_data in order_items_to_create:
        oi = OrderItem(order_id=order.id, **item_data)
        db.add(oi)

    # Persist status history
    history_entry = OrderStatusHistory(
        order_id=order.id,
        from_status=None,
        to_status=initial_status,
        changed_by_type="CUSTOMER",
        changed_by_name=current_customer.full_name,
        notes=status_note,
    )
    db.add(history_entry)
    db.commit()
    db.refresh(order)

    return format_order_response(order)


@router.get("/orders", response_model=List[OrderResponse])
def list_my_orders(
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    """List all orders belonging to the authenticated customer."""
    orders = (
        db.query(Order)
        .filter(Order.customer_id == current_customer.id)
        .order_by(Order.created_at.desc())
        .all()
    )
    return [format_order_response(o) for o in orders]


@router.get("/orders/{order_id}", response_model=OrderResponse)
def get_my_order_details(
    order_id: str,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    """Retrieve details for a specific order (customer-isolated)."""
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.customer_id == current_customer.id)
        .first()
    )
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found or access denied.",
        )
    return format_order_response(order)


@router.post("/orders/{order_id}/cancel", response_model=OrderResponse)
def cancel_my_order(
    order_id: str,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    """Allow customer to cancel an order if it is still pending confirmation or review."""
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.customer_id == current_customer.id)
        .first()
    )
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found or access denied.",
        )

    allowed_cancel_statuses = [
        OrderStatusEnum.PENDING_CONFIRMATION.value,
        OrderStatusEnum.PHARMACIST_REVIEW.value,
    ]
    if order.status not in allowed_cancel_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel order in '{order.status}' status. Please call the pharmacy directly.",
        )

    prev_status = order.status
    order.status = OrderStatusEnum.CANCELLED.value
    order.rejection_reason = "Cancelled by customer."

    history = OrderStatusHistory(
        order_id=order.id,
        from_status=prev_status,
        to_status=OrderStatusEnum.CANCELLED.value,
        changed_by_type="CUSTOMER",
        changed_by_name=current_customer.full_name,
        notes="Order cancelled by customer before store fulfillment.",
    )
    db.add(history)
    db.commit()
    db.refresh(order)

    return format_order_response(order)
