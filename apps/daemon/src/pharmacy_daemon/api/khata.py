"""Customer Khata ledger, deposits, receipts, and aging analysis router."""

from datetime import datetime, timezone
import math
import sqlite3
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..security.roles import UserRole
from .dependencies import get_db, get_current_user, require_role, require_write_role
from .schemas import (
    CustomerAgingBucketResponse,
    CustomerAgingReportResponse,
    CustomerDepositReceiptResponse,
    CustomerDepositRequest,
    KhataLedgerEntryResponse,
    PaginatedData,
    SuccessResponse,
)

router = APIRouter(prefix="/api/v1/customers", tags=["Customer Khata & Ledger"])

read_guard = Depends(require_role(UserRole.ADMIN, UserRole.PHARMACIST, UserRole.CASHIER))
write_guard = Depends(require_write_role(UserRole.ADMIN, UserRole.PHARMACIST, UserRole.CASHIER))


# ==========================================
# 1. CUSTOMER AGING BUCKET REPORT
# ==========================================

@router.get("/aging", response_model=SuccessResponse[CustomerAgingReportResponse], dependencies=[read_guard])
def get_customer_aging_report(
    db: sqlite3.Connection = Depends(get_db),
):
    """Calculate customer debt aging in 0-30, 31-60, and 60+ day buckets."""
    cursor = db.cursor()

    cursor.execute("""
        SELECT id, name, phone, credit_limit_paise, current_balance_paise
        FROM customers
        WHERE is_active = 1 AND current_balance_paise > 0
        ORDER BY current_balance_paise DESC, name ASC;
    """)
    debtor_rows = cursor.fetchall()

    now = datetime.now(timezone.utc)
    buckets: List[CustomerAgingBucketResponse] = []

    total_outstanding_paise = 0
    total_0_30_paise = 0
    total_31_60_paise = 0
    total_60_plus_paise = 0

    for cust in debtor_rows:
        cust_id = cust["id"]
        total_debt = cust["current_balance_paise"]
        total_outstanding_paise += total_debt

        # Fetch debits (credit sales) in chronological order
        cursor.execute("""
            SELECT amount_paise, created_at
            FROM khata_ledger
            WHERE customer_id = ? AND entry_type = 'DEBIT'
            ORDER BY created_at ASC;
        """, (cust_id,))
        debit_entries = cursor.fetchall()

        # Fetch total credits (payments and return refunds)
        cursor.execute("""
            SELECT COALESCE(SUM(amount_paise), 0) AS total_credits
            FROM khata_ledger
            WHERE customer_id = ? AND entry_type = 'CREDIT';
        """, (cust_id,))
        credits_row = cursor.fetchone()
        remaining_credits = credits_row["total_credits"] if credits_row else 0

        # Fetch last payment date
        cursor.execute("""
            SELECT created_at
            FROM khata_ledger
            WHERE customer_id = ? AND transaction_type = 'PAYMENT'
            ORDER BY created_at DESC
            LIMIT 1;
        """, (cust_id,))
        last_pay_row = cursor.fetchone()
        last_payment_date = last_pay_row["created_at"] if last_pay_row else None

        # Allocate credits against oldest debits (FIFO)
        b0_30 = 0
        b31_60 = 0
        b60_plus = 0

        unallocated_balance = total_debt

        if debit_entries:
            for d in debit_entries:
                d_amount = d["amount_paise"]
                if remaining_credits >= d_amount:
                    # Fully covered by prior payments
                    remaining_credits -= d_amount
                    continue
                elif remaining_credits > 0:
                    # Partially covered
                    unpaid_part = d_amount - remaining_credits
                    remaining_credits = 0
                else:
                    unpaid_part = d_amount

                if unallocated_balance <= 0:
                    break

                unpaid_part = min(unpaid_part, unallocated_balance)
                unallocated_balance -= unpaid_part

                # Age categorization
                try:
                    d_dt = datetime.fromisoformat(d["created_at"].replace("Z", "+00:00"))
                    age_days = (now - d_dt).days
                except Exception:
                    age_days = 0

                if age_days <= 30:
                    b0_30 += unpaid_part
                elif age_days <= 60:
                    b31_60 += unpaid_part
                else:
                    b60_plus += unpaid_part

        # If any debt remains unallocated (e.g., legacy balance without ledger entry), put in 0-30
        if unallocated_balance > 0:
            b0_30 += unallocated_balance

        total_0_30_paise += b0_30
        total_31_60_paise += b31_60
        total_60_plus_paise += b60_plus

        buckets.append(
            CustomerAgingBucketResponse(
                customer_id=cust_id,
                customer_name=cust["name"],
                customer_phone=cust["phone"],
                total_outstanding_paise=total_debt,
                credit_limit_paise=cust["credit_limit_paise"],
                bucket_0_30_paise=b0_30,
                bucket_31_60_paise=b31_60,
                bucket_60_plus_paise=b60_plus,
                last_payment_date=last_payment_date,
            )
        )

    cursor.close()

    report = CustomerAgingReportResponse(
        total_customers=len(buckets),
        total_outstanding_paise=total_outstanding_paise,
        total_0_30_paise=total_0_30_paise,
        total_31_60_paise=total_31_60_paise,
        total_60_plus_paise=total_60_plus_paise,
        customers=buckets,
    )
    return SuccessResponse(data=report)


# ==========================================
# 2. CUSTOMER KHATA LEDGER HISTORY
# ==========================================

@router.get("/{id}/khata", response_model=SuccessResponse[PaginatedData[KhataLedgerEntryResponse]], dependencies=[read_guard])
def get_customer_khata_ledger(
    id: int,
    entry_type: Optional[str] = Query(None, description="Filter by DEBIT or CREDIT"),
    transaction_type: Optional[str] = Query(None, description="Filter by transaction type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: sqlite3.Connection = Depends(get_db),
):
    """Fetch paginated chronological ledger entries for a customer."""
    cursor = db.cursor()

    # Check customer exists
    cursor.execute("SELECT id, name FROM customers WHERE id = ?;", (id,))
    cust = cursor.fetchone()
    if not cust:
        cursor.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Customer #{id} not found.")

    conditions = ["k.customer_id = ?"]
    params: List[Any] = [id]

    if entry_type:
        conditions.append("k.entry_type = ?")
        params.append(entry_type.upper())

    if transaction_type:
        conditions.append("k.transaction_type = ?")
        params.append(transaction_type.upper())

    where_sql = f"WHERE {' AND '.join(conditions)}"

    cursor.execute(f"SELECT COUNT(*) FROM khata_ledger k {where_sql};", params)
    total = cursor.fetchone()[0]

    offset = (page - 1) * page_size
    cursor.execute(
        f"""
        SELECT k.id, k.customer_id, c.name AS customer_name, k.transaction_type, k.entry_type,
               k.amount_paise, k.balance_paise, k.payment_mode, k.reference_type, k.reference_id,
               k.receipt_no, k.notes, k.user_id, u.username, k.created_at
        FROM khata_ledger k
        JOIN customers c ON c.id = k.customer_id
        LEFT JOIN users u ON u.id = k.user_id
        {where_sql}
        ORDER BY k.created_at DESC, k.id DESC
        LIMIT ? OFFSET ?;
        """,
        params + [page_size, offset],
    )
    rows = cursor.fetchall()
    cursor.close()

    items = [
        KhataLedgerEntryResponse(
            id=r["id"],
            customer_id=r["customer_id"],
            customer_name=r["customer_name"],
            transaction_type=r["transaction_type"],
            entry_type=r["entry_type"],
            amount_paise=r["amount_paise"],
            balance_paise=r["balance_paise"],
            payment_mode=r["payment_mode"],
            reference_type=r["reference_type"],
            reference_id=r["reference_id"],
            receipt_no=r["receipt_no"],
            notes=r["notes"],
            user_id=r["user_id"],
            username=r["username"],
            created_at=r["created_at"],
        )
        for r in rows
    ]

    total_pages = math.ceil(total / page_size) if total > 0 else 1
    return SuccessResponse(
        data=PaginatedData(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)
    )


# ==========================================
# 3. GET CURRENT CUSTOMER BALANCE
# ==========================================

@router.get("/{id}/balance", response_model=SuccessResponse[Dict[str, Any]], dependencies=[read_guard])
def get_customer_balance(id: int, db: sqlite3.Connection = Depends(get_db)):
    """Fetch current Khata balance, credit limit, and available headroom."""
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT id, name, phone, credit_limit_paise, current_balance_paise, is_active
        FROM customers WHERE id = ?;
        """,
        (id,),
    )
    cust = cursor.fetchone()
    cursor.close()

    if not cust:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Customer #{id} not found.")

    curr_bal = cust["current_balance_paise"]
    limit = cust["credit_limit_paise"]
    available_credit = max(0, limit - curr_bal)

    return SuccessResponse(
        data={
            "customer_id": cust["id"],
            "name": cust["name"],
            "phone": cust["phone"],
            "current_balance_paise": curr_bal,
            "credit_limit_paise": limit,
            "available_credit_paise": available_credit,
            "is_credit_exceeded": curr_bal > limit,
            "is_active": bool(cust["is_active"]),
        }
    )


# ==========================================
# 4. CUSTOMER PAYMENT / DEPOSIT ENTRY
# ==========================================

@router.post("/{id}/payments", response_model=SuccessResponse[CustomerDepositReceiptResponse], status_code=status.HTTP_201_CREATED, dependencies=[write_guard])
def record_customer_payment(
    id: int,
    payload: CustomerDepositRequest,
    db: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Record customer cash/UPI deposit to settle Khata balance with atomic ledger commit."""
    if payload.amount_paise <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Deposit amount must be strictly greater than zero.",
        )

    now = datetime.now(timezone.utc)
    now_str = now.isoformat()
    receipt_date_str = now.strftime("%Y%m%d")
    unique_suffix = uuid.uuid4().hex[:6].upper()
    receipt_no = f"RCP-{receipt_date_str}-{unique_suffix}"

    cursor = db.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE;")

        cursor.execute(
            "SELECT id, name, phone, current_balance_paise, is_active FROM customers WHERE id = ?;",
            (id,),
        )
        cust = cursor.fetchone()
        if not cust:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Customer #{id} not found.")

        if not cust["is_active"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Customer '{cust['name']}' is inactive.")

        prev_balance = cust["current_balance_paise"]
        new_balance = prev_balance - payload.amount_paise

        # Update customer balance
        cursor.execute(
            "UPDATE customers SET current_balance_paise = ?, updated_at = ? WHERE id = ?;",
            (new_balance, now_str, id),
        )

        # Append to khata_ledger
        cursor.execute(
            """
            INSERT INTO khata_ledger (
                customer_id, transaction_type, entry_type, amount_paise, balance_paise,
                payment_mode, reference_type, receipt_no, notes, user_id, created_at
            ) VALUES (?, 'PAYMENT', 'CREDIT', ?, ?, ?, 'CUSTOMER_DEPOSIT', ?, ?, ?, ?);
            """,
            (
                id,
                payload.amount_paise,
                new_balance,
                payload.payment_mode,
                receipt_no,
                payload.notes,
                current_user["id"],
                now_str,
            ),
        )

        cursor.execute("COMMIT;")
    except HTTPException:
        cursor.execute("ROLLBACK;")
        cursor.close()
        raise
    except Exception as e:
        cursor.execute("ROLLBACK;")
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record customer payment: {e}",
        ) from e

    receipt = CustomerDepositReceiptResponse(
        receipt_no=receipt_no,
        customer_id=id,
        customer_name=cust["name"],
        customer_phone=cust["phone"],
        amount_paise=payload.amount_paise,
        previous_balance_paise=prev_balance,
        new_balance_paise=new_balance,
        payment_mode=payload.payment_mode,
        notes=payload.notes,
        operator_name=current_user.get("full_name") or current_user.get("username"),
        created_at=now_str,
    )
    return SuccessResponse(data=receipt, message="Payment successfully recorded.")


# ==========================================
# 5. FETCH RECEIPT DETAILS BY RECEIPT NO
# ==========================================

@router.get("/receipts/{receipt_no}", response_model=SuccessResponse[CustomerDepositReceiptResponse], dependencies=[read_guard])
def get_customer_receipt(receipt_no: str, db: sqlite3.Connection = Depends(get_db)):
    """Fetch deposit receipt details for receipt preview or thermal reprint."""
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT k.receipt_no, k.customer_id, c.name AS customer_name, c.phone AS customer_phone,
               k.amount_paise, k.balance_paise, k.payment_mode, k.notes, u.full_name, u.username, k.created_at
        FROM khata_ledger k
        JOIN customers c ON c.id = k.customer_id
        LEFT JOIN users u ON u.id = k.user_id
        WHERE k.receipt_no = ?;
        """,
        (receipt_no,),
    )
    row = cursor.fetchone()
    cursor.close()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Receipt '{receipt_no}' not found.")

    new_bal = row["balance_paise"]
    amt = row["amount_paise"]
    prev_bal = new_bal + amt

    receipt = CustomerDepositReceiptResponse(
        receipt_no=row["receipt_no"],
        customer_id=row["customer_id"],
        customer_name=row["customer_name"],
        customer_phone=row["customer_phone"],
        amount_paise=amt,
        previous_balance_paise=prev_bal,
        new_balance_paise=new_bal,
        payment_mode=row["payment_mode"] or "CASH",
        notes=row["notes"],
        operator_name=row["full_name"] or row["username"],
        created_at=row["created_at"],
    )
    return SuccessResponse(data=receipt)
