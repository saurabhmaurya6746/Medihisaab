"""Master Catalog REST APIs for Manufacturers, Medicines, Suppliers, and Customers."""

from datetime import datetime, timezone
import math
import re
import sqlite3
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status

from .dependencies import get_db, require_role, require_write_role
from .schemas import (
    CreateCustomerRequest,
    CreateManufacturerRequest,
    CreateMedicineRequest,
    CreateSupplierRequest,
    CustomerResponse,
    ManufacturerResponse,
    MedicineImportExecuteRequest,
    MedicineImportExecuteResponse,
    MedicineImportPreviewResponse,
    MedicineImportRowSchema,
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
from .tabular_import import (
    clear_staged_import,
    find_col,
    generate_csv_template,
    generate_xlsx_template,
    get_staged_import,
    parse_tabular_upload,
    save_staged_import,
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
# 2B. MEDICINES BULK IMPORT (CSV & EXCEL)
# ==============================================================================

MEDICINE_TEMPLATE_HEADERS = [
    "Medicine Name *",
    "Generic Composition",
    "Dosage Form",
    "Strength",
    "Pack Size *",
    "Manufacturer",
    "HSN Code",
    "GST Rate %",
    "Schedule H1 (YES/NO)",
    "Schedule H (YES/NO)",
    "Narcotic (YES/NO)",
    "Min Stock Units",
    "Rack Location",
    "Barcode",
]

MEDICINE_SAMPLE_ROWS = [
    ["Augmentin 625", "Amoxicillin + Clavulanic Acid", "TABLET", "625mg", 10, "GlaxoSmithKline", "3004", 12, "NO", "YES", "NO", 15, "A-01", "8901234567890"],
    ["Dolo 650", "Paracetamol", "TABLET", "650mg", 15, "Micro Labs", "3004", 12, "NO", "NO", "NO", 20, "A-02", "8901234567891"],
    ["Azithral 500", "Azithromycin", "TABLET", "500mg", 5, "Alembic Pharma", "3004", 12, "YES", "YES", "NO", 10, "B-01", "8901234567892"],
    ["Benadryl Cough Syrup", "Diphenhydramine", "SYRUP", "100ml", 1, "Johnson & Johnson", "3004", 12, "NO", "NO", "NO", 10, "C-01", ""],
]


@router.get("/medicines/import/template", dependencies=[read_guard])
def download_medicine_template(format: str = Query("csv", description="csv or xlsx")):
    """Download clean, ready-to-use CSV or Excel sample template for medicines import."""
    fmt = format.strip().lower()
    if fmt == "xlsx":
        content = generate_xlsx_template("Medicines Template", MEDICINE_TEMPLATE_HEADERS, MEDICINE_SAMPLE_ROWS)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=medihisaab_medicines_sample_template.xlsx"},
        )
    content = generate_csv_template(MEDICINE_TEMPLATE_HEADERS, MEDICINE_SAMPLE_ROWS)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=medihisaab_medicines_sample_template.csv"},
    )


@router.post("/medicines/import-preview", response_model=SuccessResponse[MedicineImportPreviewResponse], dependencies=[write_guard])
async def preview_medicine_import(
    file: UploadFile = File(...),
    db: sqlite3.Connection = Depends(get_db),
):
    """Parse and validate CSV/Excel medicine file, checking for duplicates and row errors."""
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty.",
        )

    try:
        raw_rows = parse_tabular_upload(file_bytes, file.filename or "upload.csv")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read file: {str(exc)}",
        )

    if not raw_rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The file does not contain any valid data rows.",
        )

    cursor = db.cursor()
    # Cache existing medicines for duplicate checking
    cursor.execute("SELECT id, LOWER(brand_name) AS brand_lower, barcode FROM medicines;")
    existing_meds = cursor.fetchall()
    existing_by_name = {m["brand_lower"]: m["id"] for m in existing_meds if m["brand_lower"]}
    existing_by_barcode = {m["barcode"]: m["id"] for m in existing_meds if m["barcode"]}
    cursor.close()

    preview_rows: List[MedicineImportRowSchema] = []
    seen_in_batch: set = set()

    VALID_FORMS = {"TABLET", "CAPSULE", "SYRUP", "INJECTION", "OINTMENT", "DROPS", "POWDER", "RESPULES", "INHALER", "GEL", "CREAM", "OTHER"}
    VALID_GST = {0.0, 5.0, 12.0, 18.0, 28.0}

    for idx, r in enumerate(raw_rows, start=1):
        errors: List[str] = []

        brand_name_raw = find_col(r, ["Medicine Name", "Brand Name", "Name", "Medicine", "Item Name", "Product Name"])
        brand_name = str(brand_name_raw).strip() if brand_name_raw is not None else ""
        if not brand_name:
            errors.append("Medicine Name is required.")

        generic_salt_raw = find_col(r, ["Generic Composition", "Generic Salt", "Composition", "Generic", "Generic Name", "Salt", "Salt Composition"])
        generic_salt = str(generic_salt_raw).strip() if generic_salt_raw is not None else ""

        dosage_form_raw = find_col(r, ["Dosage Form", "Form", "Type"], "TABLET")
        dosage_form = str(dosage_form_raw).strip().upper() if dosage_form_raw else "TABLET"
        if dosage_form not in VALID_FORMS:
            errors.append(f"Invalid dosage form '{dosage_form_raw}'. Allowed: {', '.join(sorted(VALID_FORMS))}.")
            dosage_form = "OTHER"

        strength_raw = find_col(r, ["Strength", "Power", "Potency"])
        strength = str(strength_raw).strip() if strength_raw is not None else None

        pack_size_raw = find_col(r, ["Pack Size", "Pack", "Units per pack", "Packaging"], 1)
        try:
            # Handle float or integer or string like '10 Tablets'
            if isinstance(pack_size_raw, (int, float)):
                pack_size = int(pack_size_raw)
            else:
                match = re.search(r"\d+", str(pack_size_raw))
                pack_size = int(match.group(0)) if match else 1
            if pack_size < 1:
                errors.append("Pack size must be at least 1 unit.")
                pack_size = 1
        except Exception:
            errors.append("Invalid pack size number.")
            pack_size = 1

        manufacturer_raw = find_col(r, ["Manufacturer", "Mfg", "Company", "Brand Manufacturer"])
        manufacturer_name = str(manufacturer_raw).strip() if manufacturer_raw is not None else None

        hsn_raw = find_col(r, ["HSN Code", "HSN"], "3004")
        hsn_code = str(hsn_raw).strip() if hsn_raw else "3004"

        gst_raw = find_col(r, ["GST Rate %", "GST Rate", "GST", "Tax Rate"], 12.0)
        try:
            gst_rate = float(gst_raw)
            if gst_rate not in VALID_GST:
                errors.append(f"GST rate {gst_rate}% is not a statutory slab (0, 5, 12, 18, 28%).")
        except Exception:
            errors.append("Invalid GST rate.")
            gst_rate = 12.0

        def parse_bool(col_names: List[str]) -> bool:
            val = find_col(r, col_names)
            if val is None:
                return False
            s = str(val).strip().lower()
            return s in ("yes", "y", "true", "1", "t")

        is_h1 = parse_bool(["Schedule H1", "Sch H1", "H1", "Schedule H1 (YES/NO)"])
        is_h = parse_bool(["Schedule H", "Sch H", "H", "Schedule H (YES/NO)"])
        is_narc = parse_bool(["Narcotic", "Schedule X", "Sch X", "Narcotic (YES/NO)"])

        min_stock_raw = find_col(r, ["Min Stock Units", "Min Stock", "Minimum Stock", "Reorder Level"], 10)
        try:
            min_stock = max(0, int(float(min_stock_raw)))
        except Exception:
            min_stock = 10

        rack_raw = find_col(r, ["Rack Location", "Rack", "Shelf"])
        rack_location = str(rack_raw).strip() if rack_raw is not None else None

        barcode_raw = find_col(r, ["Barcode", "EAN", "UPC"])
        barcode = str(barcode_raw).strip() if barcode_raw is not None else None

        # Duplicate checking
        existing_id = None
        status_label = "NEW"

        if brand_name:
            brand_lower = brand_name.lower()
            if brand_lower in seen_in_batch:
                errors.append("Duplicate medicine name found within this same import file.")
            seen_in_batch.add(brand_lower)

            if brand_lower in existing_by_name:
                existing_id = existing_by_name[brand_lower]
                status_label = "DUPLICATE"
            elif barcode and barcode in existing_by_barcode:
                existing_id = existing_by_barcode[barcode]
                status_label = "DUPLICATE"

        if errors:
            status_label = "INVALID"

        preview_rows.append(
            MedicineImportRowSchema(
                row_number=idx,
                brand_name=brand_name,
                generic_salt=generic_salt,
                dosage_form=dosage_form,
                strength=strength,
                pack_size=pack_size,
                manufacturer_name=manufacturer_name,
                hsn_code=hsn_code,
                gst_rate=gst_rate,
                is_schedule_h1=is_h1,
                is_schedule_h=is_h,
                is_narcotic=is_narc,
                min_stock_units=min_stock,
                rack_location=rack_location,
                barcode=barcode,
                status=status_label,
                existing_id=existing_id,
                errors=errors,
            )
        )

    total_rows = len(preview_rows)
    valid_rows = sum(1 for r in preview_rows if r.status in ("NEW", "DUPLICATE") and not r.errors)
    duplicate_rows = sum(1 for r in preview_rows if r.status == "DUPLICATE" and not r.errors)
    error_rows = sum(1 for r in preview_rows if r.status == "INVALID" or r.errors)

    staging_token = save_staged_import(
        "MEDICINES",
        [r.model_dump() for r in preview_rows],
    )

    return SuccessResponse(
        data=MedicineImportPreviewResponse(
            staging_token=staging_token,
            total_rows=total_rows,
            valid_rows=valid_rows,
            duplicate_rows=duplicate_rows,
            error_rows=error_rows,
            rows=preview_rows,
        )
    )


@router.post("/medicines/import-execute", response_model=SuccessResponse[MedicineImportExecuteResponse], dependencies=[write_guard])
def execute_medicine_import(
    payload: MedicineImportExecuteRequest,
    db: sqlite3.Connection = Depends(get_db),
):
    """Execute bulk medicine import committing verified rows with chosen duplicate policy."""
    rows_to_process: List[Dict[str, Any]] = []

    if payload.staging_token:
        session = get_staged_import(payload.staging_token)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Staging session expired or not found. Please upload the file again to preview.",
            )
        rows_to_process = session["rows"]
    elif payload.rows:
        rows_to_process = [r.model_dump() for r in payload.rows]
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either staging_token or rows array must be provided.",
        )

    policy = payload.duplicate_policy.strip().upper()
    if policy not in ("SKIP", "UPDATE"):
        policy = "SKIP"

    now_str = datetime.now(timezone.utc).isoformat()
    inserted_count = 0
    updated_count = 0
    skipped_count = 0
    failed_count = 0

    cursor = db.cursor()
    cursor.execute("BEGIN IMMEDIATE;")
    try:
        # Cache manufacturers
        cursor.execute("SELECT id, LOWER(name) AS name_lower FROM manufacturers;")
        mfg_map = {m["name_lower"]: m["id"] for m in cursor.fetchall()}

        for r in rows_to_process:
            if r.get("errors") or r.get("status") == "INVALID":
                failed_count += 1
                continue

            brand_name = r["brand_name"].strip()
            generic_salt = r.get("generic_salt") or ""
            dosage_form = r.get("dosage_form") or "TABLET"
            strength = r.get("strength")
            pack_size = max(1, int(r.get("pack_size", 1)))
            hsn_code = r.get("hsn_code") or "3004"
            gst_rate = float(r.get("gst_rate", 12.0))
            is_h1 = 1 if r.get("is_schedule_h1") else 0
            is_h = 1 if r.get("is_schedule_h") else 0
            is_narc = 1 if r.get("is_narcotic") else 0
            min_stock = max(0, int(r.get("min_stock_units", 10)))
            rack = r.get("rack_location")
            barcode = r.get("barcode")

            # Resolve manufacturer
            manufacturer_id = None
            mfg_name = r.get("manufacturer_name")
            if mfg_name and mfg_name.strip():
                clean_mfg = mfg_name.strip()
                mfg_lower = clean_mfg.lower()
                if mfg_lower in mfg_map:
                    manufacturer_id = mfg_map[mfg_lower]
                else:
                    cursor.execute(
                        "INSERT INTO manufacturers (name, is_active, created_at, updated_at) VALUES (?, 1, ?, ?);",
                        (clean_mfg, now_str, now_str),
                    )
                    manufacturer_id = cursor.lastrowid
                    mfg_map[mfg_lower] = manufacturer_id

            # Check duplicate status
            is_dup = r.get("status") == "DUPLICATE"
            existing_id = r.get("existing_id")

            if not is_dup:
                # Re-verify against database
                cursor.execute(
                    "SELECT id FROM medicines WHERE LOWER(brand_name) = ? OR (barcode IS NOT NULL AND barcode != '' AND barcode = ?);",
                    (brand_name.lower(), barcode),
                )
                found = cursor.fetchone()
                if found:
                    is_dup = True
                    existing_id = found[0]

            if is_dup:
                if policy == "SKIP":
                    skipped_count += 1
                    continue
                # UPDATE existing
                cursor.execute(
                    """
                    UPDATE medicines SET
                        generic_salt = ?,
                        dosage_form = ?,
                        strength = ?,
                        pack_size = ?,
                        manufacturer_id = COALESCE(?, manufacturer_id),
                        hsn_code = ?,
                        gst_rate = ?,
                        is_schedule_h1 = ?,
                        is_schedule_h = ?,
                        is_narcotic = ?,
                        min_stock_units = ?,
                        rack_location = COALESCE(?, rack_location),
                        barcode = COALESCE(?, barcode),
                        updated_at = ?
                    WHERE id = ?;
                    """,
                    (
                        generic_salt, dosage_form, strength, pack_size,
                        manufacturer_id, hsn_code, gst_rate, is_h1, is_h,
                        is_narc, min_stock, rack, barcode, now_str, existing_id,
                    ),
                )
                updated_count += 1
            else:
                # INSERT new medicine
                cursor.execute(
                    """
                    INSERT INTO medicines (
                        brand_name, generic_salt, dosage_form, strength, pack_size,
                        manufacturer_id, hsn_code, gst_rate, is_schedule_h1, is_schedule_h,
                        is_narcotic, min_stock_units, rack_location, barcode, is_active,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?);
                    """,
                    (
                        brand_name, generic_salt, dosage_form, strength, pack_size,
                        manufacturer_id, hsn_code, gst_rate, is_h1, is_h,
                        is_narc, min_stock, rack, barcode, now_str, now_str,
                    ),
                )
                inserted_count += 1

        cursor.execute("COMMIT;")
    except Exception as exc:
        cursor.execute("ROLLBACK;")
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Medicine bulk import transaction failed: {str(exc)}",
        )
    finally:
        cursor.close()

    if payload.staging_token:
        clear_staged_import(payload.staging_token)

    summary_msg = (
        f"Import completed: {inserted_count} new medicine(s) inserted, "
        f"{updated_count} updated, {skipped_count} skipped, {failed_count} invalid."
    )

    return SuccessResponse(
        data=MedicineImportExecuteResponse(
            success=True,
            inserted_count=inserted_count,
            updated_count=updated_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            message=summary_msg,
        )
    )



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
