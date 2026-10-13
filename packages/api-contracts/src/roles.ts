/**
 * Role-Based Access Control (RBAC) definitions and permission matrices.
 */

export const USER_ROLES = ["ADMIN", "PHARMACIST", "CASHIER"] as const;
export type UserRole = (typeof USER_ROLES)[number];

export const PERMISSIONS = [
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
] as const;

export type Permission = (typeof PERMISSIONS)[number];

export const ROLE_PERMISSIONS: Record<UserRole, readonly Permission[]> = {
  ADMIN: [
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
  ],
  PHARMACIST: [
    "TRIGGER_BACKUP",
    "DISPENSE_SCHEDULE_H1",
    "COUNTER_BILLING",
    "VIEW_REPORTS",
    "RECORD_KHATA_DEPOSIT",
    "MANAGE_MASTERS",
    "STOCK_AUDIT",
  ],
  CASHIER: [
    "COUNTER_BILLING",
    "RECORD_KHATA_DEPOSIT",
  ],
} as const;

/**
 * Check if a role possesses a specific permission.
 */
export function hasPermission(role: UserRole, permission: Permission): boolean {
  const permissions = ROLE_PERMISSIONS[role];
  return permissions ? permissions.includes(permission) : false;
}

export interface RoleMetadata {
  role: UserRole;
  display_name: string;
  description: string;
}

export const ROLE_METADATA: Record<UserRole, RoleMetadata> = {
  ADMIN: {
    role: "ADMIN",
    display_name: "Store Owner / Administrator",
    description: "Complete control over master catalog, user permissions, profit margins, and backups",
  },
  PHARMACIST: {
    role: "PHARMACIST",
    display_name: "Registered Pharmacist",
    description: "Dispensing authority, Schedule H1 logging, stock audits, and catalog updates",
  },
  CASHIER: {
    role: "CASHIER",
    display_name: "Billing Cashier",
    description: "High-velocity counter sales billing, tender processing, and Khata deposit collections",
  },
};
