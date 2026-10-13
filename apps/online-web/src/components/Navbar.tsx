import React, { useState, useEffect } from "react";
import { Link } from "../router/Link";
import { useRouter } from "../router/RouterContext";
import { useAuth } from "../context/AuthContext";
import { softwareApi } from "../api/client";
import type { SupportContacts } from "../types";

interface NavbarProps {
  onOpenTrial?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ onOpenTrial }) => {
  const { navigate } = useRouter();
  const { role, clientUser, logout } = useAuth();
  const [contacts, setContacts] = useState<SupportContacts>({
    phone: "+91 98765 43210",
    whatsapp: "+91 98765 43210",
    email: "support@apexhealth.com",
  });
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    softwareApi.getSupportContacts().then(setContacts).catch(() => {});
  }, []);

  const handleDownloadClick = (e: React.MouseEvent) => {
    e.preventDefault();
    if (role === "client") {
      navigate("/download");
    } else {
      navigate("/account?next=/download");
    }
    setMobileMenuOpen(false);
  };

  const handleLogout = () => {
    logout();
    navigate("/");
    setMobileMenuOpen(false);
  };

  return (
    <header className="navbar-container">
      {/* Top Utility Announcement Bar */}
      <div className="top-notice-bar">
        <div className="container top-notice-content">
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
            <span className="notice-badge">v1.0.0 Commercial Release</span>
            <span>Windows 10 / 11 (64-bit)</span>
            <span className="dot-sep">•</span>
            <span>Offline-First (Port 38291)</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
            <a href={`tel:${contacts.phone.replace(/\s+/g, "")}`} className="top-link">
              📞 Helpline: {contacts.phone}
            </a>
            <span className="dot-sep">•</span>
            {role === "admin" ? (
              <a href="/vendor" className="top-link" style={{ color: "#93c5fd", fontWeight: 600 }}>
                🛡️ Admin Console
              </a>
            ) : (
              <Link to="/account" className="top-link" style={{ color: "#cbd5e1" }}>
                🔒 Portal Sign In
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* Main Navigation Bar */}
      <div className="container main-nav">
        <Link to="/" className="brand-section" onClick={() => setMobileMenuOpen(false)}>
          <img src="/medihisaab-horizontal.png" alt="MediHisaab Logo" className="brand-logo-img" />
          <span className="brand-badge">Pharmacy POS</span>
        </Link>

        {/* Desktop Navigation Links */}
        <nav className="nav-links">
          <Link to="/product" className="nav-link" activeClassName="active">
            Product
          </Link>
          <Link to="/how-it-works" className="nav-link" activeClassName="active">
            How It Works
          </Link>
          <Link to="/plans" className="nav-link" activeClassName="active">
            Plans & Trial
          </Link>
          <Link to="/about" className="nav-link" activeClassName="active">
            About
          </Link>
          <Link to="/support" className="nav-link" activeClassName="active">
            Support
          </Link>
          <Link to="/faq" className="nav-link" activeClassName="active">
            FAQ
          </Link>

          {/* User state buttons */}
          {role === "client" ? (
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <Link to="/client" className="btn-client-portal" style={{ background: "#2563eb" }}>
                <svg width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
                {clientUser?.business_name ? clientUser.business_name.slice(0, 16) : "Dashboard"}
              </Link>
              <button
                onClick={handleLogout}
                className="btn-text-secondary"
                title="Sign out of pharmacy account"
              >
                Sign Out
              </button>
            </div>
          ) : role === "admin" ? (
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <a href="/vendor" className="btn-client-portal" style={{ background: "#059669" }}>
                🛡️ Admin Console
              </a>
              <button onClick={handleLogout} className="btn-text-secondary" title="Sign out of admin account">
                Sign Out
              </button>
            </div>
          ) : (
            <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
              <Link to="/account" className="btn-text-secondary">
                Sign In
              </Link>
              {onOpenTrial ? (
                <button onClick={onOpenTrial} className="btn-nav-trial">
                  Start Free Trial
                </button>
              ) : (
                <Link to="/account?tab=signup" className="btn-nav-trial">
                  Start Free Trial
                </Link>
              )}
            </div>
          )}

          <a href="/download" onClick={handleDownloadClick} className="btn-nav-download">
            <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Download POS
          </a>
        </nav>

        {/* Mobile Hamburger Toggle */}
        <button
          className="mobile-hamburger-btn"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          aria-label="Toggle navigation menu"
        >
          {mobileMenuOpen ? "✕" : "☰"}
        </button>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="mobile-nav-drawer">
          <Link to="/product" className="mobile-nav-link" onClick={() => setMobileMenuOpen(false)}>
            Product Capabilities
          </Link>
          <Link to="/how-it-works" className="mobile-nav-link" onClick={() => setMobileMenuOpen(false)}>
            How It Works (7 Steps)
          </Link>
          <Link to="/plans" className="mobile-nav-link" onClick={() => setMobileMenuOpen(false)}>
            Plans & Evaluation Trial
          </Link>
          <Link to="/about" className="mobile-nav-link" onClick={() => setMobileMenuOpen(false)}>
            About MediHisaab
          </Link>
          <Link to="/support" className="mobile-nav-link" onClick={() => setMobileMenuOpen(false)}>
            Technical Support
          </Link>
          <Link to="/faq" className="mobile-nav-link" onClick={() => setMobileMenuOpen(false)}>
            Frequently Asked Questions
          </Link>

          <div style={{ borderTop: "1px solid #e2e8f0", paddingTop: "0.75rem", marginTop: "0.5rem" }}>
            {role === "client" ? (
              <>
                <Link to="/client" className="mobile-nav-link" onClick={() => setMobileMenuOpen(false)} style={{ fontWeight: 600, color: "#2563eb" }}>
                  Client Dashboard ({clientUser?.business_name})
                </Link>
                <button onClick={handleLogout} className="mobile-nav-link" style={{ background: "none", border: "none", width: "100%", textAlign: "left", color: "#dc2626" }}>
                  Sign Out
                </button>
              </>
            ) : role === "admin" ? (
              <>
                <a href="/vendor" className="mobile-nav-link" style={{ fontWeight: 600, color: "#059669" }}>
                  Admin Console
                </a>
                <button onClick={handleLogout} className="mobile-nav-link" style={{ background: "none", border: "none", width: "100%", textAlign: "left", color: "#dc2626" }}>
                  Sign Out
                </button>
              </>
            ) : (
              <>
                <Link to="/account" className="mobile-nav-link" onClick={() => setMobileMenuOpen(false)}>
                  Sign In / Register
                </Link>
                <Link to="/account?tab=signup" className="mobile-nav-link" onClick={() => setMobileMenuOpen(false)} style={{ color: "#2563eb", fontWeight: 600 }}>
                  Start 15-Day Free Evaluation
                </Link>
              </>
            )}
            <a href="/download" onClick={handleDownloadClick} className="btn-primary-download" style={{ width: "100%", justifyContent: "center", marginTop: "0.5rem" }}>
              Download Windows Installer
            </a>
          </div>
        </div>
      )}
    </header>
  );
};
