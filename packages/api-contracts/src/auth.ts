/**
 * Authentication, Session Tokens, User Profiles, and First-Run Setup Contracts.
 */

import type { UserRole } from "./roles";

/**
 * System initialization / first-run state check.
 * Used before any user exists to guide the operator to the setup wizard.
 */
export interface SystemSetupStatusResponse {
  is_initialized: boolean;
  admin_count: number;
  store_name?: string | null;
}

/**
 * Payload for the one-time first-run setup wizard.
 */
export interface FirstRunSetupInput {
  username: string;
  full_name: string;
  password: string;
  confirm_password: string;
  pin?: string | null; // Optional 4-digit PIN for quick cashier unlock
  store_name: string;
  store_address?: string | null;
  store_phone?: string | null;
  store_dl_number_20b?: string | null;
  store_dl_number_21b?: string | null;
  store_gstin?: string | null;
}

/**
 * Public User entity model.
 */
export interface User {
  id: number;
  username: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  has_pin: boolean;
  created_at: string;
  updated_at?: string | null;
}

/**
 * Input for creating secondary operator accounts by an Admin.
 */
export interface CreateUserInput {
  username: string;
  full_name: string;
  password: string;
  pin?: string | null;
  role: UserRole;
}

/**
 * Input for updating user details.
 */
export interface UpdateUserInput {
  full_name?: string;
  role?: UserRole;
  is_active?: boolean;
}

/**
 * Password login request.
 */
export interface LoginInput {
  username: string;
  password: string;
}

/**
 * Quick PIN switch request for counter operators.
 */
export interface PinUnlockInput {
  pin: string;
  user_id?: number | null; // Optional if PIN is uniquely associated or selecting active operator
}

/**
 * JWT Bearer token authentication response.
 */
export interface AuthTokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in_seconds: number;
  user: User;
}

/**
 * Self-service credential update payloads.
 */
export interface ChangePasswordInput {
  current_password: string;
  new_password: string;
  confirm_new_password: string;
}

export interface SetPinInput {
  current_password: string;
  new_pin: string;
}

/**
 * Frontend client session state interface.
 */
export interface SessionState {
  isAuthenticated: boolean;
  user: User | null;
  token: string | null;
  requiresSetup: boolean;
}
