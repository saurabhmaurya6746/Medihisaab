"""Staff catalog and category administration endpoints."""

import json
import re
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from portal_service.db.models import (
    Category,
    PortalAuditLog,
    PortalStaffUser,
    Product,
    StaffRole,
)
from portal_service.db.session import get_db
from portal_service.security.dependencies import get_current_staff, require_roles
from portal_service.schemas import (
    CategoryCreateUpdateRequest,
    CategoryResponse,
    ProductCreateUpdateRequest,
    ProductResponse,
)

router = APIRouter(prefix="/staff", tags=["Staff Catalog"])


def slugify(text: str) -> str:
    """Convert text into a URL slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[-\s]+", "-", text)


# ==================== Product Management ====================


@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreateUpdateRequest,
    current_staff: PortalStaffUser = Depends(require_roles([StaffRole.ADMIN.value, StaffRole.PHARMACIST.value])),
    db: Session = Depends(get_db),
):
    """Create a new catalog product (Admin or Pharmacist)."""
    category = db.query(Category).filter(Category.id == payload.category_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category ID '{payload.category_id}' does not exist.",
        )

    base_slug = slugify(payload.slug or payload.name)
    slug = base_slug
    counter = 1
    while db.query(Product).filter(Product.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    product = Product(
        category_id=payload.category_id,
        name=payload.name.strip(),
        slug=slug,
        generic_name=(payload.generic_name or "").strip(),
        dosage_form=payload.dosage_form or "Tablet",
        pack_size=payload.pack_size or "10 Tablets",
        mrp_paise=payload.mrp_paise,
        selling_price_paise=payload.selling_price_paise,
        is_prescription_required=payload.is_prescription_required,
        is_available=payload.is_available,
        stock_status=payload.stock_status or "IN_STOCK",
        image_url=(payload.image_url or "").strip(),
        description=(payload.description or "").strip(),
        usage_instructions=(payload.usage_instructions or "").strip(),
        side_effects=(payload.side_effects or "").strip(),
    )
    db.add(product)
    db.flush()

    audit = PortalAuditLog(
        staff_user_id=current_staff.id,
        staff_email=current_staff.email,
        action="PRODUCT_CREATED",
        entity_type="PRODUCT",
        entity_id=product.id,
        details_json=json.dumps(
            {
                "name": product.name,
                "price": product.selling_price_paise,
                "is_rx": product.is_prescription_required,
            }
        ),
    )
    db.add(audit)
    db.commit()
    db.refresh(product)

    return ProductResponse(
        id=product.id,
        category_id=product.category_id,
        category_name=product.category.name if product.category else "",
        category_slug=product.category.slug if product.category else "",
        name=product.name,
        slug=product.slug,
        generic_name=product.generic_name,
        dosage_form=product.dosage_form,
        pack_size=product.pack_size,
        mrp_paise=product.mrp_paise,
        selling_price_paise=product.selling_price_paise,
        is_prescription_required=product.is_prescription_required,
        is_available=product.is_available,
        stock_status=product.stock_status,
        image_url=product.image_url,
        description=product.description,
        usage_instructions=product.usage_instructions,
        side_effects=product.side_effects,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


@router.put("/products/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: str,
    payload: ProductCreateUpdateRequest,
    current_staff: PortalStaffUser = Depends(require_roles([StaffRole.ADMIN.value, StaffRole.PHARMACIST.value])),
    db: Session = Depends(get_db),
):
    """Update existing product details, price, or prescription requirement."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product ID '{product_id}' was not found.",
        )

    product.category_id = payload.category_id
    product.name = payload.name.strip()
    product.generic_name = (payload.generic_name or "").strip()
    product.dosage_form = payload.dosage_form or product.dosage_form
    product.pack_size = payload.pack_size or product.pack_size
    product.mrp_paise = payload.mrp_paise
    product.selling_price_paise = payload.selling_price_paise
    product.is_prescription_required = payload.is_prescription_required
    product.is_available = payload.is_available
    product.stock_status = payload.stock_status or product.stock_status
    if payload.image_url is not None:
        product.image_url = payload.image_url.strip()
    if payload.description is not None:
        product.description = payload.description.strip()
    if payload.usage_instructions is not None:
        product.usage_instructions = payload.usage_instructions.strip()
    if payload.side_effects is not None:
        product.side_effects = payload.side_effects.strip()

    audit = PortalAuditLog(
        staff_user_id=current_staff.id,
        staff_email=current_staff.email,
        action="PRODUCT_UPDATED",
        entity_type="PRODUCT",
        entity_id=product.id,
        details_json=json.dumps(
            {
                "name": product.name,
                "price": product.selling_price_paise,
                "stock_status": product.stock_status,
                "is_available": product.is_available,
            }
        ),
    )
    db.add(audit)
    db.commit()
    db.refresh(product)

    return ProductResponse(
        id=product.id,
        category_id=product.category_id,
        category_name=product.category.name if product.category else "",
        category_slug=product.category.slug if product.category else "",
        name=product.name,
        slug=product.slug,
        generic_name=product.generic_name,
        dosage_form=product.dosage_form,
        pack_size=product.pack_size,
        mrp_paise=product.mrp_paise,
        selling_price_paise=product.selling_price_paise,
        is_prescription_required=product.is_prescription_required,
        is_available=product.is_available,
        stock_status=product.stock_status,
        image_url=product.image_url,
        description=product.description,
        usage_instructions=product.usage_instructions,
        side_effects=product.side_effects,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


@router.patch("/products/{product_id}/availability", response_model=ProductResponse)
def toggle_product_availability(
    product_id: str,
    is_available: Optional[bool] = Query(None),
    stock_status: Optional[str] = Query(None),
    current_staff: PortalStaffUser = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    """Quick toggle product listing status or stock status (all staff roles)."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product ID '{product_id}' was not found.",
        )

    if is_available is not None:
        product.is_available = is_available
    if stock_status is not None:
        product.stock_status = stock_status

    audit = PortalAuditLog(
        staff_user_id=current_staff.id,
        staff_email=current_staff.email,
        action="PRODUCT_AVAILABILITY_CHANGED",
        entity_type="PRODUCT",
        entity_id=product.id,
        details_json=json.dumps(
            {
                "is_available": product.is_available,
                "stock_status": product.stock_status,
            }
        ),
    )
    db.add(audit)
    db.commit()
    db.refresh(product)

    return ProductResponse(
        id=product.id,
        category_id=product.category_id,
        category_name=product.category.name if product.category else "",
        category_slug=product.category.slug if product.category else "",
        name=product.name,
        slug=product.slug,
        generic_name=product.generic_name,
        dosage_form=product.dosage_form,
        pack_size=product.pack_size,
        mrp_paise=product.mrp_paise,
        selling_price_paise=product.selling_price_paise,
        is_prescription_required=product.is_prescription_required,
        is_available=product.is_available,
        stock_status=product.stock_status,
        image_url=product.image_url,
        description=product.description,
        usage_instructions=product.usage_instructions,
        side_effects=product.side_effects,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


# ==================== Category Management ====================


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreateUpdateRequest,
    current_staff: PortalStaffUser = Depends(require_roles([StaffRole.ADMIN.value])),
    db: Session = Depends(get_db),
):
    """Create a new category (Admin only)."""
    base_slug = slugify(payload.slug or payload.name)
    existing = db.query(Category).filter(Category.slug == base_slug).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Category with slug '{base_slug}' already exists.",
        )

    cat = Category(
        name=payload.name.strip(),
        slug=base_slug,
        description=(payload.description or "").strip(),
        display_order=payload.display_order or 0,
        is_active=payload.is_active if payload.is_active is not None else True,
    )
    db.add(cat)
    db.flush()

    audit = PortalAuditLog(
        staff_user_id=current_staff.id,
        staff_email=current_staff.email,
        action="CATEGORY_CREATED",
        entity_type="CATEGORY",
        entity_id=cat.id,
        details_json=json.dumps({"name": cat.name, "slug": cat.slug}),
    )
    db.add(audit)
    db.commit()
    db.refresh(cat)

    return CategoryResponse(
        id=cat.id,
        name=cat.name,
        slug=cat.slug,
        description=cat.description,
        display_order=cat.display_order,
        is_active=cat.is_active,
        product_count=0,
    )
