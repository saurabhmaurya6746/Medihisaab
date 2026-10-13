import { Link } from "react-router-dom";
import { Logo } from "./Logo";

const cols = [
  {
    title: "Product",
    links: [
      { to: "/product", label: "Product" },
      { to: "/how-it-works", label: "How It Works" },
      { to: "/plans", label: "Plans & Trial" },
      { to: "/download", label: "Download" },
    ],
  },
  {
    title: "Account",
    links: [
      { to: "/account", label: "Sign In" },
      { to: "/account?mode=signup", label: "Create Account" },
      { to: "/client", label: "Dashboard" },
    ],
  },
  {
    title: "Help",
    links: [
      { to: "/support", label: "Support" },
      { to: "/faq", label: "FAQ" },
      { to: "/about", label: "About" },
      { to: "/privacy", label: "Privacy" },
    ],
  },
] as const;

export function SiteFooter() {
  return (
    <footer className="mt-24 border-t bg-card">
      <div className="container-page grid gap-10 py-14 md:grid-cols-[1.4fr_repeat(3,1fr)]">
        <div className="max-w-xs">
          <Logo className="h-7" />
          <p className="mt-4 text-sm text-muted-foreground">
            Pharmacy billing, stock and expiry records for Indian medical stores, on your Windows
            computer.
          </p>
        </div>
        {cols.map((c) => (
          <div key={c.title}>
            <h2 className="text-sm font-semibold">{c.title}</h2>
            <ul className="mt-4 space-y-2.5">
              {c.links.map((l) => (
                <li key={l.label}>
                  <Link to={l.to} className="text-sm text-muted-foreground hover:text-foreground">
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t">
        <div className="container-page flex flex-col gap-2 py-6 text-xs text-muted-foreground sm:flex-row sm:justify-between">
          <p>© {new Date().getFullYear()} MediHisaab. All rights reserved.</p>
          <p>Frontend preview. Product details are subject to change.</p>
        </div>
      </div>
    </footer>
  );
}
