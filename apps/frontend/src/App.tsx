import { Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { RootLayout } from "./layouts/RootLayout";
import { ErrorBoundary } from "./components/site/ErrorBoundary";
import { HomePage } from "./pages/HomePage";
import { ProductPage } from "./pages/ProductPage";
import { HowItWorksPage } from "./pages/HowItWorksPage";
import { PlansPage } from "./pages/PlansPage";
import { AccountPage } from "./pages/AccountPage";
import { ClientDashboardPage } from "./pages/ClientDashboardPage";
import { DownloadPage } from "./pages/DownloadPage";
import { AboutPage } from "./pages/AboutPage";
import { SupportPage } from "./pages/SupportPage";
import { PrivacyPage } from "./pages/PrivacyPage";
import { FaqPage } from "./pages/FaqPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { AdminPortalPage } from "./pages/AdminPortalPage";

export default function App() {
  const [queryClient] = useState(() => new QueryClient());

  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <Routes>
          <Route element={<RootLayout />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/product" element={<ProductPage />} />
            <Route path="/how-it-works" element={<HowItWorksPage />} />
            <Route path="/plans" element={<PlansPage />} />
            <Route path="/account" element={<AccountPage />} />
            <Route path="/client" element={<ClientDashboardPage />} />
            <Route path="/client/*" element={<ClientDashboardPage />} />
            <Route path="/download" element={<DownloadPage />} />
            <Route path="/download/*" element={<DownloadPage />} />
            <Route path="/admin" element={<AdminPortalPage />} />
            <Route path="/admin/*" element={<AdminPortalPage />} />
            <Route path="/vendor" element={<AdminPortalPage />} />
            <Route path="/vendor/*" element={<AdminPortalPage />} />
            <Route path="/about" element={<AboutPage />} />
            <Route path="/support" element={<SupportPage />} />
            <Route path="/privacy" element={<PrivacyPage />} />
            <Route path="/faq" element={<FaqPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
