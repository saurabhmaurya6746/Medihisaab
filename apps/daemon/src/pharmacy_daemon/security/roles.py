"""User role definitions and permission matrix matching api-contracts."""

from enum import Enum
from typing import Dict, List, Set


class UserRole(str, Enum):
    """System user roles."""

    ADMIN = "ADMIN"
    PHARMACIST = "PHARMACIST"
    CASHIER = "CASHIER"


ROLE_PERMISSIONS: Dict[UserRole, Set[str]] = {
    UserRole.ADMIN: {
        "MANAGE_USERS",
        "MANAGE_SETTINGS",
        "EDIT_PURCHASE_RATES",
        "CANCEL_INVOICE",
        "RESTORE_BACKUP",
        "TRIGGER_BACKUP",
        "DISPENSE_SCHEDULE_H1",
        "COUNTER_BILLING",
        "VIEW_REPORTS",
        "VIEW_PROFIT_MARGINS",
        "OVERRIDE_CREDIT_LIMIT",
        "RECORD_KHATA_DEPOSIT",
        "MANAGE_MASTERS",
        "STOCK_AUDIT",
    },
    UserRole.PHARMACIST: {
        "TRIGGER_BACKUP",
        "DISPENSE_SCHEDULE_H1",
        "COUNTER_BILLING",
        "VIEW_REPORTS",
        "RECORD_KHATA_DEPOSIT",
        "MANAGE_MASTERS",
        "STOCK_AUDIT",
    },
    UserRole.CASHIER: {
        "COUNTER_BILLING",
        "RECORD_KHATA_DEPOSIT",
    },
}


def has_permission(role: str, permission: str) -> bool:
    """Validate if a role possesses a specified operational permission."""
    try:
        user_role = UserRole(role)
        return permission in ROLE_PERMISSIONS.get(user_role, set())
    except ValueError:
        return False
