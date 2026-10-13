import React, { useState } from "react";
import { RouterProvider, useRouter } from "./router/RouterContext";
import { AuthProvider } from "./context/AuthContext";
import { Navbar } from "./components/Navbar";
import { Footer } from "./components/Footer";
import { TrialSignupModal } from "./components/TrialSignupModal";

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

const AppContent: React.FC = () => {
  const { pathname } = useRouter();
  const [isTrialOpen, setIsTrialOpen] = useState(false);

  // Normalize path (handle trailing slash if not root)
  const normalizedPath = pathname.length > 1 && pathname.endsWith("/")
    ? pathname.slice(0, -1)
    : pathname;

  const renderCurrentPage = () => {
    switch (normalizedPath) {
      case "/":
        return <HomePage onOpenTrial={() => setIsTrialOpen(true)} />;
      case "/product":
        return <ProductPage />;
      case "/how-it-works":
        return <HowItWorksPage />;
      case "/plans":
        return <PlansPage onOpenTrial={() => setIsTrialOpen(true)} />;
      case "/account":
        return <AccountPage />;
      case "/client":
        return <ClientDashboardPage />;
      case "/download":
        return <DownloadPage />;
      case "/about":
        return <AboutPage />;
      case "/support":
        return <SupportPage />;
      case "/privacy":
        return <PrivacyPage />;
      case "/faq":
        return <FaqPage />;
      default:
        return <NotFoundPage />;
    }
  };

  return (
    <div className="app-layout">
      <Navbar onOpenTrial={() => setIsTrialOpen(true)} />
      <main className="main-content-area">{renderCurrentPage()}</main>
      <Footer />
      <TrialSignupModal isOpen={isTrialOpen} onClose={() => setIsTrialOpen(false)} />
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <RouterProvider>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </RouterProvider>
  );
};

export default App;
