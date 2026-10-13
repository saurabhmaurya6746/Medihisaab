"""Master Catalog REST APIs for Manufacturers, Medicines, Suppliers, and Customers."""

from datetime import datetime, timezone
import math
import re
import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from .dependencies import get_db, require_role, require_write_role
from .schemas import (
    CreateCustomerRequest,
    CreateManufacturerRequest,
    CreateMedicineRequest,
    CreateSupplierRequest,
    CustomerResponse,
    ManufacturerResponse,
    MedicineResponse,
    PaginatedData,
    SuccessResponse,
    SupplierPayableSummaryResponse,
    SupplierResponse,
    UpdateCustomerRequest,
    UpdateManufacturerRequest,
    UpdateMedicineRequest,
    UpdateSupplierRequest,
)
from ..security.roles import UserRole

router = APIRouter(prefix="/api/v1/masters", tags=["Master Catalog"])

# Permissions:
# Read operations: ADMIN, PHARMACIST, CASHIER
# Modification operations (Create, Update, Deactivate): ADMIN, PHARMACIST with active license
read_guard = Depends(require_role(UserRole.ADMIN, UserRole.PHARMACIST, UserRole.CASHIER))
write_guard = Depends(require_write_role(UserRole.ADMIN, UserRole.PHARMACIST))


def _clean_fts_query(query: str) -> str:
    """Sanitize user input string into safe FTS5 prefix match tokens."""
    # Remove any special SQLite FTS syntax characters
    cleaned = re.sub(r"[^\w\s]", " ", query).strip()
    tokens = [f"{token}*" for token in cleaned.split() if token]
    return " ".join(tokens)


# ==============================================================================
# 1. MANUFACTURERS ENDPOINTS
# ==============================================================================

@router.get("/manufacturers", response_model=SuccessResponse[PaginatedData[ManufacturerResponse]], dependencies=[read_guard])
def list_manufacturers(
    query: Optional[str] = Query(None, description="Search by manufacturer name or short code"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: sqlite3.Connection = Depends(get_db),
):
    """List and search pharmaceutical manufacturers with pagination."""
    conditions = []
    params = []

    if query and query.strip():
        term = f"%{query.strip()}%"
        conditions.append("(name LIKE ? OR short_code LIKE ?)")
        params.extend([term, term])

    if is_active is not None:
        conditions.append("is_active = ?")
        params.append(1 if is_active else 0)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    cursor = db.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM manufacturers {where_clause};", params)
    total = cursor.fetchone()[0]

    offset = (page - 1) * page_size
    query_sql = f"""
        SELECT id, name, short_code, is_active, created_at, updated_at
        FROM manufacturers
        {where_clause}
        ORDER BY name ASC
        LIMIT ? OFFSET ?;
    """
    cursor.execute(query_sql, params + [page_size, offset])
    rows = cursor.fetchall()
    cursor.close()

    items = [
        ManufacturerResponse(
            id=row["id"],
            name=row["name"],
            short_code=row["short_code"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]

    total_pages = math.ceil(total / page_size) if total > 0 else 1
    return SuccessResponse(
        data=PaginatedData(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)
    )


@router.get("/manufacturers/{id}", response_model=SuccessResponse[ManufacturerResponse], dependencies=[read_guard])
def get_manufacturer(id: int, db: sqlite3.Connection = Depends(get_db)):
    """Fetch single manufacturer by unique ID."""
    cursor = db.cursor()
    cursor.execute("SELECT id, name, short_code, is_active, created_at, updated_at FROM manufacturers WHERE id = ?;", (id,))
    row = cursor.fetchone()
    cursor.close()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Manufacturer #{id} not found.")

    return SuccessResponse(
        data=ManufacturerResponse(
            id=row["id"],
            name=row["name"],
            short_code=row["short_code"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
    )


@router.post("/manufacturers", response_model=SuccessResponse[ManufacturerResponse], status_code=status.HTTP_201_CREATED, dependencies=[write_guard])
def create_manufacturer(payload: CreateManufacturerRequest, db: sqlite3.Connection = Depends(get_db)):
    """Create a new pharmaceutical manufacturer."""
    clean_name = payload.name.strip()
    clean_code = payload.short_code.strip() if payload.short_code else None

    cursor = db.cursor()
    # Check duplicate name
    cursor.execute("SELECT id FROM manufacturers WHERE LOWER(name) = LOWER(?);", (clean_name,))
    if cursor.fetchone():
        cursor.close()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Manufacturer '{clean_name}' already exists.")

    # Check duplicate short code
    if clean_code:
        cursor.execute("SELECT id FROM manufacturers WHERE LOWER(short_code) = LOWER(?);", (clean_code,))
        if cursor.fetchone():
            cursor.close()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Manufacturer short code '{clean_code}' already exists.")

    now_str = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        "INSERT INTO manufacturers (name, short_code, is_active, created_at, updated_at) VALUES (?, ?, 1, ?, ?);",
        (clean_name, clean_code, now_str, now_str),
    )
    new_id = cursor.lastrowid
    cursor.close()

    return SuccessResponse(
        data=ManufacturerResponse(
            id=new_id,
            name=clean_name,
            short_code=clean_code,
            is_active=True,
            created_at=now_str,
            updated_at=now_str,
        ),
        message="Manufacturer created successfully.",
    )


@router.put("/manufacturers/{id}", response_model=SuccessResponse[ManufacturerResponse], dependencies=[write_guard])
def update_manufacturer(id: int, payload: UpdateManufacturerRequest, db: sqlite3.Connection = Depends(get_db)):
    """Update manufacturer attributes."""
    cursor = db.cursor()
    cursor.execute("SELECT id, name, short_code, is_active, created_at, updated_at FROM manufacturers WHERE id = ?;", (id,))
    existing = cursor.fetchone()
    if not existing:
        cursor.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Manufacturer #{id} not found.")

    new_name = payload.name.strip() if payload.name is not None else existing["name"]
    new_code = payload.short_code.strip() if payload.short_code is not None else existing["short_code"]
    new_active = payload.is_active if payload.is_active is not None else bool(existing["is_active"])

    # Check duplicate name if changed
    if new_name != existing["name"]:
        cursor.execute("SELECT id FROM manufacturers WHERE LOWER(name) = LOWER(?) AND id != ?;", (new_name, id))
        if cursor.fetchone():
            cursor.close()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Manufacturer name '{new_name}' already taken.")

    # Check duplicate code if changed
    if new_code and new_code != existing["short_code"]:
        cursor.execute("SELECT id FROM manufacturers WHERE LOWER(short_code) = LOWER(?) AND id != ?;", (new_code, id))
        if cursor.fetchone():
            cursor.close()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Short code '{new_code}' already taken.")

    now_str = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        "UPDATE manufacturers SET name = ?, short_code = ?, is_active = ?, updated_at = ? WHERE id = ?;",
        (new_name, new_code, 1 if new_active else 0, now_str, id),
    )
    cursor.close()

    return SuccessResponse(
        data=ManufacturerResponse(
            id=id,
            name=new_name,
            short_code=new_code,
            is_active=new_active,
            created_at=existing["created_at"],
            updated_at=now_str,
        ),
        message="Manufacturer updated successfully.",
    )


@router.delete("/manufacturers/{id}", response_model=SuccessResponse[ManufacturerResponse], dependencies=[write_guard])
def deactivate_manufacturer(id: int, db: sqlite3.Connection = Depends(get_db)):
    """Soft-deactivate a manufacturer without deleting historical records."""
    cursor = db.cursor()
    cursor.execute("SELECT id, name, short_code, is_active, created_at, updated_at FROM manufacturers WHERE id = ?;", (id,))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Manufacturer #{id} not found.")

    now_str = datetime.now(timezone.utc).isoformat()
    cursor.execute("UPDATE manufacturers SET is_active = 0, updated_at = ? WHERE id = ?;", (now_str, id))
    cursor.close()

    return SuccessResponse(
        data=ManufacturerResponse(
            id=row["id"],
            name=row["name"],
            short_code=row["short_code"],
            is_active=False,
            created_at=row["created_at"],
            updated_at=now_str,
        ),
        message="Manufacturer deactivated successfully.",
    )


# ==============================================================================
# 2. MEDICINES ENDPOINTS
# ==============================================================================

@router.get("/medicines", response_model=SuccessResponse[PaginatedData[MedicineResponse]], dependencies=[read_guard])
def list_medicines(
    query: Optional[str] = Query(None, description="Search by brand name, salt, medicine code, or barcode"),
    dosage_form: Optional[str] = Query(None, description="Filter by dosage form"),
    is_schedule_h1: Optional[bool] = Query(None, description="Filter restricted Schedule H1 drugs"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    manufacturer_id: Optional[int] = Query(None, description="Filter by manufacturer ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: sqlite3.Connection = Depends(get_db),
):
    """Search and list medicines with FTS5 search and regulatory filters."""
    conditions = []
    params = []

    # Use FTS5 virtual table if text query provided
    is_fts_search = False
    fts_clean = ""
    if query and query.strip():
        fts_clean = _clean_fts_query(query)
        if fts_clean:
            is_fts_search = True

    if dosage_form and dosage_form.strip():
        conditions.append("m.dosage_form = ?")
        params.append(dosage_form.strip().upper())

    if is_schedule_h1 is not None:
        conditions.append("m.is_schedule_h1 = ?")
        params.append(1 if is_schedule_h1 else 0)

    if is_active is not None:
        conditions.append("m.is_active = ?")
        params.append(1 if is_active else 0)

    if manufacturer_id is not None:
        conditions.append("m.manufacturer_id = ?")
        params.append(manufacturer_id)

    cursor = db.cursor()

    if is_fts_search:
        # FTS5 search joining medicines and manufacturers
        base_where = f"AND {' AND '.join(conditions)}" if conditions else ""
        count_sql = f"""
            SELECT COUNT(DISTINCT m.id)
            FROM fts_medicines fts
            JOIN medicines m ON m.id = fts.rowid
            LEFT JOIN manufacturers mf ON mf.id = m.manufacturer_id
            WHERE fts_medicines MATCH ? {base_where};
        """
        cursor.execute(count_sql, [fts_clean] + params)
        total = cursor.fetchone()[0]

        offset = (page - 1) * page_size
        select_sql = f"""
            SELECT m.*, mf.name AS manufacturer_name
            FROM fts_medicines fts
            JOIN medicines m ON m.id = fts.rowid
            LEFT JOIN manufacturers mf ON mf.id = m.manufacturer_id
            WHERE fts_medicines MATCH ? {base_where}
            ORDER BY m.brand_name ASC
            LIMIT ? OFFSET ?;
        """
        cursor.execute(select_sql, [fts_clean] + params + [page_size, offset])
        rows = cursor.fetchall()
    else:
        # Standard filter without text query
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        count_sql = f"SELECT COUNT(*) FROM medicines m {where_clause};"
        cursor.execute(count_sql, params)
        total = cursor.fetchone()[0]

        offset = (page - 1) * page_size
        select_sql = f"""
            SELECT m.*, mf.name AS manufacturer_name
            FROM medicines m
            LEFT JOIN manufacturers mf ON mf.id = m.manufacturer_id
            {where_clause}
            ORDER BY m.brand_name ASC
            LIMIT ? OFFSET ?;
        """
        cursor.execute(select_sql, params + [page_size, offset])
        rows = cursor.fetchall()

    cursor.close()

    items = [
        MedicineResponse(
            id=row["id"],
            medicine_code=row["medicine_code"],
            brand_name=row["brand_name"],
            generic_salt=row["generic_salt"],
            dosage_form=row["dosage_form"],
            strength=row["strength"],
            pack_size=row["pack_size"],
            manufacturer_id=row["manufacturer_id"],
            manufacturer_name=row["manufacturer_name"],
            hsn_code=row["hsn_code"],
            gst_rate=float(row["gst_rate"]),
            is_schedule_h1=bool(row["is_schedule_h1"]),
            is_schedule_h=bool(row["is_schedule_h"]),
            is_narcotic=bool(row["is_narcotic"]),
            min_stock_units=row["min_stock_units"],
            rack_location=row["rack_location"],
            barcode=row["barcode"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]

    total_pages = math.ceil(total / page_size) if total > 0 else 1
    return SuccessResponse(
        data=PaginatedData(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)
    )


@router.get("/medicines/{id}", response_model=SuccessResponse[MedicineResponse], dependencies=[read_guard])
def get_medicine(id: int, db: sqlite3.Connection = Depends(get_db)):
    """Fetch single medicine by ID with manufacturer details."""
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT m.*, mf.name AS manufacturer_name
        FROM medicines m
        LEFT JOIN manufacturers mf ON mf.id = m.manufacturer_id
        WHERE m.id = ?;
        """,
        (id,),
    )
    row = cursor.fetchone()
    cursor.close()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Medicine #{id} not found.")

    return SuccessResponse(
        data=MedicineResponse(
            id=row["id"],
            medicine_code=row["medicine_code"],
            brand_name=row["brand_name"],
            generic_salt=row["generic_salt"],
            dosage_form=row["dosage_form"],
            strength=row["strength"],
            pack_size=row["pack_size"],
            manufacturer_id=row["manufacturer_id"],
            manufacturer_name=row["manufacturer_name"],
            hsn_code=row["hsn_code"],
            gst_rate=float(row["gst_rate"]),
            is_schedule_h1=bool(row["is_schedule_h1"]),
            is_schedule_h=bool(row["is_schedule_h"]),
            is_narcotic=bool(row["is_narcotic"]),
            min_stock_units=row["min_stock_units"],
            rack_location=row["rack_location"],
            barcode=row["barcode"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
    )


@router.post("/medicines", response_model=SuccessResponse[MedicineResponse], status_code=status.HTTP_201_CREATED, dependencies=[write_guard])
def create_medicine(payload: CreateMedicineRequest, db: sqlite3.Connection = Depends(get_db)):
    """Create a new medicine in the master catalog."""
    cursor = db.cursor()

    # 1. Validate manufacturer if provided
    if payload.manufacturer_id is not None:
        cursor.execute("SELECT id FROM manufacturers WHERE id = ?;", (payload.manufacturer_id,))
        if not cursor.fetchone():
            cursor.close()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Manufacturer #{payload.manufacturer_id} does not exist.")

    # 2. Check unique medicine code
    clean_code = payload.medicine_code.strip() if payload.medicine_code else None
    if clean_code:
        cursor.execute("SELECT id FROM medicines WHERE LOWER(medicine_code) = LOWER(?);", (clean_code,))
        if cursor.fetchone():
            cursor.close()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Medicine code '{clean_code}' is already assigned.")

    # 3. Check unique barcode
    clean_barcode = payload.barcode.strip() if payload.barcode else None
    if clean_barcode:
        cursor.execute("SELECT id FROM medicines WHERE barcode = ?;", (clean_barcode,))
        if cursor.fetchone():
            cursor.close()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Barcode '{clean_barcode}' is already assigned.")

    now_str = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        """
        INSERT INTO medicines (
            medicine_code, brand_name, generic_salt, dosage_form, strength, pack_size,
            manufacturer_id, hsn_code, gst_rate, is_schedule_h1, is_schedule_h, is_narcotic,
            min_stock_units, rack_location, barcode, is_active, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?);
        """,
        (
            clean_code,
            payload.brand_name.strip(),
            payload.generic_salt.strip(),
            payload.dosage_form,
            payload.strength.strip() if payload.strength else None,
            payload.pack_size,
            payload.manufacturer_id,
            payload.hsn_code,
            payload.gst_rate,
            1 if payload.is_schedule_h1 else 0,
            1 if payload.is_schedule_h else 0,
            1 if payload.is_narcotic else 0,
            payload.min_stock_units,
            payload.rack_location.strip() if payload.rack_location else None,
            clean_barcode,
            now_str,
            now_str,
        ),
    )
    new_id = cursor.lastrowid
    cursor.close()

    # Retrieve created record with joined manufacturer name
    return get_medicine(new_id, db)


@router.put("/medicines/{id}", response_model=SuccessResponse[MedicineResponse], dependencies=[write_guard])
def update_medicine(id: int, payload: UpdateMedicineRequest, db: sqlite3.Connection = Depends(get_db)):
    """Update medicine master attributes."""
    cursor = db.cursor()
    cursor.execute("SELECT * FROM medicines WHERE id = ?;", (id,))
    existing = cursor.fetchone()
    if not existing:
        cursor.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Medicine #{id} not found.")

    # Validate manufacturer
    new_manufacturer_id = payload.manufacturer_id if payload.manufacturer_id is not None else existing["manufacturer_id"]
    if new_manufacturer_id is not None and new_manufacturer_id != existing["manufacturer_id"]:
        cursor.execute("SELECT id FROM manufacturers WHERE id = ?;", (new_manufacturer_id,))
        if not cursor.fetchone():
            cursor.close()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Manufacturer #{new_manufacturer_id} does not exist.")

    # Validate unique medicine code
    new_code = payload.medicine_code.strip() if payload.medicine_code is not None else existing["medicine_code"]
    if new_code and new_code != existing["medicine_code"]:
        cursor.execute("SELECT id FROM medicines WHERE LOWER(medicine_code) = LOWER(?) AND id != ?;", (new_code, id))
        if cursor.fetchone():
            cursor.close()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Medicine code '{new_code}' is already assigned.")

    # Validate unique barcode
    new_barcode = payload.barcode.strip() if payload.barcode is not None else existing["barcode"]
    if new_barcode and new_barcode != existing["barcode"]:
        cursor.execute("SELECT id FROM medicines WHERE barcode = ? AND id != ?;", (new_barcode, id))
        if cursor.fetchone():
            cursor.close()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Barcode '{new_barcode}' is already assigned.")

    new_brand = payload.brand_name.strip() if payload.brand_name is not None else existing["brand_name"]
    new_salt = payload.generic_salt.strip() if payload.generic_salt is not None else existing["generic_salt"]
    new_form = payload.dosage_form if payload.dosage_form is not None else existing["dosage_form"]
    new_strength = payload.strength.strip() if payload.strength is not None else existing["strength"]
    new_pack = payload.pack_size if payload.pack_size is not None else existing["pack_size"]
    new_hsn = payload.hsn_code if payload.hsn_code is not None else existing["hsn_code"]
    new_gst = payload.gst_rate if payload.gst_rate is not None else existing["gst_rate"]
    new_h1 = payload.is_schedule_h1 if payload.is_schedule_h1 is not None else bool(existing["is_schedule_h1"])
    new_h = payload.is_schedule_h if payload.is_schedule_h is not None else bool(existing["is_schedule_h"])
    new_narc = payload.is_narcotic if payload.is_narcotic is not None else bool(existing["is_narcotic"])
    new_min = payload.min_stock_units if payload.min_stock_units is not None else existing["min_stock_units"]
    new_rack = payload.rack_location.strip() if payload.rack_location is not None else existing["rack_location"]
    new_active = payload.is_active if payload.is_active is not None else bool(existing["is_active"])

    now_str = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        """
        UPDATE medicines SET
            medicine_code = ?, brand_name = ?, generic_salt = ?, dosage_form = ?, strength = ?,
            pack_size = ?, manufacturer_id = ?, hsn_code = ?, gst_rate = ?, is_schedule_h1 = ?,
            is_schedule_h = ?, is_narcotic = ?, min_stock_units = ?, rack_location = ?,
            barcode = ?, is_active = ?, updated_at = ?
        WHERE id = ?;
        """,
        (
            new_code, new_brand, new_salt, new_form, new_strength,
            new_pack, new_manufacturer_id, new_hsn, new_gst, 1 if new_h1 else 0,
            1 if new_h else 0, 1 if new_narc else 0, new_min, new_rack,
            new_barcode, 1 if new_active else 0, now_str, id,
        ),
    )
    cursor.close()

    return get_medicine(id, db)


@router.delete("/medicines/{id}", response_model=SuccessResponse[MedicineResponse], dependencies=[write_guard])
def deactivate_medicine(id: int, db: sqlite3.Connection = Depends(get_db)):
    """Soft-deactivate a medicine, preventing counter sales without breaking historical records."""
    cursor = db.cursor()
    cursor.execute("SELECT id FROM medicines WHERE id = ?;", (id,))
    if not cursor.fetchone():
        cursor.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Medicine #{id} not found.")

    now_str = datetime.now(timezone.utc).isoformat()
    cursor.execute("UPDATE medicines SET is_active = 0, updated_at = ? WHERE id = ?;", (now_str, id))
    cursor.close()

    return get_medicine(id, db)


# ==============================================================================
# 3. SUPPLIERS ENDPOINTS
# ==============================================================================

@router.get("/suppliers", response_model=SuccessResponse[PaginatedData[SupplierResponse]], dependencies=[read_guard])
def list_suppliers(
    query: Optional[str] = Query(None, description="Search by distributor name, GSTIN, phone, or DL number"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: sqlite3.Connection = Depends(get_db),
):
    """List and search stockists and distributors with pagination."""
    conditions = []
    params = []

    if query and query.strip():
        term = f"%{query.strip()}%"
        conditions.append("(name LIKE ? OR gstin LIKE ? OR phone LIKE ? OR dl_number_20b LIKE ? OR dl_number_21b LIKE ?)")
        params.extend([term, term, term, term, term])

    if is_active is not None:
        conditions.append("is_active = ?")
        params.append(1 if is_active else 0)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    cursor = db.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM suppliers {where_clause};", params)
    total = cursor.fetchone()[0]

    offset = (page - 1) * page_size
    cursor.execute(
        f"""
        SELECT id, name, gstin, dl_number_20b, dl_number_21b, phone, email, address, credit_days, current_payable_paise, is_active, created_at
        FROM suppliers
        {where_clause}
        ORDER BY name ASC
        LIMIT ? OFFSET ?;
        """,
        params + [page_size, offset],
    )
    rows = cursor.fetchall()
    cursor.close()

    items = [
        SupplierResponse(
            id=row["id"],
            name=row["name"],
            gstin=row["gstin"],
            dl_number_20b=row["dl_number_20b"],
            dl_number_21b=row["dl_number_21b"],
            phone=row["phone"],
            email=row["email"],
            address=row["address"],
            credit_days=row["credit_days"],
            current_payable_paise=row["current_payable_paise"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
        )
        for row in rows
    ]

    total_pages = math.ceil(total / page_size) if total > 0 else 1
    return SuccessResponse(
        data=PaginatedData(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)
    )


@router.get("/suppliers/{id}", response_model=SuccessResponse[SupplierResponse], dependencies=[read_guard])
def get_supplier(id: int, db: sqlite3.Connection = Depends(get_db)):
    """Fetch single supplier details."""
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT id, name, gstin, dl_number_20b, dl_number_21b, phone, email, address, credit_days, current_payable_paise, is_active, created_at
        FROM suppliers WHERE id = ?;
        """,
        (id,),
    )
    row = cursor.fetchone()
    cursor.close()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Supplier #{id} not found.")

    return SuccessResponse(
        data=SupplierResponse(
            id=row["id"],
            name=row["name"],
            gstin=row["gstin"],
            dl_number_20b=row["dl_number_20b"],
            dl_number_21b=row["dl_number_21b"],
            phone=row["phone"],
            email=row["email"],
            address=row["address"],
            credit_days=row["credit_days"],
            current_payable_paise=row["current_payable_paise"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
        )
    )


@router.get("/suppliers/{id}/payable-summary", response_model=SuccessResponse[SupplierPayableSummaryResponse], dependencies=[read_guard])
def get_supplier_payable_summary(id: int, db: sqlite3.Connection = Depends(get_db)):
    """Retrieve supplier payable ledger summary placeholder."""
    cursor = db.cursor()
    cursor.execute("SELECT id, name, current_payable_paise FROM suppliers WHERE id = ?;", (id,))
    row = cursor.fetchone()
    cursor.close()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Supplier #{id} not found.")

    return SuccessResponse(
        data=SupplierPayableSummaryResponse(
            supplier_id=row["id"],
            supplier_name=row["name"],
            current_payable_paise=row["current_payable_paise"],
            pending_invoices_count=0,
            oldest_due_date=None,
        )
    )


@router.post("/suppliers", response_model=SuccessResponse[SupplierResponse], status_code=status.HTTP_201_CREATED, dependencies=[write_guard])
def create_supplier(payload: CreateSupplierRequest, db: sqlite3.Connection = Depends(get_db)):
    """Register a new pharmaceutical stockist/distributor."""
    clean_gstin = payload.gstin.strip().upper() if payload.gstin else None
    clean_dl20 = payload.dl_number_20b.strip().upper() if payload.dl_number_20b else None
    clean_dl21 = payload.dl_number_21b.strip().upper() if payload.dl_number_21b else None

    cursor = db.cursor()

    # Check unique GSTIN
    if clean_gstin:
        cursor.execute("SELECT id FROM suppliers WHERE UPPER(gstin) = ?;", (clean_gstin,))
        if cursor.fetchone():
            cursor.close()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"GSTIN '{clean_gstin}' is already registered.")

    # Check unique Drug Licenses
    if clean_dl20:
        cursor.execute("SELECT id FROM suppliers WHERE UPPER(dl_number_20b) = ?;", (clean_dl20,))
        if cursor.fetchone():
            cursor.close()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Drug License 20B '{clean_dl20}' is already registered.")

    if clean_dl21:
        cursor.execute("SELECT id FROM suppliers WHERE UPPER(dl_number_21b) = ?;", (clean_dl21,))
        if cursor.fetchone():
            cursor.close()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Drug License 21B '{clean_dl21}' is already registered.")

    now_str = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        """
        INSERT INTO suppliers (name, gstin, dl_number_20b, dl_number_21b, phone, email, address, credit_days, current_payable_paise, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 1, ?);
        """,
        (
            payload.name.strip(),
            clean_gstin,
            clean_dl20,
            clean_dl21,
            payload.phone.strip() if payload.phone else None,
            payload.email.strip() if payload.email else None,
            payload.address.strip() if payload.address else None,
            payload.credit_days,
            now_str,
        ),
    )
    new_id = cursor.lastrowid
    cursor.close()

    return get_supplier(new_id, db)


@router.put("/suppliers/{id}", response_model=SuccessResponse[SupplierResponse], dependencies=[write_guard])
def update_supplier(id: int, payload: UpdateSupplierRequest, db: sqlite3.Connection = Depends(get_db)):
    """Update distributor profile and statutory details."""
    cursor = db.cursor()
    cursor.execute("SELECT * FROM suppliers WHERE id = ?;", (id,))
    existing = cursor.fetchone()
    if not existing:
        cursor.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Supplier #{id} not found.")

    new_gstin = payload.gstin.strip().upper() if payload.gstin is not None else existing["gstin"]
    new_dl20 = payload.dl_number_20b.strip().upper() if payload.dl_number_20b is not None else existing["dl_number_20b"]
    new_dl21 = payload.dl_number_21b.strip().upper() if payload.dl_number_21b is not None else existing["dl_number_21b"]

    if new_gstin and new_gstin != existing["gstin"]:
        cursor.execute("SELECT id FROM suppliers WHERE UPPER(gstin) = ? AND id != ?;", (new_gstin, id))
        if cursor.fetchone():
            cursor.close()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"GSTIN '{new_gstin}' is already registered.")

    if new_dl20 and new_dl20 != existing["dl_number_20b"]:
        cursor.execute("SELECT id FROM suppliers WHERE UPPER(dl_number_20b) = ? AND id != ?;", (new_dl20, id))
        if cursor.fetchone():
            cursor.close()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Drug License 20B '{new_dl20}' is already registered.")

    if new_dl21 and new_dl21 != existing["dl_number_21b"]:
        cursor.execute("SELECT id FROM suppliers WHERE UPPER(dl_number_21b) = ? AND id != ?;", (new_dl21, id))
        if cursor.fetchone():
            cursor.close()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Drug License 21B '{new_dl21}' is already registered.")

    new_name = payload.name.strip() if payload.name is not None else existing["name"]
    new_phone = payload.phone.strip() if payload.phone is not None else existing["phone"]
    new_email = payload.email.strip() if payload.email is not None else existing["email"]
    new_address = payload.address.strip() if payload.address is not None else existing["address"]
    new_days = payload.credit_days if payload.credit_days is not None else existing["credit_days"]
    new_active = payload.is_active if payload.is_active is not None else bool(existing["is_active"])

    cursor.execute(
        """
        UPDATE suppliers SET
            name = ?, gstin = ?, dl_number_20b = ?, dl_number_21b = ?,
            phone = ?, email = ?, address = ?, credit_days = ?, is_active = ?
        WHERE id = ?;
        """,
        (new_name, new_gstin, new_dl20, new_dl21, new_phone, new_email, new_address, new_days, 1 if new_active else 0, id),
    )
    cursor.close()

    return get_supplier(id, db)


@router.delete("/suppliers/{id}", response_model=SuccessResponse[SupplierResponse], dependencies=[write_guard])
def deactivate_supplier(id: int, db: sqlite3.Connection = Depends(get_db)):
    """Soft-deactivate a supplier without deleting historic ledger balances."""
    cursor = db.cursor()
    cursor.execute("SELECT id FROM suppliers WHERE id = ?;", (id,))
    if not cursor.fetchone():
        cursor.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Supplier #{id} not found.")

    cursor.execute("UPDATE suppliers SET is_active = 0 WHERE id = ?;", (id,))
    cursor.close()

    return get_supplier(id, db)


# ==============================================================================
# 4. CUSTOMERS ENDPOINTS
# ==============================================================================

@router.get("/customers", response_model=SuccessResponse[PaginatedData[CustomerResponse]], dependencies=[read_guard])
def list_customers(
    query: Optional[str] = Query(None, description="Search by customer name or phone number"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: sqlite3.Connection = Depends(get_db),
):
    """List and search customers by name and phone with pagination."""
    conditions = []
    params = []

    if query and query.strip():
        term = f"%{query.strip()}%"
        conditions.append("(name LIKE ? OR phone LIKE ?)")
        params.extend([term, term])

    if is_active is not None:
        conditions.append("is_active = ?")
        params.append(1 if is_active else 0)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    cursor = db.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM customers {where_clause};", params)
    total = cursor.fetchone()[0]

    offset = (page - 1) * page_size
    cursor.execute(
        f"""
        SELECT id, name, phone, gstin, address, default_doctor, credit_limit_paise, current_balance_paise, is_active, created_at, updated_at
        FROM customers
        {where_clause}
        ORDER BY name ASC
        LIMIT ? OFFSET ?;
        """,
        params + [page_size, offset],
    )
    rows = cursor.fetchall()
    cursor.close()

    items = [
        CustomerResponse(
            id=row["id"],
            name=row["name"],
            phone=row["phone"],
            gstin=row["gstin"] if "gstin" in row.keys() else None,
            address=row["address"],
            default_doctor=row["default_doctor"],
            credit_limit_paise=row["credit_limit_paise"],
            current_balance_paise=row["current_balance_paise"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]

    total_pages = math.ceil(total / page_size) if total > 0 else 1
    return SuccessResponse(
        data=PaginatedData(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)
    )


@router.get("/customers/{id}", response_model=SuccessResponse[CustomerResponse], dependencies=[read_guard])
def get_customer(id: int, db: sqlite3.Connection = Depends(get_db)):
    """Fetch single customer profile by ID."""
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT id, name, phone, gstin, address, default_doctor, credit_limit_paise, current_balance_paise, is_active, created_at, updated_at
        FROM customers WHERE id = ?;
        """,
        (id,),
    )
    row = cursor.fetchone()
    cursor.close()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Customer #{id} not found.")

    return SuccessResponse(
        data=CustomerResponse(
            id=row["id"],
            name=row["name"],
            phone=row["phone"],
            gstin=row["gstin"] if "gstin" in row.keys() else None,
            address=row["address"],
            default_doctor=row["default_doctor"],
            credit_limit_paise=row["credit_limit_paise"],
            current_balance_paise=row["current_balance_paise"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
    )


@router.post("/customers", response_model=SuccessResponse[CustomerResponse], status_code=status.HTTP_201_CREATED, dependencies=[write_guard])
def create_customer(payload: CreateCustomerRequest, db: sqlite3.Connection = Depends(get_db)):
    """Create a new customer account with credit limit."""
    clean_phone = payload.phone.strip() if payload.phone else None
    clean_gstin = payload.gstin.strip().upper() if payload.gstin else None

    cursor = db.cursor()
    if clean_phone:
        cursor.execute("SELECT id FROM customers WHERE phone = ?;", (clean_phone,))
        if cursor.fetchone():
            cursor.close()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Phone number '{clean_phone}' is already registered.")

    now_str = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        """
        INSERT INTO customers (name, phone, gstin, address, default_doctor, credit_limit_paise, current_balance_paise, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 0, 1, ?, ?);
        """,
        (
            payload.name.strip(),
            clean_phone,
            clean_gstin,
            payload.address.strip() if payload.address else None,
            payload.default_doctor.strip() if payload.default_doctor else None,
            payload.credit_limit_paise,
            now_str,
            now_str,
        ),
    )
    new_id = cursor.lastrowid
    cursor.close()

    return get_customer(new_id, db)


@router.put("/customers/{id}", response_model=SuccessResponse[CustomerResponse], dependencies=[write_guard])
def update_customer(id: int, payload: UpdateCustomerRequest, db: sqlite3.Connection = Depends(get_db)):
    """Update customer contact info, credit limit, or active status."""
    cursor = db.cursor()
    cursor.execute("SELECT * FROM customers WHERE id = ?;", (id,))
    existing = cursor.fetchone()
    if not existing:
        cursor.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Customer #{id} not found.")

    new_phone = payload.phone.strip() if payload.phone else existing["phone"]
    if new_phone and new_phone != existing["phone"]:
        cursor.execute("SELECT id FROM customers WHERE phone = ? AND id != ?;", (new_phone, id))
        if cursor.fetchone():
            cursor.close()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Phone number '{new_phone}' is already registered.")

    new_name = payload.name.strip() if payload.name is not None else existing["name"]
    new_gstin = payload.gstin.strip().upper() if payload.gstin is not None else existing.get("gstin")
    new_address = payload.address.strip() if payload.address is not None else existing["address"]
    new_doc = payload.default_doctor.strip() if payload.default_doctor is not None else existing["default_doctor"]
    new_limit = payload.credit_limit_paise if payload.credit_limit_paise is not None else existing["credit_limit_paise"]
    new_active = payload.is_active if payload.is_active is not None else bool(existing["is_active"])

    now_str = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        """
        UPDATE customers SET
            name = ?, phone = ?, gstin = ?, address = ?, default_doctor = ?,
            credit_limit_paise = ?, is_active = ?, updated_at = ?
        WHERE id = ?;
        """,
        (new_name, new_phone, new_gstin, new_address, new_doc, new_limit, 1 if new_active else 0, now_str, id),
    )
    cursor.close()

    return get_customer(id, db)


@router.delete("/customers/{id}", response_model=SuccessResponse[CustomerResponse], dependencies=[write_guard])
def deactivate_customer(id: int, db: sqlite3.Connection = Depends(get_db)):
    """Soft-deactivate a customer without modifying Khata ledger balance."""
    cursor = db.cursor()
    cursor.execute("SELECT id FROM customers WHERE id = ?;", (id,))
    if not cursor.fetchone():
        cursor.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Customer #{id} not found.")

    now_str = datetime.now(timezone.utc).isoformat()
    cursor.execute("UPDATE customers SET is_active = 0, updated_at = ? WHERE id = ?;", (now_str, id))
    cursor.close()

    return get_customer(id, db)
