"""Compliance and Statutory Reports API router:
Schedule H1 Drug Register, GSTR-1, GSTR-2, Sales/Purchase Registers, Day-Book Cash Reconciliation, and CSV exports.

Enforces ADMIN authorization and exact integer paise reconciliation.
"""

import csv
from datetime import datetime, timezone
import io
import sqlite3
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse

from ..security.roles import UserRole
from .dependencies import get_current_user, get_db, require_role
from .schemas import (
    DayBookCloseRequest,
    DayBookCurrentResponse,
    DayBookOpeningFloatRequest,
    DayBookSessionResponse,
    DayBookSummaryResponse,
    Gstr1B2BInvoiceResponse,
    Gstr1B2CInvoiceResponse,
    Gstr1DocSequenceResponse,
    Gstr1HsnSummaryResponse,
    Gstr1ReportResponse,
    Gstr1TotalsResponse,
    Gstr2ReportResponse,
    Gstr2SupplierGroupResponse,
    Gstr2TotalsResponse,
    PurchaseRegisterItemResponse,
    SalesRegisterItemResponse,
    ScheduleH1RecordResponse,
    ScheduleH1ReportResponse,
    SuccessResponse,
)

router = APIRouter(prefix="/api/v1/reports", tags=["Compliance & Reports"])
admin_guard = Depends(require_role(UserRole.ADMIN))


def _log_export_audit(
    db: sqlite3.Connection,
    report_type: str,
    row_count: int,
    file_name: str,
    user_id: int,
    filter_params: Optional[str] = None,
) -> None:
    """Record an audit trail entry for generated statutory reports."""
    now_str = datetime.now(timezone.utc).isoformat()
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO export_audit_logs (
            report_type, format, filter_params, row_count, file_name, generated_by, created_at
        ) VALUES (?, 'CSV', ?, ?, ?, ?, ?);
    """, (report_type, filter_params, row_count, file_name, user_id, now_str))
    db.commit()


# =========================================================================
# 1. SCHEDULE H1 DRUG REGISTER
# =========================================================================

@router.get("/schedule-h1", response_model=SuccessResponse[ScheduleH1ReportResponse], dependencies=[admin_guard])
def get_schedule_h1_report(
    from_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    db: sqlite3.Connection = Depends(get_db),
):
    """Retrieve statutory Schedule H1 register entries."""
    cursor = db.cursor()
    conditions = []
    params: List[Any] = []

    if from_date:
        conditions.append("h.dispensed_date >= ?")
        params.append(from_date.strip())
    if to_date:
        conditions.append("h.dispensed_date <= ?")
        params.append(to_date.strip())

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    cursor.execute(f"""
        SELECT h.*, si.invoice_no, si.id AS sale_inv_id
        FROM schedule_h1_records h
        JOIN sale_items sit ON sit.id = h.sale_item_id
        JOIN sale_invoices si ON si.id = sit.sale_invoice_id
        {where_sql}
        ORDER BY h.dispensed_date DESC, h.id DESC;
    """, params)
    rows = cursor.fetchall()
    cursor.close()

    records = [
        ScheduleH1RecordResponse(
            id=r["id"],
            sale_item_id=r["sale_item_id"],
            sale_invoice_id=r["sale_inv_id"],
            invoice_no=r["invoice_no"],
            dispensed_date=r["dispensed_date"],
            medicine_name=r["medicine_name"],
            batch_number=r["batch_number"],
            quantity_units=r["quantity_units"],
            patient_name=r["patient_name"],
            patient_address=r["patient_address"],
            doctor_name=r["doctor_name"],
            doctor_address=r["doctor_address"],
            created_at=r["created_at"],
        )
        for r in rows
    ]

    return SuccessResponse(
        data=ScheduleH1ReportResponse(
            from_date=from_date,
            to_date=to_date,
            total_records=len(records),
            records=records,
        )
    )


@router.get("/schedule-h1/export", dependencies=[admin_guard])
def export_schedule_h1_csv(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    db: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Export Schedule H1 Drug Register to statutory CSV format."""
    rep = get_schedule_h1_report(from_date=from_date, to_date=to_date, db=db).data
    output = io.StringIO()
    writer = csv.writer(output)

    # Statutory Headers
    writer.writerow([
        "Date of Dispensing",
        "Invoice Number",
        "Name of Schedule H1 Drug",
        "Batch Number",
        "Quantity (Units)",
        "Patient Name",
        "Patient Address",
        "Prescribing Doctor",
        "Doctor Clinic/Address",
    ])

    for r in rep.records:
        writer.writerow([
            r.dispensed_date,
            r.invoice_no,
            r.medicine_name,
            r.batch_number,
            r.quantity_units,
            r.patient_name,
            r.patient_address,
            r.doctor_name,
            r.doctor_address or "",
        ])

    file_name = f"Schedule_H1_Register_{from_date or 'ALL'}_to_{to_date or 'ALL'}.csv"
    _log_export_audit(db, "SCHEDULE_H1", len(rep.records), file_name, current_user["id"], f"{from_date}:{to_date}")

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={file_name}"},
    )


# =========================================================================
# 2. GSTR-1 TAX REPORT & CSV EXPORT
# =========================================================================

@router.get("/gstr-1", response_model=SuccessResponse[Gstr1ReportResponse], dependencies=[admin_guard])
@router.get("/gst/gstr-1", response_model=SuccessResponse[Gstr1ReportResponse], dependencies=[admin_guard])
def get_gstr1_report(
    from_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    fiscal_year: Optional[str] = Query(None, description="e.g. 2026-2027"),
    db: sqlite3.Connection = Depends(get_db),
):
    """Generate GSTR-1 summary including B2B, B2C, HSN summary, and Document sequence."""
    cursor = db.cursor()
    conditions = ["si.status = 'COMPLETED'"]
    params: List[Any] = []

    if from_date:
        conditions.append("DATE(si.created_at) >= ?")
        params.append(from_date.strip())
    if to_date:
        conditions.append("DATE(si.created_at) <= ?")
        params.append(to_date.strip())
    if fiscal_year:
        conditions.append("si.fiscal_year = ?")
        params.append(fiscal_year.strip())

    where_sql = f"WHERE {' AND '.join(conditions)}"

    # Fetch completed invoices
    cursor.execute(f"""
        SELECT si.*, COALESCE(si.customer_gstin, c.gstin) AS effective_gstin,
               COALESCE(si.customer_name, c.name, 'Walk-in') AS eff_cust_name
        FROM sale_invoices si
        LEFT JOIN customers c ON c.id = si.customer_id
        {where_sql}
        ORDER BY si.id ASC;
    """, params)
    invoices = cursor.fetchall()

    b2b_invoices: List[Gstr1B2BInvoiceResponse] = []
    b2c_invoices: List[Gstr1B2CInvoiceResponse] = []

    total_taxable_paise = 0
    total_cgst_paise = 0
    total_sgst_paise = 0
    total_igst_paise = 0
    grand_total_paise = 0

    for inv in invoices:
        gstin = (inv["effective_gstin"] or "").strip().upper()
        inv_date = inv["created_at"][:10]
        # Average / blended gst_rate on invoice
        sub_taxable = inv["subtotal_taxable_paise"]
        cgst = inv["total_cgst_paise"]
        sgst = inv["total_sgst_paise"]
        igst = inv["total_igst_paise"]
        grand = inv["grand_total_paise"]

        total_taxable_paise += sub_taxable
        total_cgst_paise += cgst
        total_sgst_paise += sgst
        total_igst_paise += igst
        grand_total_paise += grand

        gst_rate = round(((cgst + sgst + igst) * 100.0) / sub_taxable, 2) if sub_taxable > 0 else 0.0

        if gstin:
            b2b_invoices.append(
                Gstr1B2BInvoiceResponse(
                    customer_gstin=gstin,
                    customer_name=inv["eff_cust_name"],
                    invoice_no=inv["invoice_no"],
                    invoice_date=inv_date,
                    invoice_value_paise=grand,
                    taxable_value_paise=sub_taxable,
                    gst_rate=gst_rate,
                    cgst_paise=cgst,
                    sgst_paise=sgst,
                    igst_paise=igst,
                    place_of_supply="State",
                )
            )
        else:
            b2c_invoices.append(
                Gstr1B2CInvoiceResponse(
                    invoice_no=inv["invoice_no"],
                    invoice_date=inv_date,
                    customer_name=inv["eff_cust_name"],
                    invoice_value_paise=grand,
                    taxable_value_paise=sub_taxable,
                    gst_rate=gst_rate,
                    cgst_paise=cgst,
                    sgst_paise=sgst,
                    igst_paise=igst,
                )
            )

    # HSN Summary
    cursor.execute(f"""
        SELECT m.hsn_code, m.dosage_form,
               SUM(sit.quantity_units) AS total_units,
               SUM(sit.taxable_amount_paise) AS hsn_taxable_paise,
               SUM(sit.cgst_amount_paise) AS hsn_cgst_paise,
               SUM(sit.sgst_amount_paise) AS hsn_sgst_paise,
               SUM(sit.total_amount_paise) AS hsn_total_paise
        FROM sale_items sit
        JOIN sale_invoices si ON si.id = sit.sale_invoice_id
        JOIN medicines m ON m.id = sit.medicine_id
        {where_sql}
        GROUP BY m.hsn_code;
    """, params)
    hsn_rows = cursor.fetchall()

    hsn_summary = [
        Gstr1HsnSummaryResponse(
            hsn_code=h["hsn_code"] or "3004",
            description="Medicaments",
            uqc="NOS",
            total_quantity=h["total_units"] or 0,
            total_value_paise=h["hsn_total_paise"] or 0,
            taxable_value_paise=h["hsn_taxable_paise"] or 0,
            igst_paise=0,
            cgst_paise=h["hsn_cgst_paise"] or 0,
            sgst_paise=h["hsn_sgst_paise"] or 0,
        )
        for h in hsn_rows
    ]

    # Document Sequence Summary
    cursor.execute(f"""
        SELECT MIN(sequence_number) AS min_seq, MAX(sequence_number) AS max_seq,
               COUNT(*) AS total_count
        FROM sale_invoices si
        {where_sql};
    """, params)
    seq_row = cursor.fetchone()

    doc_summary: List[Gstr1DocSequenceResponse] = []
    if invoices and seq_row and seq_row["total_count"] > 0:
        first_no = invoices[0]["invoice_no"]
        last_no = invoices[-1]["invoice_no"]
        total_cnt = seq_row["total_count"]
        doc_summary.append(
            Gstr1DocSequenceResponse(
                doc_type="Invoices for outward supply",
                from_serial=first_no,
                to_serial=last_no,
                total_number=total_cnt,
                cancelled_number=0,
                net_number=total_cnt,
            )
        )

    cursor.close()

    result = Gstr1ReportResponse(
        from_date=from_date or (invoices[0]["created_at"][:10] if invoices else ""),
        to_date=to_date or (invoices[-1]["created_at"][:10] if invoices else ""),
        fiscal_year=fiscal_year or (invoices[0]["fiscal_year"] if invoices else "2026-2027"),
        b2b_invoices=b2b_invoices,
        b2c_invoices=b2c_invoices,
        hsn_summary=hsn_summary,
        doc_summary=doc_summary,
        totals=Gstr1TotalsResponse(
            total_taxable_paise=total_taxable_paise,
            total_cgst_paise=total_cgst_paise,
            total_sgst_paise=total_sgst_paise,
            total_igst_paise=total_igst_paise,
            grand_total_paise=grand_total_paise,
        ),
    )
    return SuccessResponse(data=result)


@router.get("/gstr-1/export", dependencies=[admin_guard])
@router.get("/gst/gstr-1/export", dependencies=[admin_guard])
def export_gstr1_csv(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    fiscal_year: Optional[str] = Query(None),
    section: str = Query("b2b", description="b2b, b2c, hsn, or docs"),
    db: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Export GSTR-1 sections to statutory CSV."""
    rep = get_gstr1_report(from_date=from_date, to_date=to_date, fiscal_year=fiscal_year, db=db).data
    output = io.StringIO()
    writer = csv.writer(output)

    sec = section.strip().lower()
    if sec == "b2b":
        writer.writerow(["GSTIN/UIN of Recipient", "Receiver Name", "Invoice Number", "Invoice Date", "Invoice Value (INR)", "Taxable Value (INR)", "Rate (%)", "Cess Amount (INR)"])
        for b in rep.b2b_invoices:
            writer.writerow([
                b.customer_gstin,
                b.customer_name,
                b.invoice_no,
                b.invoice_date,
                f"{(b.invoice_value_paise / 100):.2f}",
                f"{(b.taxable_value_paise / 100):.2f}",
                b.gst_rate,
                "0.00",
            ])
        file_name = f"GSTR1_B2B_{rep.fiscal_year}.csv"
        row_cnt = len(rep.b2b_invoices)
    elif sec == "hsn":
        writer.writerow(["HSN", "Description", "UQC", "Total Quantity", "Total Value (INR)", "Taxable Value (INR)", "Integrated Tax (INR)", "Central Tax (INR)", "State/UT Tax (INR)"])
        for h in rep.hsn_summary:
            writer.writerow([
                h.hsn_code,
                h.description,
                h.uqc,
                h.total_quantity,
                f"{(h.total_value_paise / 100):.2f}",
                f"{(h.taxable_value_paise / 100):.2f}",
                f"{(h.igst_paise / 100):.2f}",
                f"{(h.cgst_paise / 100):.2f}",
                f"{(h.sgst_paise / 100):.2f}",
            ])
        file_name = f"GSTR1_HSN_{rep.fiscal_year}.csv"
        row_cnt = len(rep.hsn_summary)
    else:  # b2c default
        writer.writerow(["Type", "Invoice Number", "Invoice Date", "Invoice Value (INR)", "Taxable Value (INR)", "Rate (%)", "Central Tax (INR)", "State/UT Tax (INR)"])
        for b in rep.b2c_invoices:
            writer.writerow([
                "OE",
                b.invoice_no,
                b.invoice_date,
                f"{(b.invoice_value_paise / 100):.2f}",
                f"{(b.taxable_value_paise / 100):.2f}",
                b.gst_rate,
                f"{(b.cgst_paise / 100):.2f}",
                f"{(b.sgst_paise / 100):.2f}",
            ])
        file_name = f"GSTR1_B2C_{rep.fiscal_year}.csv"
        row_cnt = len(rep.b2c_invoices)

    _log_export_audit(db, f"GSTR_1_{sec.upper()}", row_cnt, file_name, current_user["id"], f"{from_date}:{to_date}")
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={file_name}"},
    )


@router.get("/gstr-1/b2b/export", dependencies=[admin_guard])
def export_gstr1_b2b_csv(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    fiscal_year: Optional[str] = Query(None),
    db: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return export_gstr1_csv(from_date=from_date, to_date=to_date, fiscal_year=fiscal_year, section="b2b", db=db, current_user=current_user)


@router.get("/gstr-1/b2c/export", dependencies=[admin_guard])
def export_gstr1_b2c_csv(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    fiscal_year: Optional[str] = Query(None),
    db: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return export_gstr1_csv(from_date=from_date, to_date=to_date, fiscal_year=fiscal_year, section="b2c", db=db, current_user=current_user)


@router.get("/gstr-1/hsn/export", dependencies=[admin_guard])
def export_gstr1_hsn_csv(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    fiscal_year: Optional[str] = Query(None),
    db: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return export_gstr1_csv(from_date=from_date, to_date=to_date, fiscal_year=fiscal_year, section="hsn", db=db, current_user=current_user)


# =========================================================================
# 3. GSTR-2 PURCHASE REGISTER & EXPORT
# =========================================================================

@router.get("/gstr-2", response_model=SuccessResponse[Gstr2ReportResponse], dependencies=[admin_guard])
@router.get("/gst/gstr-2", response_model=SuccessResponse[Gstr2ReportResponse], dependencies=[admin_guard])
def get_gstr2_report(
    from_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    db: sqlite3.Connection = Depends(get_db),
):
    """Generate GSTR-2 inward purchase register grouped by supplier GSTIN."""
    cursor = db.cursor()
    conditions = ["pi.status = 'POSTED'"]
    params: List[Any] = []

    if from_date:
        conditions.append("pi.invoice_date >= ?")
        params.append(from_date.strip())
    if to_date:
        conditions.append("pi.invoice_date <= ?")
        params.append(to_date.strip())

    where_sql = f"WHERE {' AND '.join(conditions)}"

    cursor.execute(f"""
        SELECT s.id AS sup_id, s.name AS sup_name, COALESCE(s.gstin, 'UNREGISTERED') AS sup_gstin,
               COUNT(pi.id) AS inv_count,
               SUM(pi.subtotal_paise) AS total_taxable,
               SUM(pi.tax_amount_paise) AS total_tax,
               SUM(pi.grand_total_paise) AS total_grand
        FROM purchase_invoices pi
        JOIN suppliers s ON s.id = pi.supplier_id
        {where_sql}
        GROUP BY s.id, s.name, s.gstin
        ORDER BY total_grand DESC;
    """, params)
    rows = cursor.fetchall()
    cursor.close()

    total_invoices = 0
    total_taxable_paise = 0
    total_tax_paise = 0
    grand_total_paise = 0

    suppliers: List[Gstr2SupplierGroupResponse] = []
    for r in rows:
        cnt = r["inv_count"] or 0
        taxable = r["total_taxable"] or 0
        tax = r["total_tax"] or 0
        grand = r["total_grand"] or 0

        total_invoices += cnt
        total_taxable_paise += taxable
        total_tax_paise += tax
        grand_total_paise += grand

        suppliers.append(
            Gstr2SupplierGroupResponse(
                supplier_id=r["sup_id"],
                supplier_name=r["sup_name"],
                supplier_gstin=r["sup_gstin"],
                invoice_count=cnt,
                subtotal_taxable_paise=taxable,
                total_tax_paise=tax,
                grand_total_paise=grand,
            )
        )

    result = Gstr2ReportResponse(
        from_date=from_date or "",
        to_date=to_date or "",
        suppliers=suppliers,
        totals=Gstr2TotalsResponse(
            total_invoices=total_invoices,
            total_taxable_paise=total_taxable_paise,
            total_tax_paise=total_tax_paise,
            grand_total_paise=grand_total_paise,
        ),
    )
    return SuccessResponse(data=result)


@router.get("/gstr-2/export", dependencies=[admin_guard])
@router.get("/gst/gstr-2/export", dependencies=[admin_guard])
def export_gstr2_csv(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    db: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Export GSTR-2 inward purchase register to CSV."""
    rep = get_gstr2_report(from_date=from_date, to_date=to_date, db=db).data
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["Supplier GSTIN", "Supplier Name", "Invoices Count", "Taxable Value (INR)", "Tax Amount (INR)", "Total Inward Amount (INR)"])
    for s in rep.suppliers:
        writer.writerow([
            s.supplier_gstin,
            s.supplier_name,
            s.invoice_count,
            f"{(s.subtotal_taxable_paise / 100):.2f}",
            f"{(s.total_tax_paise / 100):.2f}",
            f"{(s.grand_total_paise / 100):.2f}",
        ])

    file_name = f"GSTR2_Purchase_Register_{from_date or 'ALL'}_to_{to_date or 'ALL'}.csv"
    _log_export_audit(db, "GSTR_2", len(rep.suppliers), file_name, current_user["id"], f"{from_date}:{to_date}")

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={file_name}"},
    )


# =========================================================================
# 4. SALES & PURCHASE REGISTERS
# =========================================================================

@router.get("/sales-register", response_model=SuccessResponse[List[SalesRegisterItemResponse]], dependencies=[admin_guard])
def get_sales_register(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    db: sqlite3.Connection = Depends(get_db),
):
    """List detailed sales register."""
    cursor = db.cursor()
    conditions = []
    params: List[Any] = []

    if from_date:
        conditions.append("DATE(si.created_at) >= ?")
        params.append(from_date.strip())
    if to_date:
        conditions.append("DATE(si.created_at) <= ?")
        params.append(to_date.strip())

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    cursor.execute(f"""
        SELECT si.*, COUNT(sit.id) AS line_count
        FROM sale_invoices si
        LEFT JOIN sale_items sit ON sit.sale_invoice_id = si.id
        {where_sql}
        GROUP BY si.id
        ORDER BY si.id DESC;
    """, params)
    rows = cursor.fetchall()
    cursor.close()

    items = [
        SalesRegisterItemResponse(
            invoice_id=r["id"],
            invoice_no=r["invoice_no"],
            invoice_date=r["created_at"][:10],
            customer_name=r["customer_name"],
            customer_phone=r["customer_phone"],
            payment_mode=r["payment_mode"],
            item_count=r["line_count"],
            subtotal_taxable_paise=r["subtotal_taxable_paise"],
            total_cgst_paise=r["total_cgst_paise"],
            total_sgst_paise=r["total_sgst_paise"],
            total_igst_paise=r["total_igst_paise"],
            discount_paise=r["discount_paise"],
            round_off_paise=r["round_off_paise"],
            grand_total_paise=r["grand_total_paise"],
            status=r["status"],
        )
        for r in rows
    ]
    return SuccessResponse(data=items)


@router.get("/sales-register/export", dependencies=[admin_guard])
def export_sales_register_csv(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    db: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Export sales register to CSV."""
    items = get_sales_register(from_date=from_date, to_date=to_date, db=db).data
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Invoice No", "Date", "Customer", "Phone", "Payment Mode", "Taxable (INR)",
        "CGST (INR)", "SGST (INR)", "Discount (INR)", "Grand Total (INR)", "Status"
    ])
    for s in items:
        writer.writerow([
            s.invoice_no,
            s.invoice_date,
            s.customer_name or "Walk-in",
            s.customer_phone or "",
            s.payment_mode,
            f"{(s.subtotal_taxable_paise / 100):.2f}",
            f"{(s.total_cgst_paise / 100):.2f}",
            f"{(s.total_sgst_paise / 100):.2f}",
            f"{(s.discount_paise / 100):.2f}",
            f"{(s.grand_total_paise / 100):.2f}",
            s.status,
        ])

    file_name = f"Sales_Register_{from_date or 'ALL'}_to_{to_date or 'ALL'}.csv"
    _log_export_audit(db, "SALES_REGISTER", len(items), file_name, current_user["id"], f"{from_date}:{to_date}")

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={file_name}"},
    )


@router.get("/purchase-register", response_model=SuccessResponse[List[PurchaseRegisterItemResponse]], dependencies=[admin_guard])
def get_purchase_register(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    db: sqlite3.Connection = Depends(get_db),
):
    """List detailed purchase inwarding register."""
    cursor = db.cursor()
    conditions = []
    params: List[Any] = []

    if from_date:
        conditions.append("pi.invoice_date >= ?")
        params.append(from_date.strip())
    if to_date:
        conditions.append("pi.invoice_date <= ?")
        params.append(to_date.strip())

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    cursor.execute(f"""
        SELECT pi.*, s.name AS sup_name, s.gstin AS sup_gstin
        FROM purchase_invoices pi
        JOIN suppliers s ON s.id = pi.supplier_id
        {where_sql}
        ORDER BY pi.invoice_date DESC, pi.id DESC;
    """, params)
    rows = cursor.fetchall()
    cursor.close()

    items = [
        PurchaseRegisterItemResponse(
            invoice_id=r["id"],
            supplier_invoice_number=r["supplier_invoice_number"],
            invoice_date=r["invoice_date"],
            supplier_name=r["sup_name"],
            supplier_gstin=r["sup_gstin"],
            subtotal_paise=r["subtotal_paise"],
            discount_paise=r["discount_paise"],
            tax_amount_paise=r["tax_amount_paise"],
            grand_total_paise=r["grand_total_paise"],
            status=r["status"],
        )
        for r in rows
    ]
    return SuccessResponse(data=items)


@router.get("/purchase-register/export", dependencies=[admin_guard])
def export_purchase_register_csv(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    db: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Export purchase inwarding register to CSV."""
    items = get_purchase_register(from_date=from_date, to_date=to_date, db=db).data
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Supplier Invoice No", "Invoice Date", "Supplier", "Supplier GSTIN",
        "Subtotal (INR)", "Discount (INR)", "Tax (INR)", "Grand Total (INR)", "Status"
    ])
    for p in items:
        writer.writerow([
            p.supplier_invoice_number,
            p.invoice_date,
            p.supplier_name,
            p.supplier_gstin or "",
            f"{(p.subtotal_paise / 100):.2f}",
            f"{(p.discount_paise / 100):.2f}",
            f"{(p.tax_amount_paise / 100):.2f}",
            f"{(p.grand_total_paise / 100):.2f}",
            p.status,
        ])

    file_name = f"Purchase_Register_{from_date or 'ALL'}_to_{to_date or 'ALL'}.csv"
    _log_export_audit(db, "PURCHASE_REGISTER", len(items), file_name, current_user["id"], f"{from_date}:{to_date}")

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={file_name}"},
    )


# =========================================================================
# 5. DAY-BOOK & CASH RECONCILIATION
# =========================================================================

@router.get("/day-book/current", response_model=SuccessResponse[DayBookCurrentResponse], dependencies=[admin_guard])
@router.get("/daybook/current", response_model=SuccessResponse[DayBookCurrentResponse], dependencies=[admin_guard])
def get_current_daybook(
    session_date: Optional[str] = Query(None, description="Date YYYY-MM-DD (defaults to today)"),
    db: sqlite3.Connection = Depends(get_db),
):
    """Calculate live day-book reconciliation for the specified date."""
    target_date = session_date.strip() if session_date else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cursor = db.cursor()

    # 1. Fetch or initialize cash_session
    cursor.execute("""
        SELECT cs.*, u.username, u.full_name
        FROM cash_sessions cs
        LEFT JOIN users u ON u.id = cs.closed_by
        WHERE cs.session_date = ?;
    """, (target_date,))
    sess_row = cursor.fetchone()

    now_str = datetime.now(timezone.utc).isoformat()
    if not sess_row:
        cursor.execute("""
            INSERT INTO cash_sessions (
                session_date, opening_float_paise, cash_sales_paise, cash_deposits_paise,
                cash_refunds_paise, expected_cash_paise, status, created_at, updated_at
            ) VALUES (?, 0, 0, 0, 0, 0, 'OPEN', ?, ?);
        """, (target_date, now_str, now_str))
        db.commit()

        cursor.execute("SELECT * FROM cash_sessions WHERE session_date = ?;", (target_date,))
        sess_row = cursor.fetchone()

    opening_float_paise = sess_row["opening_float_paise"]
    is_closed = sess_row["status"] == "CLOSED"

    if is_closed:
        # If day is closed, use immutable recorded numbers
        cash_sales_paise = sess_row["cash_sales_paise"]
        cash_deposits_paise = sess_row["cash_deposits_paise"]
        cash_refunds_paise = sess_row["cash_refunds_paise"]
        expected_cash_paise = sess_row["expected_cash_paise"]
        actual_cash_paise = sess_row["actual_cash_paise"]
        variance_paise = sess_row["variance_paise"]
    else:
        # Calculate live cash sales
        cursor.execute("""
            SELECT COALESCE(SUM(sp.amount_paise), 0)
            FROM sale_payments sp
            JOIN sale_invoices si ON si.id = sp.sale_invoice_id
            WHERE sp.payment_mode = 'CASH'
              AND si.status = 'COMPLETED'
              AND DATE(si.created_at) = ?;
        """, (target_date,))
        cash_sales_paise = cursor.fetchone()[0]

        # Calculate live cash customer deposits (Khata payments)
        cursor.execute("""
            SELECT COALESCE(SUM(amount_paise), 0)
            FROM khata_ledger
            WHERE transaction_type = 'PAYMENT'
              AND payment_mode = 'CASH'
              AND DATE(created_at) = ?;
        """, (target_date,))
        cash_deposits_paise = cursor.fetchone()[0]

        # Calculate live cash refunds
        cursor.execute("""
            SELECT COALESCE(SUM(refund_amount_paise), 0)
            FROM sales_returns
            WHERE refund_mode = 'CASH'
              AND DATE(created_at) = ?;
        """, (target_date,))
        cash_refunds_paise = cursor.fetchone()[0]

        # Formula: Expected = Float + Sales + Deposits - Refunds
        expected_cash_paise = opening_float_paise + cash_sales_paise + cash_deposits_paise - cash_refunds_paise
        actual_cash_paise = sess_row["actual_cash_paise"]
        variance_paise = (actual_cash_paise - expected_cash_paise) if actual_cash_paise is not None else None

        # Update cache in open session
        cursor.execute("""
            UPDATE cash_sessions
            SET cash_sales_paise = ?, cash_deposits_paise = ?, cash_refunds_paise = ?,
                expected_cash_paise = ?, updated_at = ?
            WHERE id = ?;
        """, (cash_sales_paise, cash_deposits_paise, cash_refunds_paise, expected_cash_paise, now_str, sess_row["id"]))
        db.commit()

    # Calculate payment breakdown across all modes
    cursor.execute("""
        SELECT sp.payment_mode, COALESCE(SUM(sp.amount_paise), 0) AS total_paise
        FROM sale_payments sp
        JOIN sale_invoices si ON si.id = sp.sale_invoice_id
        WHERE si.status = 'COMPLETED'
          AND DATE(si.created_at) = ?
        GROUP BY sp.payment_mode;
    """, (target_date,))
    breakdown_rows = cursor.fetchall()
    cursor.close()

    payment_breakdown = {b["payment_mode"]: b["total_paise"] for b in breakdown_rows}

    session_resp = DayBookSessionResponse(
        id=sess_row["id"],
        session_date=target_date,
        opening_float_paise=opening_float_paise,
        cash_sales_paise=cash_sales_paise,
        cash_deposits_paise=cash_deposits_paise,
        cash_refunds_paise=cash_refunds_paise,
        expected_cash_paise=expected_cash_paise,
        actual_cash_paise=actual_cash_paise,
        variance_paise=variance_paise,
        status=sess_row["status"],
        closed_by=sess_row["closed_by"],
        closed_by_name=(sess_row["full_name"] or sess_row["username"]) if "full_name" in sess_row.keys() else None,
        closed_at=sess_row["closed_at"],
        notes=sess_row["notes"],
        created_at=sess_row["created_at"],
        updated_at=now_str,
    )

    summary_resp = DayBookSummaryResponse(
        opening_float_paise=opening_float_paise,
        cash_sales_paise=cash_sales_paise,
        cash_deposits_paise=cash_deposits_paise,
        cash_refunds_paise=cash_refunds_paise,
        expected_cash_paise=expected_cash_paise,
    )

    return SuccessResponse(
        data=DayBookCurrentResponse(
            session=session_resp,
            payment_breakdown=payment_breakdown,
            summary=summary_resp,
        )
    )


@router.post("/day-book/opening-float", response_model=SuccessResponse[DayBookSessionResponse], dependencies=[admin_guard])
@router.post("/daybook/opening-float", response_model=SuccessResponse[DayBookSessionResponse], dependencies=[admin_guard])
def set_daybook_opening_float(
    payload: DayBookOpeningFloatRequest,
    db: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Set or update the opening float for an unclosed day."""
    target_date = payload.session_date.strip() if payload.session_date else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now_str = datetime.now(timezone.utc).isoformat()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM cash_sessions WHERE session_date = ?;", (target_date,))
    existing = cursor.fetchone()

    if existing and existing["status"] == "CLOSED":
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cash session for {target_date} is already CLOSED and cannot be modified.",
        )

    if existing:
        cursor.execute("""
            UPDATE cash_sessions
            SET opening_float_paise = ?,
                expected_cash_paise = ? + cash_sales_paise + cash_deposits_paise - cash_refunds_paise,
                updated_at = ?
            WHERE id = ?;
        """, (payload.opening_float_paise, payload.opening_float_paise, now_str, existing["id"]))
    else:
        cursor.execute("""
            INSERT INTO cash_sessions (
                session_date, opening_float_paise, cash_sales_paise, cash_deposits_paise,
                cash_refunds_paise, expected_cash_paise, status, created_by, created_at, updated_at
            ) VALUES (?, ?, 0, 0, 0, ?, 'OPEN', ?, ?, ?);
        """, (target_date, payload.opening_float_paise, payload.opening_float_paise, current_user["id"], now_str, now_str))

    db.commit()

    cursor.execute("SELECT * FROM cash_sessions WHERE session_date = ?;", (target_date,))
    updated = cursor.fetchone()
    cursor.close()

    return SuccessResponse(
        data=DayBookSessionResponse(
            id=updated["id"],
            session_date=updated["session_date"],
            opening_float_paise=updated["opening_float_paise"],
            cash_sales_paise=updated["cash_sales_paise"],
            cash_deposits_paise=updated["cash_deposits_paise"],
            cash_refunds_paise=updated["cash_refunds_paise"],
            expected_cash_paise=updated["expected_cash_paise"],
            actual_cash_paise=updated["actual_cash_paise"],
            variance_paise=updated["variance_paise"],
            status=updated["status"],
            closed_by=updated["closed_by"],
            closed_at=updated["closed_at"],
            notes=updated["notes"],
            created_at=updated["created_at"],
            updated_at=updated["updated_at"],
        ),
        message=f"Opening float for {target_date} set successfully.",
    )


@router.post("/day-book/close", response_model=SuccessResponse[DayBookSessionResponse], dependencies=[admin_guard])
@router.post("/daybook/close", response_model=SuccessResponse[DayBookSessionResponse], dependencies=[admin_guard])
def close_daybook_session(
    payload: DayBookCloseRequest,
    session_date: Optional[str] = Query(None, description="Date YYYY-MM-DD"),
    db: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Reconcile physical cash count, compute variance, and mark cash session CLOSED."""
    target_date = session_date.strip() if session_date else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now_str = datetime.now(timezone.utc).isoformat()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM cash_sessions WHERE session_date = ?;", (target_date,))
    sess = cursor.fetchone()

    if not sess:
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cash session for {target_date} does not exist.",
        )

    if sess["status"] == "CLOSED":
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cash session for {target_date} was already CLOSED at {sess['closed_at']}. Closed sessions are immutable.",
        )

    # Recalculate latest expected cash before locking
    cursor.execute("""
        SELECT COALESCE(SUM(sp.amount_paise), 0)
        FROM sale_payments sp
        JOIN sale_invoices si ON si.id = sp.sale_invoice_id
        WHERE sp.payment_mode = 'CASH'
          AND si.status = 'COMPLETED'
          AND DATE(si.created_at) = ?;
    """, (target_date,))
    cash_sales = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COALESCE(SUM(amount_paise), 0)
        FROM khata_ledger
        WHERE transaction_type = 'PAYMENT'
          AND payment_mode = 'CASH'
          AND DATE(created_at) = ?;
    """, (target_date,))
    cash_deposits = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COALESCE(SUM(refund_amount_paise), 0)
        FROM sales_returns
        WHERE refund_mode = 'CASH'
          AND DATE(created_at) = ?;
    """, (target_date,))
    cash_refunds = cursor.fetchone()[0]

    opening_float = sess["opening_float_paise"]
    expected_cash = opening_float + cash_sales + cash_deposits - cash_refunds
    actual_cash = payload.actual_cash_paise
    variance = actual_cash - expected_cash

    cursor.execute("""
        UPDATE cash_sessions
        SET cash_sales_paise = ?, cash_deposits_paise = ?, cash_refunds_paise = ?,
            expected_cash_paise = ?, actual_cash_paise = ?, variance_paise = ?,
            status = 'CLOSED', closed_by = ?, closed_at = ?, notes = ?, updated_at = ?
        WHERE id = ?;
    """, (
        cash_sales, cash_deposits, cash_refunds,
        expected_cash, actual_cash, variance,
        current_user["id"], now_str, payload.notes, now_str, sess["id"]
    ))
    db.commit()

    cursor.execute("SELECT * FROM cash_sessions WHERE id = ?;", (sess["id"],))
    closed_row = cursor.fetchone()
    cursor.close()

    return SuccessResponse(
        data=DayBookSessionResponse(
            id=closed_row["id"],
            session_date=closed_row["session_date"],
            opening_float_paise=closed_row["opening_float_paise"],
            cash_sales_paise=closed_row["cash_sales_paise"],
            cash_deposits_paise=closed_row["cash_deposits_paise"],
            cash_refunds_paise=closed_row["cash_refunds_paise"],
            expected_cash_paise=closed_row["expected_cash_paise"],
            actual_cash_paise=closed_row["actual_cash_paise"],
            variance_paise=closed_row["variance_paise"],
            status="CLOSED",
            closed_by=current_user["id"],
            closed_by_name=current_user.get("full_name") or current_user.get("username"),
            closed_at=now_str,
            notes=closed_row["notes"],
            created_at=closed_row["created_at"],
            updated_at=now_str,
        ),
        message=f"Cash drawer for {target_date} closed successfully. Variance: {(variance / 100):.2f} INR.",
    )


@router.get("/day-book/history", response_model=SuccessResponse[List[DayBookSessionResponse]], dependencies=[admin_guard])
@router.get("/daybook/history", response_model=SuccessResponse[List[DayBookSessionResponse]], dependencies=[admin_guard])
def get_daybook_history(
    limit: int = Query(30, ge=1, le=100),
    db: sqlite3.Connection = Depends(get_db),
):
    """List historical day-book cash sessions."""
    cursor = db.cursor()
    cursor.execute("""
        SELECT cs.*, u.username, u.full_name
        FROM cash_sessions cs
        LEFT JOIN users u ON u.id = cs.closed_by
        ORDER BY cs.session_date DESC
        LIMIT ?;
    """, (limit,))
    rows = cursor.fetchall()
    cursor.close()

    items = [
        DayBookSessionResponse(
            id=r["id"],
            session_date=r["session_date"],
            opening_float_paise=r["opening_float_paise"],
            cash_sales_paise=r["cash_sales_paise"],
            cash_deposits_paise=r["cash_deposits_paise"],
            cash_refunds_paise=r["cash_refunds_paise"],
            expected_cash_paise=r["expected_cash_paise"],
            actual_cash_paise=r["actual_cash_paise"],
            variance_paise=r["variance_paise"],
            status=r["status"],
            closed_by=r["closed_by"],
            closed_by_name=(r["full_name"] or r["username"]) if "full_name" in r.keys() else None,
            closed_at=r["closed_at"],
            notes=r["notes"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
        for r in rows
    ]
    return SuccessResponse(data=items)
