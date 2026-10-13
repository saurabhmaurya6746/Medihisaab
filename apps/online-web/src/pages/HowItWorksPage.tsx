import React from "react";
import { Link } from "../router/Link";
import { useRouter } from "../router/RouterContext";
import { useAuth } from "../context/AuthContext";

export const HowItWorksPage: React.FC = () => {
  const { navigate } = useRouter();
  const { role } = useAuth();

  const handleDownloadClick = (e: React.MouseEvent) => {
    e.preventDefault();
    if (role === "client") {
      navigate("/download");
    } else {
      navigate("/account?next=/download");
    }
  };

  const steps = [
    {
      number: 1,
      title: "Create Pharmacy Account & Start Trial",
      subtitle: "Web Registration",
      requiresInternet: true,
      description:
        "Sign up on the website with your pharmacy name, owner name, email, and phone. Your account is created instantly on the Central Licensing API, and a free evaluation trial is provisioned using the vendor-configured duration (default: 15 days).",
      details: [
        "A single pharmacy account identity powers both your web client portal and your desktop application.",
        "No credit card required. No automatic recurring charges.",
        "Your password is used on the next step to activate your desktop software.",
      ],
    },
    {
      number: 2,
      title: "Download & Run Windows Installer",
      subtitle: "Desktop Installation",
      requiresInternet: true,
      description:
        "Download MediHisaab-Setup-1.0.0.exe (approx. 91.0 MB) from your authenticated client portal or download link. Run the installer to install the self-contained desktop package.",
      details: [
        "Standard Windows Inno Setup wizard: accept the license agreement and choose installation folder.",
        "Includes embedded Python daemon, SQLite WAL database engine, and frontend interface.",
        "Zero external runtimes or complex database server installations required.",
      ],
    },
    {
      number: 3,
      title: "Sign In Once to Activate Signed License",
      subtitle: "Automatic Cryptographic Activation",
      requiresInternet: true,
      description:
        "Launch MediHisaab from your Desktop. On the first launch, choose 'Sign In' and enter your pharmacy email and password from Step 1. The app contacts the licensing service once and activates your signed Ed25519 trial license.",
      details: [
        "The server returns an Ed25519 cryptographically signed license payload.",
        "The desktop daemon validates the cryptographic signature locally and installs the license.",
        "No manual file copying, emailing, or file imports required for your initial trial.",
      ],
    },
    {
      number: 4,
      title: "Configure Local Store Details & Admin Credentials",
      subtitle: "Local Store Setup",
      requiresInternet: false,
      description:
        "Complete the 1-time local store initialization wizard. Enter your store name, Retail Drug License number, GSTIN, and create local staff/cashier PINs and administrator password.",
      details: [
        "Separation of concerns: your local store administrator and cashier accounts are stored strictly in your local SQLite database.",
        "They remain completely separate from your central web licensing account credentials.",
        "Drug license number and GSTIN print on your customer tax invoices.",
      ],
    },
    {
      number: 5,
      title: "Add Medicine Master, Opening Stock & Suppliers",
      subtitle: "Inventory Inwarding",
      requiresInternet: false,
      description:
        "Inward your opening inventory using the high-speed tabular purchase grid (F3). Enter medicine brand names, formulations, distributor details, batch numbers, and expiry dates.",
      details: [
        "Support for trade discounts (TD%) and free quantity schemes (e.g. 10+1, 100+15).",
        "Set Schedule H1 and narcotic statutory compliance flags where required by Rule 65(3)(h).",
        "Exact landed cost and fractional loose-tablet strip calculations.",
      ],
    },
    {
      number: 6,
      title: "Start Sub-Second Counter Billing & LAN Counters",
      subtitle: "Daily Operations",
      requiresInternet: false,
      description:
        "Press F2 to enter billing mode. Scan barcodes or type medicine names for continuous keyboard-driven checkout. If your store has multiple billing counters, activate LAN Server Mode.",
      details: [
        "FEFO auto-allocation dispatches the earliest expiring batch automatically.",
        "Thermal ESC/POS receipt generation bypasses printer driver lag for instantaneous printing.",
        "Secondary counter terminals open in any web browser at http://[SERVER-IP]:38291 without installing local software.",
      ],
    },
    {
      number: 7,
      title: "Automated Hot Backups & Disaster Recovery",
      subtitle: "Data Protection",
      requiresInternet: false,
      description:
        "Protect your pharmacy's sales bills, customer Khata ledgers, and inventory. Create hot backups via Settings > Disaster Recovery without interrupting active counter billing.",
      details: [
        "Generates compressed .pbk archives with cryptographic SHA-256 integrity manifests.",
        "Copy generated backup archives to an external USB flash drive weekly.",
        "Clean-machine disaster recovery safely restores your database in minutes.",
      ],
    },
  ];

  return (
    <div className="page-wrapper">
      {/* Header Banner */}
      <section className="section-container" style={{ background: "linear-gradient(180deg, #ffffff 0%, #f1f5f9 100%)", borderBottom: "1px solid var(--border-color)", padding: "3.5rem 0" }}>
        <div className="container">
          <div className="section-header" style={{ marginBottom: "1rem" }}>
            <span className="section-label">Deployment Roadmap</span>
            <h1 className="section-title">The Complete 7-Step Pharmacy Customer Journey</h1>
            <p className="section-desc">
              Understand exactly how MediHisaab is installed, activated, configured, and run on pharmacy counters.
            </p>
          </div>
          <div style={{ display: "flex", justifyContent: "center", gap: "1rem", flexWrap: "wrap", marginTop: "1.5rem" }}>
            <a href="/download" onClick={handleDownloadClick} className="btn-primary-download">
              Download Windows Installer
            </a>
            <Link to="/plans" className="btn-secondary-trial">
              View Plans & Evaluation Trial &rarr;
            </Link>
          </div>
        </div>
      </section>

      {/* Network Architecture Clarification Notice */}
      <section className="container" style={{ marginTop: "2rem", marginBottom: "2rem" }}>
        <div className="alert-box" style={{ background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: "10px", padding: "1.25rem 1.5rem" }}>
          <div style={{ display: "flex", alignItems: "flex-start", gap: "1rem" }}>
            <span style={{ fontSize: "1.5rem" }}>💡</span>
            <div>
              <strong style={{ color: "#1e40af", fontSize: "1rem" }}>
                Important Architectural Clarification: Online Activation vs. Offline Billing
              </strong>
              <p style={{ color: "#334155", fontSize: "0.9rem", marginTop: "0.35rem", lineHeight: 1.6 }}>
                <strong>Internet is required only during Steps 1, 2, and 3:</strong> creating your pharmacy account, downloading the installer, and activating your initial digital license token.
                <br />
                <strong>Steps 4 through 7 operate 100% offline:</strong> all store configuration, inventory inwarding, daily counter billing, Schedule H1 registers, customer Khata credit, thermal printing, and hot backups run entirely on your local PC and local store network. If your store broadband goes down, your billing never stops.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 7-Step Timeline Section */}
      <section className="section-container" style={{ paddingTop: "1rem" }}>
        <div className="container">
          <div className="timeline-container">
            {steps.map((step) => (
              <div key={step.number} className="timeline-item">
                <div className="timeline-badge">{step.number}</div>
                <div className="timeline-content-card">
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "0.5rem", marginBottom: "0.5rem" }}>
                    <div>
                      <span className="guide-step-badge" style={{ marginBottom: "0.35rem" }}>
                        {step.subtitle}
                      </span>
                      <h3 style={{ fontSize: "1.35rem", fontWeight: 700, color: "#0f172a" }}>
                        {step.title}
                      </h3>
                    </div>
                    {step.requiresInternet ? (
                      <span className="badge badge-warn">Requires Internet</span>
                    ) : (
                      <span className="badge badge-active">100% Offline</span>
                    )}
                  </div>

                  <p style={{ color: "#475569", fontSize: "0.95rem", lineHeight: 1.6, marginBottom: "1rem" }}>
                    {step.description}
                  </p>

                  <ul className="feature-bullets">
                    {step.details.map((d, i) => (
                      <li key={i} className="feature-bullet">
                        <span className="feature-bullet-check">&bull;</span>
                        <span style={{ fontSize: "0.875rem", color: "#334155" }}>{d}</span>
                      </li>
                    ))}
                  </ul>

                  {step.number === 6 && (
                    <div style={{ marginTop: "1rem" }}>
                      <p style={{ fontSize: "0.825rem", color: "#64748b", marginBottom: "0.35rem" }}>
                        One-time Windows Firewall rule to allow secondary LAN counter access on port 38291:
                      </p>
                      <div className="code-box">
                        <code>netsh advfirewall firewall add rule name="MediHisaab LAN" dir=in action=allow protocol=TCP localport=38291 profile=private</code>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div style={{ textAlign: "center", marginTop: "3rem" }}>
            <a href="/download" onClick={handleDownloadClick} className="btn-primary-download" style={{ padding: "0.85rem 2.5rem" }}>
              Get Started: Download Windows Installer &rarr;
            </a>
          </div>
        </div>
      </section>
    </div>
  );
};
