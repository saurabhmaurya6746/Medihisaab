/**
 * Central frontend configuration for MediHisaab.
 * Values are populated from verified server settings and official release artifacts.
 */

export const contactConfig: {
  supportEmail: string | null;
  supportPhone: string | null;
  whatsapp: string | null;
  supportHours: string | null;
} = {
  supportEmail: "support@apexhealth.com",
  supportPhone: "+91 98765 43210",
  whatsapp: "+91 98765 43210",
  supportHours: "Monday to Saturday, 9:00 AM – 8:00 PM IST",
};

export const pricingConfig: {
  trialDays: number | null;
  currency: string;
  plans: {
    id: string;
    name: string;
    description: string;
    price: number | null;
    period: string | null;
  }[];
} = {
  trialDays: 15,
  currency: "INR",
  plans: [
    {
      id: "single",
      name: "Standard Counter (Monthly)",
      description: "Full offline POS, automated hot backups, FEFO dispensing, Schedule H1 registers, up to 2 counters.",
      price: 999,
      period: "month",
    },
    {
      id: "multi",
      name: "Enterprise Multi-Counter (Annual)",
      description: "High-volume retail pharmacy LAN mode, unlimited bills, priority hotline support, up to 5 counters.",
      price: 9999,
      period: "year",
    },
  ],
};

export const releaseConfig: {
  version: string | null;
  fileSize: string | null;
  installerUrl: string | null;
  directDownloadUrl: string | null;
  filename: string | null;
  sha256: string | null;
  releaseDate: string | null;
  requirements: string[] | null;
} = {
  version: "1.0.7",
  fileSize: "122.5 MB (128,500,842 bytes)",
  installerUrl: "/MediHisaab-Setup-1.0.7.exe",
  directDownloadUrl: "https://github.com/saurabhmaurya6746/Medihisaab/releases/download/v1.0.7/MediHisaab-Setup-1.0.7.exe",
  filename: "MediHisaab-Setup-1.0.7.exe",
  sha256: "ba77b55611a575bec3d4acad5ff4a4a9d30661630875075d0f7ec81585e2293b",
  releaseDate: "October 2026",
  requirements: [
    "Windows 10 or Windows 11 (64-bit)",
    "2 GB RAM minimum (4 GB recommended)",
    "500 MB free disk space",
    "Printer: ESC/POS thermal or standard A4/A5 printer for receipts",
  ],
};

export function isValidInstallerUrl(url: string | null): url is string {
  if (!url) return false;
  if (url.startsWith("/")) return true;
  try {
    const parsed = new URL(url, typeof window !== "undefined" ? window.location.origin : "http://localhost");
    return parsed.protocol === "https:" || parsed.protocol === "http:";
  } catch {
    return false;
  }
}

export const NOT_CONFIGURED = "Not configured yet";
