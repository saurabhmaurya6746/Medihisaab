/** Illustrative demo data for the client dashboard. Not real customer data. */
export type LicenseState = "trial" | "active" | "renewal_pending" | "expiring" | "expired";

export const licenseStates: Record<
  LicenseState,
  {
    label: string;
    tone: "ok" | "info" | "warn" | "bad";
    daysRemaining: number;
    description: string;
  }
> = {
  trial: {
    label: "Active trial",
    tone: "info",
    daysRemaining: 9,
    description:
      "You are using the trial. Request a license before it ends to keep billing without interruption.",
  },
  active: {
    label: "Active license",
    tone: "ok",
    daysRemaining: 214,
    description: "Your license is active. No action is needed right now.",
  },
  renewal_pending: {
    label: "Renewal pending",
    tone: "info",
    daysRemaining: 6,
    description: "A renewal request is waiting for review by the provider.",
  },
  expiring: {
    label: "Expiring soon",
    tone: "warn",
    daysRemaining: 4,
    description: "Your license ends soon. Submit a renewal request to avoid interruption.",
  },
  expired: {
    label: "Expired",
    tone: "bad",
    daysRemaining: 0,
    description: "Your license has ended. Submit a renewal request to restore access.",
  },
};

export function expiryDateFor(days: number) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export const demoActivity = [
  { when: "Today, 10:42", text: "Signed in to the account portal" },
  { when: "Yesterday, 18:05", text: "Viewed installation instructions" },
  { when: "3 days ago", text: "Trial started for this pharmacy account" },
  { when: "3 days ago", text: "Pharmacy account created" },
];
