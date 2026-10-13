import { apiClient, getStoredToken } from "./client";
import type {
  ApiSuccessEnvelope,
  BackupManifest,
  BackupCreateInput,
  BackupVerifyResult,
  RestorePreviewResponse,
  RestoreExecuteResult,
  SystemDiscoveryResponse,
  SystemConfigResponse,
} from "@pharmacy/api-contracts";

// 1. Backups & Manifests
export async function listBackups(): Promise<BackupManifest[]> {
  const res = await apiClient<ApiSuccessEnvelope<BackupManifest[]>>("/api/v1/system/backups");
  return res.data;
}

export async function createBackup(input: BackupCreateInput): Promise<BackupManifest> {
  const res = await apiClient<ApiSuccessEnvelope<BackupManifest>>("/api/v1/system/backups", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return res.data;
}

export async function verifyBackup(backupId: number): Promise<BackupVerifyResult> {
  const res = await apiClient<ApiSuccessEnvelope<BackupVerifyResult>>(`/api/v1/system/backups/${backupId}/verify`);
  return res.data;
}

export async function downloadBackupArchive(backupId: number, defaultFilename: string): Promise<void> {
  const token = getStoredToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`/api/v1/system/backups/${backupId}/download`, { headers });
  if (!response.ok) {
    throw new Error(`Failed to download backup archive (${response.status})`);
  }

  const blob = await response.blob();
  const downloadUrl = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = downloadUrl;
  a.download = defaultFilename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(downloadUrl);
}

// 2. Disaster Recovery & Safe Restore
export async function previewRestore(params: { backupId?: number; file?: File }): Promise<RestorePreviewResponse> {
  const token = getStoredToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const formData = new FormData();
  if (params.backupId) {
    formData.append("backup_id", String(params.backupId));
  }
  if (params.file) {
    formData.append("file", params.file);
  }

  const response = await fetch("/api/v1/system/restore/preview", {
    method: "POST",
    headers,
    body: formData,
  });

  const body = await response.json();
  if (!response.ok || !body.success) {
    throw new Error(body.detail || body.error?.message || "Failed to inspect backup package");
  }

  return body.data;
}

export async function executeRestore(stagingToken: string, confirm: boolean): Promise<RestoreExecuteResult> {
  const res = await apiClient<ApiSuccessEnvelope<RestoreExecuteResult>>("/api/v1/system/restore/execute", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ staging_token: stagingToken, confirm }),
  });
  return res.data;
}

// 3. System Configuration & Store Settings
export async function getSystemConfig(): Promise<Record<string, string>> {
  const res = await apiClient<ApiSuccessEnvelope<SystemConfigResponse>>("/api/v1/system/config");
  return res.data.configs;
}

export async function updateSystemConfig(configs: Record<string, string>): Promise<Record<string, string>> {
  const res = await apiClient<ApiSuccessEnvelope<SystemConfigResponse>>("/api/v1/system/config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ configs }),
  });
  return res.data.configs;
}

// 4. LAN Discovery & Telemetry
export async function getSystemDiscovery(): Promise<SystemDiscoveryResponse> {
  const res = await apiClient<ApiSuccessEnvelope<SystemDiscoveryResponse>>("/api/v1/system/discovery");
  return res.data;
}

// 5. Offline Client Licensing
export interface LicenseStatusInfo {
  is_valid: boolean;
  status: string;
  client_name: string;
  license_id: string;
  terminal_count: number;
  activation_date: string;
  expiry_date: string | null;
  edition: string;
  message: string;
  remaining_days?: number | null;
  grace_period_active?: boolean;
}

export async function getLicenseStatus(): Promise<LicenseStatusInfo> {
  const res = await apiClient<ApiSuccessEnvelope<LicenseStatusInfo>>("/api/v1/system/license");
  return res.data;
}

export async function importLicense(payload: Record<string, unknown>): Promise<LicenseStatusInfo> {
  const res = await apiClient<ApiSuccessEnvelope<LicenseStatusInfo>>("/api/v1/system/license", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.data;
}

