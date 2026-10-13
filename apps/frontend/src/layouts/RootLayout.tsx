import { Outlet, useLocation } from "react-router-dom";
import { SiteHeader } from "@/components/site/SiteHeader";
import { SiteFooter } from "@/components/site/SiteFooter";
import { Toaster } from "@/components/ui/sonner";
import { ScrollToTop } from "@/components/site/ScrollToTop";

export function RootLayout() {
  const { pathname } = useLocation();
  const isApp =
    pathname.startsWith("/client") ||
    pathname.startsWith("/admin") ||
    pathname.startsWith("/vendor");

  return (
    <>
      <ScrollToTop />
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-card focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      {!isApp && <SiteHeader />}
      <main id="main">
        <Outlet />
      </main>
      {!isApp && <SiteFooter />}
      <Toaster />
    </>
  );
}
