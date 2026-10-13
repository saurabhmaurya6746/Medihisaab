import { Link, NavLink } from "react-router-dom";
import { Download, Menu, X } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Logo } from "./Logo";
import { useSession } from "@/lib/auth";

const nav = [
  { to: "/", label: "Home" },
  { to: "/product", label: "Product" },
  { to: "/how-it-works", label: "How It Works" },
  { to: "/plans", label: "Plans" },
  { to: "/support", label: "Support" },
] as const;

export function SiteHeader() {
  const [open, setOpen] = useState(false);
  const { session } = useSession();

  const userPath = session?.role === "admin" ? "/admin" : "/client";
  const userLabel = session?.role === "admin" ? "Admin Console" : "Dashboard";

  return (
    <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur-sm">
      <div className="container-page flex h-16 items-center justify-between gap-6">
        <Logo className="h-7 md:h-8" />
        <nav aria-label="Main" className="hidden items-center gap-1 lg:flex">
          {nav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              className={({ isActive }) =>
                `rounded-md px-3 py-2 text-sm font-medium transition-colors hover:text-foreground ${
                  isActive ? "text-primary" : "text-muted-foreground"
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="hidden items-center gap-2 lg:flex">
          {session ? (
            <Button asChild variant="ghost" size="sm">
              <Link to={userPath}>{userLabel}</Link>
            </Button>
          ) : (
            <Button asChild variant="ghost" size="sm">
              <Link to="/account">Sign In</Link>
            </Button>
          )}
          <Button asChild size="sm">
            <Link to="/download">
              <Download className="size-4" /> Download for Windows
            </Link>
          </Button>
        </div>
        <button
          type="button"
          className="inline-flex size-10 items-center justify-center rounded-md border lg:hidden"
          aria-expanded={open}
          aria-controls="mobile-nav"
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((o) => !o)}
        >
          {open ? <X className="size-5" /> : <Menu className="size-5" />}
        </button>
      </div>
      {open && (
        <nav id="mobile-nav" aria-label="Mobile" className="border-t bg-background lg:hidden">
          <div className="container-page flex flex-col py-3">
            {nav.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.to === "/"}
                onClick={() => setOpen(false)}
                className={({ isActive }) =>
                  `rounded-md px-2 py-3 text-base font-medium ${
                    isActive ? "text-primary" : "text-muted-foreground"
                  }`
                }
              >
                {n.label}
              </NavLink>
            ))}
            <div className="mt-3 grid gap-2 border-t pt-4">
              <Button asChild variant="outline" onClick={() => setOpen(false)}>
                <Link to={session ? userPath : "/account"}>
                  {session ? userLabel : "Sign In"}
                </Link>
              </Button>
              <Button asChild onClick={() => setOpen(false)}>
                <Link to="/download">
                  <Download className="size-4" /> Download for Windows
                </Link>
              </Button>
            </div>
          </div>
        </nav>
      )}
    </header>
  );
}
