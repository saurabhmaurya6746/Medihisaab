import React, { useState, useEffect } from "react";
import { Link } from "../router/Link";
import { useRouter } from "../router/RouterContext";
import { useAuth } from "../context/AuthContext";
import { softwareApi } from "../api/client";
import type { SoftwareCapability, DownloadItem } from "../types";

interface HomePageProps {
  onOpenTrial: () => void;
}

export const HomePage: React.FC<HomePageProps> = ({ onOpenTrial }) => {
  const { navigate } = useRouter();
  const { role } = useAuth();
  const [installerInfo, setInstallerInfo] = useState<DownloadItem | null>(null);

  useEffect(() => {
    softwareApi.getInstallerInfo().then(setInstallerInfo).catch(() => {});
  }, []);

  const handleDownloadClick = (e: React.MouseEvent) => {
    e.preventDefault();
    if (role === "client") {
      navigate("/download");
    } else {
      navigate("/account?next=/download");
    }
  };

  const capabilities: SoftwareCapability[] = [
    {
      id: "fefo-billing",
      title: "Sub-Second Counter Billing & FEFO",
      shortcut: "F2",
      category: "Billing",
      summary: "High-speed retail counter billing interface built for continuous keyboard input without mouse reliance.",
      bullets: [
        "Automatic First-Expiry-First-Out (FEFO) batch pick algorithm.",
        "Blister cutting support: sell loose tablets with exact fractional MRP math.",
        "Bill hold & recall (Ctrl+H) for managing multi-customer queues.",
        "Split-tender checkout (Cash + UPI + Card + Customer Khata Credit).",
      ],
    },
    {
      id: "purchase-inwarding",
      title: "Tabular Purchase Inwarding Grid",
      shortcut: "F3",
      category: "Inventory",
      summary: "Streamlined distributor invoice entry matching traditional MARG ERP fast tabular data flow.",
      bullets: [
        "Trade discount percentage (TD%) and free quantity schemes (10+1, 100+15).",
        "Exact landed cost per fundamental unit calculated with zero floating-point drift.",
        "Non-inventory charges support (freight, cold-chain refrigeration handling).",
        "Automatic batch creation and distributor accounts payable ledger tracking.",
      ],
    },
    {
      id: "h1-statutory",
      title: "Rule 65(3)(h) Schedule H1 Register",
      shortcut: "F9",
      category: "Statutory",
      summary: "Mandatory regulatory compliance register for restricted schedule drugs and antibiotics.",
      bullets: [
        "Patient name, prescribing doctor, address, and batch ID automatically captured.",
        "Instant statutory compliance CSV and print export for drug inspector audits.",
        "Strict expired drug lockout: expired batches are blocked from counter billing.",
      ],
    },
    {
      id: "khata-ledger",
      title: "Customer Credit Ledger (Khata)",
      shortcut: "F4",
      category: "Billing",
      summary: "Append-only customer credit management with aging bucket analysis for regular neighborhood clients.",
      bullets: [
        "0-30, 31-60, and 60+ days aging bucket breakdowns.",
        "Quick cash deposit shortcut (Ctrl+K) with instant receipt voucher generation.",
        "Linked sales returns with maximum returnable bounds enforcement.",
      ],
    },
    {
      id: "lan-concurrency",
      title: "Multi-Counter LAN Server Mode",
      shortcut: "Port 38291",
      category: "Infrastructure",
      summary: "Operate multiple counter terminals simultaneously across store local network from a single main PC.",
      bullets: [
        "SQLite WAL concurrency allows counter terminals to bill simultaneously.",
        "Secondary counter terminals run in any browser without installing local software.",
        "Zero cloud latency and 100% operational continuity during Internet outages.",
      ],
    },
    {
      id: "disaster-recovery",
      title: "Disaster Recovery & Hot Snapshots",
      shortcut: "VACUUM INTO",
      category: "Infrastructure",
      summary: "Automated hot database backup engine producing compressed .pbk archives with SHA-256 integrity.",
      bullets: [
        "Zero-downtime hot backups taken during active counter billing.",
        "1-Click clean-machine disaster recovery with safety snapshot verification.",
        "Application updates and uninstalls strictly preserve client pharmacy databases.",
      ],
    },
  ];

  return (
    <div className="page-wrapper">
      {/* Hero Section */}
      <section className="hero-section">
        <div className="container">
          <div className="hero-tag">
            <svg width="16" height="16" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            MediHisaab v1.0.0 Official Release
          </div>

          <h1 className="hero-title">
            Offline Pharmacy Management System & Retail Billing POS
          </h1>

          <p className="hero-subtitle">
            Engineered for high-volume Indian retail chemists and pharmacy stores. Sub-second keyboard billing, automated FEFO batch allocation, Schedule H1 statutory records, customer Khata credit, thermal ESC/POS printing, and multi-counter LAN mode.
          </p>

          <div className="hero-cta-group">
            <a href="/download" onClick={handleDownloadClick} className="btn-primary-download">
              <svg width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2.2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Download Windows Installer (v1.0.0)
            </a>

            <button onClick={onOpenTrial} className="btn-secondary-trial">
              <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Start Free Evaluation Trial
            </button>

            <Link to="/product" className="btn-text-link">
              Explore Capabilities &rarr;
            </Link>
          </div>

          <div className="hero-meta-box">
            <span className="meta-pill">
              📦 Installer: <strong>MediHisaab-Setup-1.0.0.exe</strong> ({installerInfo?.size || "91.0 MB"})
            </span>
            <span className="dot-sep">•</span>
            <span className="meta-pill">
              💻 Platform: <strong>Windows 10 / 11 (64-bit)</strong>
            </span>
            <span className="dot-sep">•</span>
            <span className="meta-pill">
              🛡️ Offline Sovereignty: <strong>100% Local SQLite WAL</strong>
            </span>
          </div>
        </div>
      </section>

      {/* Core Capabilities Grid */}
      <section className="section-container">
        <div className="container">
          <div className="section-header">
            <span className="section-label">Verified Architecture</span>
            <h2 className="section-title">Designed for Fast-Paced Pharmacy Counters</h2>
            <p className="section-desc">
              All features operate offline without requiring continuous Internet connectivity. Your store database lives strictly on your local PC.
            </p>
          </div>

          <div className="feature-grid">
            {capabilities.map((cap) => (
              <div key={cap.id} className="feature-card">
                <div className="feature-card-header">
                  <div className="feature-icon-badge">
                    {cap.category === "Billing" ? "💳" : cap.category === "Inventory" ? "📦" : cap.category === "Statutory" ? "📋" : "🖥️"}
                  </div>
                  {cap.shortcut && <span className="shortcut-tag">{cap.shortcut}</span>}
                </div>
                <h3 className="feature-title">{cap.title}</h3>
                <p className="feature-summary">{cap.summary}</p>
                <ul className="feature-bullets">
                  {cap.bullets.map((b, idx) => (
                    <li key={idx} className="feature-bullet">
                      <span className="feature-bullet-check">&check;</span>
                      <span>{b}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <div style={{ textAlign: "center", marginTop: "2.5rem" }}>
            <Link to="/product" className="btn-secondary-trial" style={{ display: "inline-flex" }}>
              View Complete Product Specifications & Peripherals &rarr;
            </Link>
          </div>
        </div>
      </section>

      {/* 3-Step Journey Teaser */}
      <section className="section-container" style={{ background: "#f8fafc", borderTop: "1px solid var(--border-color)", borderBottom: "1px solid var(--border-color)" }}>
        <div className="container">
          <div className="section-header">
            <span className="section-label">Simple Onboarding</span>
            <h2 className="section-title">How Getting Started Works</h2>
            <p className="section-desc">
              From web registration to high-speed offline counter billing in three straightforward steps.
            </p>
          </div>

          <div className="steps-cards-row">
            <div className="step-feature-card">
              <span className="step-circle">1</span>
              <h3>Create Account & Download</h3>
              <p>
                Sign up on this website with your pharmacy details. Your account automatically receives a free evaluation trial. Download the self-contained Windows installer.
              </p>
            </div>

            <div className="step-feature-card">
              <span className="step-circle">2</span>
              <h3>Sign In Once to Activate</h3>
              <p>
                Install MediHisaab and launch it. On first run, enter the same pharmacy email and password. The app contacts the licensing server once to activate your signed Ed25519 license.
              </p>
            </div>

            <div className="step-feature-card">
              <span className="step-circle">3</span>
              <h3>Run 100% Offline</h3>
              <p>
                Set up your store details and admin PIN. Inward medicine inventory and start billing. No active internet connection is needed for continuous billing or receipt printing.
              </p>
            </div>
          </div>

          <div style={{ textAlign: "center", marginTop: "2rem" }}>
            <Link to="/how-it-works" className="btn-text-link" style={{ fontWeight: 600 }}>
              Read the full 7-step customer deployment guide &rarr;
            </Link>
          </div>
        </div>
      </section>

      {/* Commercial Evaluation CTA Banner */}
      <section className="section-container" style={{ background: "linear-gradient(180deg, #1e293b 0%, #0f172a 100%)", color: "#ffffff" }}>
        <div className="container" style={{ textAlign: "center" }}>
          <span className="notice-badge" style={{ background: "rgba(59, 130, 246, 0.2)", color: "#93c5fd" }}>
            Asymmetric Ed25519 Licensing
          </span>
          <h2 style={{ fontSize: "2.25rem", fontWeight: 800, margin: "1rem 0", color: "#ffffff" }}>
            Ready to Streamline Your Pharmacy Counters?
          </h2>
          <p style={{ color: "#94a3b8", fontSize: "1.1rem", maxWidth: "680px", margin: "0 auto 2rem auto" }}>
            Start with a free evaluation trial. No credit card required. Download the Windows installer and begin billing immediately.
          </p>

          <div style={{ display: "flex", justifyContent: "center", gap: "1rem", flexWrap: "wrap" }}>
            <button
              onClick={onOpenTrial}
              className="btn-primary-download"
              style={{ padding: "0.85rem 2rem", fontSize: "1.05rem" }}
            >
              Start Free Evaluation Trial
            </button>
            <a
              href="/download"
              onClick={handleDownloadClick}
              className="btn-secondary-trial"
              style={{ background: "transparent", color: "#ffffff", borderColor: "rgba(255,255,255,0.2)" }}
            >
              Download Windows Installer &rarr;
            </a>
          </div>
        </div>
      </section>
    </div>
  );
};
