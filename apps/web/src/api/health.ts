/**
 * Daemon Health and System Diagnostics API client.
 */

import type { SystemHealthResponse } from "@pharmacy/api-contracts";
import { apiClient } from "./client";

export async function getSystemHealth(): Promise<SystemHealthResponse> {
  return apiClient<SystemHealthResponse>("/api/v1/health");
}
