/**
 * Authentication and Setup API functions typed against @pharmacy/api-contracts.
 */

import type {
  SystemSetupStatusResponse,
  FirstRunSetupInput,
  LoginInput,
  PinUnlockInput,
  AuthTokenResponse,
  User,
} from "@pharmacy/api-contracts";
import { apiClient } from "./client";

export async function getSetupStatus(): Promise<SystemSetupStatusResponse> {
  return apiClient<SystemSetupStatusResponse>("/api/v1/auth/setup-status");
}

export async function firstRunSetup(payload: FirstRunSetupInput): Promise<AuthTokenResponse> {
  return apiClient<AuthTokenResponse>("/api/v1/auth/first-run-setup", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function login(payload: LoginInput): Promise<AuthTokenResponse> {
  return apiClient<AuthTokenResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function pinSwitch(payload: PinUnlockInput): Promise<AuthTokenResponse> {
  return apiClient<AuthTokenResponse>("/api/v1/auth/pin-switch", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getCurrentUser(): Promise<User> {
  return apiClient<User>("/api/v1/auth/me");
}
