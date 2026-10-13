import React, { createContext, useContext, useState, useEffect, useCallback } from "react";

export type AppTheme = "dark" | "light" | "system";

export interface ModuleSettings {
  medicines: boolean;
  suppliers: boolean;
  purchases: boolean;
  customers: boolean;
  inventory: boolean;
  stockAudit: boolean;
  khata: boolean;
  salesReturns: boolean;
  purchaseReturns: boolean;
  wastage: boolean;
  reports: boolean;
}

export interface POSPreferences {
  autoPrintReceipt: boolean;
  barcodeScanner: boolean;
  lowStockAlerts: boolean;
  expiryAlerts: boolean;
  allowDiscounts: boolean;
  allowCreditSales: boolean;
}

export interface AppSettings {
  theme: AppTheme;
  modules: ModuleSettings;
  preferences: POSPreferences;
}

export const DEFAULT_SETTINGS: AppSettings = {
  theme: "dark",
  modules: {
    medicines: true,
    suppliers: true,
    purchases: true,
    customers: true,
    inventory: true,
    stockAudit: true,
    khata: true,
    salesReturns: true,
    purchaseReturns: true,
    wastage: true,
    reports: true,
  },
  preferences: {
    autoPrintReceipt: false,
    barcodeScanner: true,
    lowStockAlerts: true,
    expiryAlerts: true,
    allowDiscounts: true,
    allowCreditSales: true,
  },
};

const SETTINGS_STORAGE_KEY = "pharmacy-pos-settings";
const THEME_STORAGE_KEY = "pharmacy-pos-theme";

interface SettingsContextValue {
  settings: AppSettings;
  resolvedTheme: "dark" | "light";
  updateSettings: (newSettings: AppSettings) => void;
  resetSettings: () => void;
  isModuleEnabled: (moduleKey: keyof ModuleSettings) => boolean;
  isPreferenceEnabled: (prefKey: keyof POSPreferences) => boolean;
}

const SettingsContext = createContext<SettingsContextValue | undefined>(undefined);

function resolveSystemTheme(): "dark" | "light" {
  if (typeof window !== "undefined" && window.matchMedia) {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return "dark";
}

function loadInitialSettings(): AppSettings {
  if (typeof window === "undefined") {
    return DEFAULT_SETTINGS;
  }

  try {
    const raw = localStorage.getItem(SETTINGS_STORAGE_KEY);
    const storedTheme = localStorage.getItem(THEME_STORAGE_KEY);

    if (!raw) {
      const initial = { ...DEFAULT_SETTINGS };
      if (storedTheme === "dark" || storedTheme === "light" || storedTheme === "system") {
        initial.theme = storedTheme;
      }
      return initial;
    }

    const parsed = JSON.parse(raw);
    const validTheme: AppTheme =
      parsed.theme === "dark" || parsed.theme === "light" || parsed.theme === "system"
        ? parsed.theme
        : storedTheme === "dark" || storedTheme === "light" || storedTheme === "system"
        ? (storedTheme as AppTheme)
        : DEFAULT_SETTINGS.theme;

    return {
      theme: validTheme,
      modules: {
        medicines: typeof parsed.modules?.medicines === "boolean" ? parsed.modules.medicines : DEFAULT_SETTINGS.modules.medicines,
        suppliers: typeof parsed.modules?.suppliers === "boolean" ? parsed.modules.suppliers : DEFAULT_SETTINGS.modules.suppliers,
        purchases: typeof parsed.modules?.purchases === "boolean" ? parsed.modules.purchases : DEFAULT_SETTINGS.modules.purchases,
        customers: typeof parsed.modules?.customers === "boolean" ? parsed.modules.customers : DEFAULT_SETTINGS.modules.customers,
        inventory: typeof parsed.modules?.inventory === "boolean" ? parsed.modules.inventory : DEFAULT_SETTINGS.modules.inventory,
        stockAudit: typeof parsed.modules?.stockAudit === "boolean" ? parsed.modules.stockAudit : DEFAULT_SETTINGS.modules.stockAudit,
        khata: typeof parsed.modules?.khata === "boolean" ? parsed.modules.khata : DEFAULT_SETTINGS.modules.khata,
        salesReturns: typeof parsed.modules?.salesReturns === "boolean" ? parsed.modules.salesReturns : DEFAULT_SETTINGS.modules.salesReturns,
        purchaseReturns: typeof parsed.modules?.purchaseReturns === "boolean" ? parsed.modules.purchaseReturns : DEFAULT_SETTINGS.modules.purchaseReturns,
        wastage: typeof parsed.modules?.wastage === "boolean" ? parsed.modules.wastage : DEFAULT_SETTINGS.modules.wastage,
        reports: typeof parsed.modules?.reports === "boolean" ? parsed.modules.reports : DEFAULT_SETTINGS.modules.reports,
      },
      preferences: {
        autoPrintReceipt: typeof parsed.preferences?.autoPrintReceipt === "boolean" ? parsed.preferences.autoPrintReceipt : DEFAULT_SETTINGS.preferences.autoPrintReceipt,
        barcodeScanner: typeof parsed.preferences?.barcodeScanner === "boolean" ? parsed.preferences.barcodeScanner : DEFAULT_SETTINGS.preferences.barcodeScanner,
        lowStockAlerts: typeof parsed.preferences?.lowStockAlerts === "boolean" ? parsed.preferences.lowStockAlerts : DEFAULT_SETTINGS.preferences.lowStockAlerts,
        expiryAlerts: typeof parsed.preferences?.expiryAlerts === "boolean" ? parsed.preferences.expiryAlerts : DEFAULT_SETTINGS.preferences.expiryAlerts,
        allowDiscounts: typeof parsed.preferences?.allowDiscounts === "boolean" ? parsed.preferences.allowDiscounts : DEFAULT_SETTINGS.preferences.allowDiscounts,
        allowCreditSales: typeof parsed.preferences?.allowCreditSales === "boolean" ? parsed.preferences.allowCreditSales : DEFAULT_SETTINGS.preferences.allowCreditSales,
      },
    };
  } catch (err) {
    console.error("Failed to parse settings from localStorage:", err);
    return DEFAULT_SETTINGS;
  }
}

export const SettingsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [settings, setSettings] = useState<AppSettings>(loadInitialSettings);
  const [systemScheme, setSystemScheme] = useState<"dark" | "light">(resolveSystemTheme);

  // Listen to OS color scheme changes
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

    const handleChange = (e: MediaQueryListEvent) => {
      setSystemScheme(e.matches ? "dark" : "light");
    };

    mediaQuery.addEventListener("change", handleChange);
    return () => {
      mediaQuery.removeEventListener("change", handleChange);
    };
  }, []);

  const resolvedTheme: "dark" | "light" =
    settings.theme === "system" ? systemScheme : settings.theme;

  // Apply data-theme attribute on document root whenever resolvedTheme changes
  useEffect(() => {
    if (typeof document !== "undefined") {
      document.documentElement.setAttribute("data-theme", resolvedTheme);
    }
  }, [resolvedTheme]);

  const updateSettings = useCallback((newSettings: AppSettings) => {
    setSettings(newSettings);
    try {
      localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(newSettings));
      localStorage.setItem(THEME_STORAGE_KEY, newSettings.theme);
    } catch (err) {
      console.error("Failed to write settings to localStorage:", err);
    }
  }, []);

  const resetSettings = useCallback(() => {
    updateSettings(DEFAULT_SETTINGS);
  }, [updateSettings]);

  const isModuleEnabled = useCallback(
    (moduleKey: keyof ModuleSettings): boolean => {
      return settings.modules[moduleKey] ?? true;
    },
    [settings.modules]
  );

  const isPreferenceEnabled = useCallback(
    (prefKey: keyof POSPreferences): boolean => {
      return settings.preferences[prefKey] ?? false;
    },
    [settings.preferences]
  );

  const value: SettingsContextValue = {
    settings,
    resolvedTheme,
    updateSettings,
    resetSettings,
    isModuleEnabled,
    isPreferenceEnabled,
  };

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
};

export function useSettings(): SettingsContextValue {
  const context = useContext(SettingsContext);
  if (!context) {
    throw new Error("useSettings must be used within a SettingsProvider");
  }
  return context;
}
