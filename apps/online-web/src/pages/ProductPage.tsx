import React from "react";
import { Link } from "../router/Link";
import { useRouter } from "../router/RouterContext";
import { useAuth } from "../context/AuthContext";
import type { HardwareCompatibility, SystemRequirements } from "../types";

export const ProductPage: React.FC = () => {
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

  const hardwareCompat: HardwareCompatibility[] = [
    {
      deviceType: "Thermal Receipt Printers",
      standards: "ESC/POS 80mm & 58mm",
      details: "Raw byte spooler decoupling. Bypasses Windows print driver lag for instant sub-second receipt printing.",
      recommended: "Epson TM-T82, TVS RP-3200, Posiflex, NGX, Everycom",
    },
    {
      deviceType: "Barcode Scanners",
      standards: "USB HID Keyboard Emulation",
      details: "1D & 2D barcode reading into active input fields. Standard factory default Carriage Return ([CR]) suffix.",
      recommended: "Honeywell Voyager, Zebra Symbol, TVS BS-L100, Winson",
    },
    {
      deviceType: "Cash Drawers",
      standards: "RJ-11 / RJ-12 Solenoid Kick Pulse",
      details: "Triggered via thermal printer kick pulse command (ESC p 0 25 250). Compatible with 12V and 24V solenoids.",
      recommended: "Standard RJ-11 cash drawer connected directly to ESC/POS printer",
    },
    {
      deviceType: "Laser Tax Invoices",
      standards: "A4 & A5 Standard Formats",
      details: "Clean tax invoice printing for wholesale distributor inwarding reconciliation and B2B hospital sales.",
      recommended: "HP LaserJet, Canon imageCLASS, Brother laser series",
    },
  ];

  const systemRequirements: SystemRequirements = {
    os: "Windows 10 / Windows 11 (64-bit editions)",
    processor: "Intel Core i3 / AMD Ryzen 3 or higher (Dual-Core 2.0 GHz+)",
    ram: "4 GB RAM minimum (8 GB recommended for multi-counter LAN host)",
    disk: "200 MB free storage for application files + local SQLite database",
    ports: "TCP Port 38291 (Localhost / Private LAN only)",
    dependencies: "None. Embedded Python daemon, SQLite WAL engine, and web UI are fully self-contained.",
  };

  return (
    <div className="page-wrapper">
      {/* Header Banner */}
      <section className="section-container" style={{ background: "linear-gradient(180deg, #ffffff 0%, #f1f5f9 100%)", borderBottom: "1px solid var(--border-color)", padding: "3rem 0" }}>
        <div className="container">
          <div className="section-header" style={{ marginBottom: "1rem" }}>
            <span className="section-label">Product Capabilities</span>
            <h1 className="section-title">Verified Architecture & Feature Breakdown</h1>
            <p className="section-desc">
              MediHisaab is engineered around real operational workflows of Indian chemists. Every feature listed here is verified in code and operates offline.
            </p>
          </div>
          <div style={{ display: "flex", justifyContent: "center", gap: "1rem", flexWrap: "wrap", marginTop: "1.5rem" }}>
            <a href="/download" onClick={handleDownloadClick} className="btn-primary-download">
              Download Windows POS (v1.0.0)
            </a>
            <Link to="/how-it-works" className="btn-secondary-trial">
              View Deployment Steps &rarr;
            </Link>
          </div>
        </div>
      </section>

      {/* Offline vs Online Operational Matrix */}
      <section className="section-container">
        <div className="container">
          <div className="section-header">
            <span className="section-label">Operational Continuity</span>
            <h2 className="section-title">What Works Offline vs. What Requires Internet</h2>
            <p className="section-desc">
              MediHisaab is designed so pharmacy counters never halt billing when broadband fails.
            </p>
          </div>

          <div className="matrix-table-wrapper">
            <table className="specs-table">
              <thead>
                <tr>
                  <th style={{ width: "35%" }}>Operational Capability</th>
                  <th style={{ width: "20%" }}>Network Mode</th>
                  <th style={{ width: "45%" }}>Technical Implementation</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><strong>Counter Billing & Invoicing (F2)</strong></td>
                  <td><span className="badge badge-active">100% Offline</span></td>
                  <td>Processes locally against SQLite database. Zero cloud latency. Sub-second response.</td>
                </tr>
                <tr>
                  <td><strong>FEFO Batch Dispensing & MRP Calculation</strong></td>
                  <td><span className="badge badge-active">100% Offline</span></td>
                  <td>Automatic batch allocation sorted by earliest expiry date on local disk.</td>
                </tr>
                <tr>
                  <td><strong>Loose Tablet Blister Cutting</strong></td>
                  <td><span className="badge badge-active">100% Offline</span></td>
                  <td>Calculates exact fractional pricing per loose tablet with zero rounding drift.</td>
                </tr>
                <tr>
                  <td><strong>Schedule H1 Statutory Register (F9)</strong></td>
                  <td><span className="badge badge-active">100% Offline</span></td>
                  <td>Captures patient name, doctor, and batch locally. Exports statutory audit files without internet.</td>
                </tr>
                <tr>
                  <td><strong>Customer Credit Ledger / Khata (F4)</strong></td>
                  <td><span className="badge badge-active">100% Offline</span></td>
                  <td>Append-only ledger with aging buckets (0-30, 31-60, 60+ days) and cash deposits.</td>
                </tr>
                <tr>
                  <td><strong>Multi-Counter LAN Billing</strong></td>
                  <td><span className="badge badge-active">100% Offline (Local LAN)</span></td>
                  <td>Secondary terminals connect over store Wi-Fi/Ethernet to port 38291. No internet required.</td>
                </tr>
                <tr>
                  <td><strong>Disaster Recovery Hot Backups</strong></td>
                  <td><span className="badge badge-active">100% Offline</span></td>
                  <td>SQLite <code>VACUUM INTO</code> produces hot <code>.pbk</code> archives during active billing.</td>
                </tr>
                <tr>
                  <td><strong>Initial Trial License Activation</strong></td>
                  <td><span className="badge badge-warn">Requires Internet (Once)</span></td>
                  <td>Desktop app signs in to the Central Licensing API once on first launch to retrieve signed Ed25519 token.</td>
                </tr>
                <tr>
                  <td><strong>License Renewal & Subscription Sync</strong></td>
                  <td><span className="badge badge-warn">Requires Internet / File</span></td>
                  <td>Submitted from client portal or desktop app. Can also be updated completely offline via manual signed license file import.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Feature Deep-Dive Grid */}
      <section className="section-container" style={{ background: "#f8fafc", borderTop: "1px solid var(--border-color)", borderBottom: "1px solid var(--border-color)" }}>
        <div className="container">
          <div className="section-header">
            <span className="section-label">Core Modules</span>
            <h2 className="section-title">Built for Real Retail Chemist Workflows</h2>
            <p className="section-desc">
              Keyboard shortcuts and operational logic built to match the speed of traditional MARG ERP 9+.
            </p>
          </div>

          <div className="feature-grid">
            <div className="feature-card">
              <div className="feature-card-header">
                <span className="feature-icon-badge">⚡</span>
                <span className="shortcut-tag">F2 Shortcut</span>
              </div>
              <h3 className="feature-title">Keyboard-First Retail Counter Billing</h3>
              <p className="feature-summary">
                Sub-second checkout flow designed for rapid continuous typing without touching the mouse.
              </p>
              <ul className="feature-bullets">
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> Barcode scan or quick name search with instant medicine matches.</li>
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> Blister strip fractional cutting (sell 3 loose tablets from a strip of 10).</li>
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> Multi-customer bill hold and recall (Ctrl+H) for busy counters.</li>
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> Split tender checkout: Cash, UPI QR, Card, and Customer Khata Credit.</li>
              </ul>
            </div>

            <div className="feature-card">
              <div className="feature-card-header">
                <span className="feature-icon-badge">📦</span>
                <span className="shortcut-tag">F3 Shortcut</span>
              </div>
              <h3 className="feature-title">Tabular Distributor Purchase Inwarding</h3>
              <p className="feature-summary">
                High-speed distributor invoice inwarding grid mirroring traditional wholesale billing sheets.
              </p>
              <ul className="feature-bullets">
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> Supports trade discount percentage (TD%) and cash discounts.</li>
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> Free quantity scheme handling (e.g. 10+1, 100+15 schemes).</li>
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> Landed cost per fundamental unit calculated with zero rounding drift.</li>
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> Non-inventory freight and cold-chain charges allocation.</li>
              </ul>
            </div>

            <div className="feature-card">
              <div className="feature-card-header">
                <span className="feature-icon-badge">📋</span>
                <span className="shortcut-tag">F9 Shortcut</span>
              </div>
              <h3 className="feature-title">Rule 65(3)(h) Schedule H1 Register</h3>
              <p className="feature-summary">
                Statutory regulatory compliance register for restricted schedule drugs and antibiotics.
              </p>
              <ul className="feature-bullets">
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> Automatically prompts for patient name, doctor, and address during billing.</li>
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> Strict expired drug lockout prevents billing expired batches.</li>
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> Instant export to compliant CSV and printable reports for Drug Inspector inspections.</li>
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> GSTR-1 and GSTR-2 inward/outward tax breakdown summaries.</li>
              </ul>
            </div>

            <div className="feature-card">
              <div className="feature-card-header">
                <span className="feature-icon-badge">📖</span>
                <span className="shortcut-tag">F4 Shortcut</span>
              </div>
              <h3 className="feature-title">Customer Khata Credit Ledger</h3>
              <p className="feature-summary">
                Append-only customer credit management for regular neighborhood families and clinic accounts.
              </p>
              <ul className="feature-bullets">
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> Aging buckets breakdown: 0–30 days, 31–60 days, and 60+ days overdue.</li>
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> Quick cash deposit receipt shortcut (Ctrl+K) with instant thermal receipt vouchers.</li>
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> Credit limit enforcement to prevent unapproved debt accumulation.</li>
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> Linked sales returns with maximum returnable bounds enforcement.</li>
              </ul>
            </div>

            <div className="feature-card">
              <div className="feature-card-header">
                <span className="feature-icon-badge">🌐</span>
                <span className="shortcut-tag">Port 38291</span>
              </div>
              <h3 className="feature-title">Multi-Counter LAN Architecture</h3>
              <p className="feature-summary">
                Operate multiple counter terminals simultaneously across store local network from one host PC.
              </p>
              <ul className="feature-bullets">
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> SQLite Write-Ahead Logging (WAL) concurrency supports simultaneous multi-counter checkout.</li>
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> Secondary counter terminals run in any browser (Chrome, Edge, Firefox) without software installation.</li>
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> Zero cloud latency; 100% operational continuity during Internet outages.</li>
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> Works across standard store Wi-Fi router or Ethernet switch.</li>
              </ul>
            </div>

            <div className="feature-card">
              <div className="feature-card-header">
                <span className="feature-icon-badge">💾</span>
                <span className="shortcut-tag">VACUUM INTO</span>
              </div>
              <h3 className="feature-title">Disaster Recovery & Hot SQLite Backups</h3>
              <p className="feature-summary">
                Automated hot database backup engine producing compressed archives with SHA-256 integrity.
              </p>
              <ul className="feature-bullets">
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> Zero-downtime hot backups taken during active counter billing without locking tables.</li>
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> Compressed <code>.pbk</code> archive format with cryptographic manifest verification.</li>
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> 1-Click clean-machine disaster recovery with mandatory safety snapshot creation.</li>
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> Application updates and uninstalls strictly preserve client pharmacy databases.</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Hardware Compatibility Section */}
      <section className="section-container">
        <div className="container">
          <div className="section-header">
            <span className="section-label">Peripherals</span>
            <h2 className="section-title">Tested Counter Hardware Compatibility</h2>
            <p className="section-desc">
              Standard retail POS peripherals supported by MediHisaab's decoupled raw byte spooler.
            </p>
          </div>

          <div className="feature-grid">
            {hardwareCompat.map((item, idx) => (
              <div key={idx} className="feature-card">
                <div className="feature-card-header">
                  <span className="feature-icon-badge">
                    {item.deviceType.includes("Printer") ? "🖨️" : item.deviceType.includes("Scanner") ? "🔍" : item.deviceType.includes("Drawer") ? "💵" : "📄"}
                  </span>
                  <span className="shortcut-tag">{item.standards}</span>
                </div>
                <h3 className="feature-title">{item.deviceType}</h3>
                <p className="feature-summary">{item.details}</p>
                <div style={{ fontSize: "0.85rem", color: "#64748b", borderTop: "1px solid #f1f5f9", paddingTop: "0.75rem" }}>
                  <strong>Verified Devices:</strong> {item.recommended}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* System Requirements Section */}
      <section className="section-container" style={{ background: "#f8fafc", borderTop: "1px solid var(--border-color)", borderBottom: "1px solid var(--border-color)" }}>
        <div className="container">
          <div className="section-header">
            <span className="section-label">Hardware Specifications</span>
            <h2 className="section-title">Minimum System Requirements</h2>
            <p className="section-desc">
              Lightweight footprint designed to run reliably on affordable Windows desktop hardware.
            </p>
          </div>

          <div className="specs-wrapper">
            <table className="specs-table">
              <tbody>
                <tr>
                  <th>Operating System</th>
                  <td>{systemRequirements.os}</td>
                </tr>
                <tr>
                  <th>Processor</th>
                  <td>{systemRequirements.processor}</td>
                </tr>
                <tr>
                  <th>System Memory</th>
                  <td>{systemRequirements.ram}</td>
                </tr>
                <tr>
                  <th>Storage</th>
                  <td>{systemRequirements.disk}</td>
                </tr>
                <tr>
                  <th>Network Ports</th>
                  <td>{systemRequirements.ports}</td>
                </tr>
                <tr>
                  <th>External Runtimes</th>
                  <td>{systemRequirements.dependencies}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div style={{ textAlign: "center", marginTop: "2.5rem" }}>
            <a href="/download" onClick={handleDownloadClick} className="btn-primary-download">
              Download Windows Installer &rarr;
            </a>
          </div>
        </div>
      </section>
    </div>
  );
};
