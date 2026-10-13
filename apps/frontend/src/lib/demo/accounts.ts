/**
 * DEVELOPMENT-ONLY demo accounts. These are not production credentials and
 * are only accepted when `import.meta.env.DEV` is true.
 */
export type Role = "client" | "admin";

export interface DemoAccount {
  email: string;
  password: string;
  role: Role;
  pharmacyName: string;
  ownerName: string;
}

export const DEMO_ENABLED = import.meta.env.DEV;

export const demoAccounts: DemoAccount[] = DEMO_ENABLED
  ? [
      {
        email: "client@demo.local",
        password: "demo-client",
        role: "client",
        pharmacyName: "Shree Demo Medical Store",
        ownerName: "Demo Owner",
      },
      {
        email: "admin@demo.local",
        password: "demo-admin",
        role: "admin",
        pharmacyName: "MediHisaab Admin (Demo)",
        ownerName: "Demo Admin",
      },
    ]
  : [];
