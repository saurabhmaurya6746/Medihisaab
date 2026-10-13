import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from "react";

export interface RouterContextValue {
  pathname: string;
  search: string;
  hash: string;
  query: URLSearchParams;
  navigate: (to: string, options?: { replace?: boolean }) => void;
}

const RouterContext = createContext<RouterContextValue | null>(null);

export const RouterProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentUrl, setCurrentUrl] = useState(() => ({
    pathname: window.location.pathname || "/",
    search: window.location.search || "",
    hash: window.location.hash || "",
  }));

  useEffect(() => {
    const handlePopState = () => {
      setCurrentUrl({
        pathname: window.location.pathname || "/",
        search: window.location.search || "",
        hash: window.location.hash || "",
      });
    };

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const navigate = useCallback((to: string, options?: { replace?: boolean }) => {
    // Check if it's an external link or protocol
    if (to.startsWith("http://") || to.startsWith("https://") || to.startsWith("mailto:") || to.startsWith("tel:")) {
      window.location.href = to;
      return;
    }

    const url = new URL(to, window.location.origin);
    const newPath = url.pathname;
    const newSearch = url.search;
    const newHash = url.hash;

    if (options?.replace) {
      window.history.replaceState({}, "", to);
    } else {
      window.history.pushState({}, "", to);
    }

    setCurrentUrl({
      pathname: newPath,
      search: newSearch,
      hash: newHash,
    });

    if (newHash) {
      const el = document.getElementById(newHash.slice(1));
      if (el) {
        el.scrollIntoView({ behavior: "smooth" });
        return;
      }
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  const query = useMemo(() => new URLSearchParams(currentUrl.search), [currentUrl.search]);

  const value = useMemo(
    () => ({
      pathname: currentUrl.pathname,
      search: currentUrl.search,
      hash: currentUrl.hash,
      query,
      navigate,
    }),
    [currentUrl.pathname, currentUrl.search, currentUrl.hash, query, navigate]
  );

  return <RouterContext.Provider value={value}>{children}</RouterContext.Provider>;
};

export const useRouter = (): RouterContextValue => {
  const context = useContext(RouterContext);
  if (!context) {
    throw new Error("useRouter must be used within a RouterProvider");
  }
  return context;
};
