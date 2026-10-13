/**
 * System Administration, Automated Hot Backups, Safe Restore, and LAN Configuration Contracts.
 */

// ==========================================
// 1. HOT BACKUPS & MANIFESTS
// ==========================================

export type BackupType = "MANUAL" | "AUTOMATED" | "PRE_RESTORE_SAFETY";

export type BackupStatus = "VALID" | "CORRUPT" | "RESTORED";

export interface BackupManifest {
  id: number;
  filename: string;
  filepath: string;
  file_size_bytes: number;
  sha256_hash: string;
  backup_type: BackupType;
  status: BackupStatus;
  schema_version: number;
  invoice_count: number;
  medicine_count: number;
  revenue_total_paise: number;
  khata_balance_paise: number;
  notes?: string | null;
  created_by?: number | null;
  created_by_name?: string | null;
  created_at: string;
  verified_at?: string | null;
}

export interface BackupCreateInput {
  notes?: string | null;
  backup_type?: BackupType;
}

export interface BackupVerifyResult {
  id: number;
  filename: string;
  is_valid: boolean;
  sha256_hash: string;
  integrity_status: string;
  message: string;
  verified_at: string;
}

// ==========================================
// 2. DISASTER RECOVERY & RESTORE
// ==========================================

export interface RestorePreviewResponse {
  staging_token: string;
  filename: string;
  created_at: string;
  schema_version: number;
  invoice_count: number;
  medicine_count: number;
  revenue_total_paise: number;
  khata_balance_paise: number;
  sha256_hash: string;
  integrity_status: string;
  is_compatible: boolean;
  message: string;
}

export interface RestoreExecuteInput {
  staging_token: string;
  confirm: boolean;
}

export interface RestoreExecuteResult {
  success: boolean;
  message: string;
  safety_backup_filename: string;
  restored_schema_version: number;
  restored_at: string;
}

// ==========================================
// 3. SYSTEM CONFIG & LAN DISCOVERY
// ==========================================

export type ServerMode = "STANDALONE" | "LAN_SERVER";

export interface SystemConfigItem {
  key: string;
  value: string;
  description?: string | null;
  is_secret: boolean;
  updated_at: string;
}

export interface SystemConfigUpdateInput {
  configs: Record<string, string>;
}

export interface SystemConfigResponse {
  configs: Record<string, string>;
}

export interface SystemDiscoveryInfo {
  server_name: string;
  version: string;
  server_mode: ServerMode;
  host: string;
  port: number;
  lan_ips: string[];
  database_status: string;
  database_size_kb: number;
  uptime_seconds: number;
  platform: string;
  mdns_enabled: boolean;
}

export type SystemDiscoveryResponse = SystemDiscoveryInfo;
