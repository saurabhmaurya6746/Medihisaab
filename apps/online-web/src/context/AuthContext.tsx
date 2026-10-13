import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { softwareApi } from "../api/client";
import type {
  AuthRole,
  ClientUser,
  VendorUser,
  EvaluationSignupPayload,
  EvaluationSignupResponse,
} from "../types";

interface AuthContextType {
  role: AuthRole | null;
  clientUser: ClientUser | null;
  vendorUser: VendorUser | null;
  token: string | null;
  isLoading: boolean;
  login: (credentials: { email: string; password: string }) => Promise<{ role: AuthRole; redirectPath: string }>;
  signup: (payload: EvaluationSignupPayload) => Promise<EvaluationSignupResponse>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

const STORAGE_KEY_TOKEN = "medihisaab_auth_token";
const STORAGE_KEY_ROLE = "medihisaab_auth_role";
const STORAGE_KEY_CLIENT_USER = "medihisaab_client_user";
const STORAGE_KEY_VENDOR_USER = "medihisaab_vendor_user";

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [role, setRole] = useState<AuthRole | null>(null);
  const [clientUser, setClientUser] = useState<ClientUser | null>(null);
  const [vendorUser, setVendorUser] = useState<VendorUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Initialize from storage
  useEffect(() => {
    try {
      const storedToken = localStorage.getItem(STORAGE_KEY_TOKEN);
      const storedRole = localStorage.getItem(STORAGE_KEY_ROLE) as AuthRole | null;

      if (storedToken && storedRole) {
        setToken(storedToken);
        setRole(storedRole);

        if (storedRole === "client") {
          const rawClient = localStorage.getItem(STORAGE_KEY_CLIENT_USER);
          if (rawClient) {
            setClientUser(JSON.parse(rawClient));
          }
        } else if (storedRole === "admin") {
          const rawVendor = localStorage.getItem(STORAGE_KEY_VENDOR_USER);
          if (rawVendor) {
            setVendorUser(JSON.parse(rawVendor));
          }
        }
      }
    } catch {
      // Clear corrupt storage
      localStorage.removeItem(STORAGE_KEY_TOKEN);
      localStorage.removeItem(STORAGE_KEY_ROLE);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const login = useCallback(
    async (credentials: { email: string; password: string }): Promise<{ role: AuthRole; redirectPath: string }> => {
      // 1. First attempt Client Authentication
      try {
        const clientRes = await softwareApi.clientLogin(credentials);
        if (clientRes && clientRes.access_token) {
          const t = clientRes.access_token;
          const user = clientRes.client;

          setToken(t);
          setRole("client");
          setClientUser(user);
          setVendorUser(null);

          localStorage.setItem(STORAGE_KEY_TOKEN, t);
          localStorage.setItem(STORAGE_KEY_ROLE, "client");
          localStorage.setItem(STORAGE_KEY_CLIENT_USER, JSON.stringify(user));
          localStorage.removeItem(STORAGE_KEY_VENDOR_USER);

          return { role: "client", redirectPath: "/client" };
        }
      } catch (err: any) {
        // If client is deactivated/suspended with 403, do not fallback to admin
        if (err.status === 403) {
          throw err;
        }
      }

      // 2. If client auth failed with 401/404, attempt Vendor Admin Authentication
      try {
        const vendorRes = await softwareApi.vendorLogin(credentials);
        if (vendorRes && vendorRes.access_token) {
          const t = vendorRes.access_token;
          const user = vendorRes.user;

          setToken(t);
          setRole("admin");
          setVendorUser(user);
          setClientUser(null);

          localStorage.setItem(STORAGE_KEY_TOKEN, t);
          localStorage.setItem(STORAGE_KEY_ROLE, "admin");
          localStorage.setItem(STORAGE_KEY_VENDOR_USER, JSON.stringify(user));
          localStorage.removeItem(STORAGE_KEY_CLIENT_USER);

          // Also set vendor_token in sessionStorage for vendor portal admin console
          sessionStorage.setItem("vendor_token", t);

          return { role: "admin", redirectPath: "/vendor" };
        }
      } catch (adminErr: any) {
        // If vendor account is deactivated (403), throw that error
        if (adminErr.status === 403) {
          throw adminErr;
        }
      }

      // 3. If both failed, display safe unified error without revealing account existence
      throw new Error("Invalid email or password. Please verify your credentials and try again.");
    },
    []
  );

  const signup = useCallback(
    async (payload: EvaluationSignupPayload): Promise<EvaluationSignupResponse> => {
      const res = await softwareApi.registerTrial(payload);
      if (res && res.access_token) {
        const t = res.access_token;
        const user = res.client;

        setToken(t);
        setRole("client");
        setClientUser(user);
        setVendorUser(null);

        localStorage.setItem(STORAGE_KEY_TOKEN, t);
        localStorage.setItem(STORAGE_KEY_ROLE, "client");
        localStorage.setItem(STORAGE_KEY_CLIENT_USER, JSON.stringify(user));
        localStorage.removeItem(STORAGE_KEY_VENDOR_USER);
      }
      return res;
    },
    []
  );

  const logout = useCallback(() => {
    setToken(null);
    setRole(null);
    setClientUser(null);
    setVendorUser(null);

    localStorage.removeItem(STORAGE_KEY_TOKEN);
    localStorage.removeItem(STORAGE_KEY_ROLE);
    localStorage.removeItem(STORAGE_KEY_CLIENT_USER);
    localStorage.removeItem(STORAGE_KEY_VENDOR_USER);
    sessionStorage.removeItem("vendor_token");
  }, []);

  return (
    <AuthContext.Provider
      value={{
        role,
        clientUser,
        vendorUser,
        token,
        isLoading,
        login,
        signup,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
