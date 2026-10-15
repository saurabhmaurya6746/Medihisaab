import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import type {
  User,
  FirstRunSetupInput,
  LoginInput,
  OwnerLoginInput,
  PinUnlockInput,
  AuthTokenResponse,
  SystemSetupStatusResponse,
} from "@pharmacy/api-contracts";
import * as authApi from "../api/auth";
import { getStoredToken, setStoredToken, clearStoredToken, ApiError } from "../api/client";

interface AuthContextValue {
  user: User | null;
  storeName: string | null;
  isInitialized: boolean | null;
  isLoading: boolean;
  error: string | null;
  refreshSession: () => Promise<void>;
  performLogin: (input: LoginInput) => Promise<void>;
  performOwnerLogin: (input: OwnerLoginInput) => Promise<AuthTokenResponse>;
  performPinSwitch: (input: PinUnlockInput) => Promise<void>;
  performFirstRunSetup: (input: FirstRunSetupInput) => Promise<void>;
  performLogout: () => void;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [storeName, setStoreName] = useState<string | null>(null);
  const [isInitialized, setIsInitialized] = useState<boolean | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const refreshSession = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      // 1. Check whether database has been initialized with an admin
      const statusRes: SystemSetupStatusResponse = await authApi.getSetupStatus();
      setIsInitialized(statusRes.is_initialized);
      if (statusRes.store_name) {
        setStoreName(statusRes.store_name);
      }

      if (!statusRes.is_initialized) {
        setUser(null);
        clearStoredToken();
        setIsLoading(false);
        return;
      }

      // 2. If token exists in sessionStorage, validate with /api/v1/auth/me
      const token = getStoredToken();
      if (token) {
        try {
          const profile = await authApi.getCurrentUser();
          setUser(profile);
        } catch {
          // Token is expired or invalid
          clearStoredToken();
          setUser(null);
        }
      } else {
        setUser(null);
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("An unexpected error occurred while connecting to the system.");
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshSession();

    const handleUnauthorized = () => {
      setUser(null);
      clearStoredToken();
    };

    window.addEventListener("pos:unauthorized", handleUnauthorized);
    return () => {
      window.removeEventListener("pos:unauthorized", handleUnauthorized);
    };
  }, [refreshSession]);

  const performLogin = async (input: LoginInput) => {
    setIsLoading(true);
    setError(null);
    try {
      const resp = await authApi.login(input);
      setStoredToken(resp.access_token);
      setUser(resp.user);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.message);
        throw err;
      }
      const genericMsg = err instanceof Error ? err.message : "Failed to log in.";
      setError(genericMsg);
      throw new Error(genericMsg);
    } finally {
      setIsLoading(false);
    }
  };

  const performOwnerLogin = async (input: OwnerLoginInput): Promise<AuthTokenResponse> => {
    setIsLoading(true);
    setError(null);
    try {
      const resp = await authApi.ownerLogin(input);
      setStoredToken(resp.access_token);
      setUser(resp.user);
      return resp;
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.message);
        throw err;
      }
      const genericMsg = err instanceof Error ? err.message : "Failed to sign in as owner.";
      setError(genericMsg);
      throw new Error(genericMsg);
    } finally {
      setIsLoading(false);
    }
  };

  const performPinSwitch = async (input: PinUnlockInput) => {
    setIsLoading(true);
    setError(null);
    try {
      const resp = await authApi.pinSwitch(input);
      setStoredToken(resp.access_token);
      setUser(resp.user);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.message);
        throw err;
      }
      const genericMsg = err instanceof Error ? err.message : "Failed to switch PIN.";
      setError(genericMsg);
      throw new Error(genericMsg);
    } finally {
      setIsLoading(false);
    }
  };

  const performFirstRunSetup = async (input: FirstRunSetupInput) => {
    setIsLoading(true);
    setError(null);
    try {
      const resp = await authApi.firstRunSetup(input);
      setStoredToken(resp.access_token);
      setUser(resp.user);
      setIsInitialized(true);
      setStoreName(input.store_name);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.message);
        throw err;
      }
      const genericMsg = err instanceof Error ? err.message : "First-run setup failed.";
      setError(genericMsg);
      throw new Error(genericMsg);
    } finally {
      setIsLoading(false);
    }
  };

  const performLogout = () => {
    clearStoredToken();
    setUser(null);
    setError(null);
  };

  const clearError = () => {
    setError(null);
  };

  const value: AuthContextValue = {
    user,
    storeName,
    isInitialized,
    isLoading,
    error,
    refreshSession,
    performLogin,
    performOwnerLogin,
    performPinSwitch,
    performFirstRunSetup,
    performLogout,
    clearError,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
