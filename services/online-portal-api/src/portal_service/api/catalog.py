"""Public catalog router for customer and guest browsing."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from portal_service.db.models import Category, Product
from portal_service.db.session import get_db
from portal_service.schemas import CategoryResponse, ProductListResponse, ProductResponse

router = APIRouter(prefix="/catalog", tags=["Catalog"])


@router.get("/categories", response_model=List[CategoryResponse])
def list_categories(db: Session = Depends(get_db)):
    """List all active product categories with product counts."""
    categories = (
        db.query(
            Category,
            func.count(Product.id).label("product_count"),
        )
        .outerjoin(Product, (Product.category_id == Category.id) & (Product.is_available == True))
        .filter(Category.is_active == True)
        .group_by(Category.id)
        .order_by(Category.display_order.asc(), Category.name.asc())
        .all()
    )

    result = []
    for cat, p_count in categories:
        result.append(
            CategoryResponse(
                id=cat.id,
                name=cat.name,
                slug=cat.slug,
                description=cat.description,
                display_order=cat.display_order,
                is_active=cat.is_active,
                product_count=p_count,
            )
        )
    return result


@router.get("/products", response_model=ProductListResponse)
def list_products(
    category_slug: Optional[str] = Query(None, description="Filter by category slug"),
    search: Optional[str] = Query(None, description="Search by name or generic salt"),
    prescription_only: Optional[bool] = Query(None, description="Filter by prescription requirement"),
    in_stock_only: Optional[bool] = Query(False, description="Filter only in-stock items"),
    sort: Optional[str] = Query("name_asc", description="name_asc, price_asc, price_desc"),
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Browse and search catalog products with filters and pagination."""
    query = db.query(Product).join(Category).filter(Product.is_available == True, Category.is_active == True)

    if category_slug:
        query = query.filter(Category.slug == category_slug)

    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Product.name.ilike(search_term),
                Product.generic_name.ilike(search_term),
                Product.description.ilike(search_term),
            )
        )

    if prescription_only is not None:
        query = query.filter(Product.is_prescription_required == prescription_only)

    if in_stock_only:
        query = query.filter(Product.stock_status.in_(["IN_STOCK", "LOW_STOCK"]))

    # Sorting
    if sort == "price_asc":
        query = query.order_by(Product.selling_price_paise.asc())
    elif sort == "price_desc":
        query = query.order_by(Product.selling_price_paise.desc())
    else:
        query = query.order_by(Product.name.asc())

    total = query.count()
    offset = (page - 1) * limit
    products = query.offset(offset).limit(limit).all()

    items = [
        ProductResponse(
            id=p.id,
            category_id=p.category_id,
            category_name=p.category.name if p.category else "",
            category_slug=p.category.slug if p.category else "",
            name=p.name,
            slug=p.slug,
            generic_name=p.generic_name,
            dosage_form=p.dosage_form,
            pack_size=p.pack_size,
            mrp_paise=p.mrp_paise,
            selling_price_paise=p.selling_price_paise,
            is_prescription_required=p.is_prescription_required,
            is_available=p.is_available,
            stock_status=p.stock_status,
            image_url=p.image_url,
            description=p.description,
            usage_instructions=p.usage_instructions,
            side_effects=p.side_effects,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in products
    ]

    return ProductListResponse(items=items, total=total, page=page, limit=limit)


@router.get("/products/{slug}", response_model=ProductResponse)
def get_product_by_slug(slug: str, db: Session = Depends(get_db)):
    """Retrieve full details for an individual product by its URL slug."""
    product = (
        db.query(Product)
        .join(Category)
        .filter(Product.slug == slug, Product.is_available == True, Category.is_active == True)
        .first()
    )
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product '{slug}' not found or currently unavailable.",
        )

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
