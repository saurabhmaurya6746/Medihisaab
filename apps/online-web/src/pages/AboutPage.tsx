import React from "react";
import { Link } from "../router/Link";

export const AboutPage: React.FC = () => {
  return (
    <div className="page-wrapper">
      {/* Header Banner */}
      <section className="section-container" style={{ background: "linear-gradient(180deg, #ffffff 0%, #f1f5f9 100%)", borderBottom: "1px solid var(--border-color)", padding: "3.5rem 0" }}>
        <div className="container">
          <div className="section-header" style={{ marginBottom: "1rem" }}>
            <span className="section-label">Company & Product</span>
            <h1 className="section-title">About MediHisaab</h1>
            <p className="section-desc">
              Offline-first retail pharmacy management system and POS ERP engineered by Apex Health Software Solutions.
            </p>
          </div>
        </div>
      </section>

      {/* Main Content */}
      <section className="section-container">
        <div className="container" style={{ maxWidth: "860px" }}>
          <div className="about-content-section" style={{ lineHeight: 1.8, fontSize: "1.025rem", color: "#334155" }}>
            <h2 style={{ fontSize: "1.6rem", fontWeight: 700, color: "#0f172a", marginBottom: "1rem" }}>
              Our Philosophy: Fast, Keyboard-Driven & Offline-Sovereign
            </h2>
            <p style={{ marginBottom: "1.25rem" }}>
              Retail pharmacies in India operate in high-density, fast-paced environments where queues form quickly and every second at the counter counts. Traditional cloud-only SaaS systems introduce internet latency, spinning loaders, and the constant risk of complete operational stoppage during broadband outages.
            </p>
            <p style={{ marginBottom: "1.25rem" }}>
              MediHisaab was designed from the ground up to preserve the legendary keyboard speed of traditional ERP systems like MARG ERP 9+, while providing a modern, reliable user experience. Pharmacists can complete an entire sale—from scanning medicines and cutting loose blister tablets to calculating GST and printing thermal receipts—purely via keyboard shortcuts without touching a mouse.
            </p>

            <h2 style={{ fontSize: "1.6rem", fontWeight: 700, color: "#0f172a", marginTop: "2.5rem", marginBottom: "1rem" }}>
              Verified Technology Architecture
            </h2>
            <p style={{ marginBottom: "1.25rem" }}>
              Rather than relying on unverified claims, our product architecture is straightforward, transparent, and tested:
            </p>

            <div className="guides-grid" style={{ marginBottom: "2rem" }}>
              <div className="guide-card" style={{ padding: "1.5rem" }}>
                <h4 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#0f172a", marginBottom: "0.5rem" }}>
                  1. Local FastAPI Daemon (Port 38291)
                </h4>
                <p style={{ fontSize: "0.875rem", color: "#64748b" }}>
                  A lightweight Python service runs directly on your Windows desktop. All billing queries, FEFO batch selection, and customer Khata calculations execute locally within milliseconds.
                </p>
              </div>

              <div className="guide-card" style={{ padding: "1.5rem" }}>
                <h4 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#0f172a", marginBottom: "0.5rem" }}>
                  2. SQLite Write-Ahead Logging (WAL)
                </h4>
                <p style={{ fontSize: "0.875rem", color: "#64748b" }}>
                  Ensures rock-solid database concurrency. Multiple counter terminals can bill simultaneously over your local store network (LAN) without database table lockups or data corruption.
                </p>
              </div>

              <div className="guide-card" style={{ padding: "1.5rem" }}>
                <h4 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#0f172a", marginBottom: "0.5rem" }}>
                  3. Asymmetric Ed25519 Cryptography
                </h4>
                <p style={{ fontSize: "0.875rem", color: "#64748b" }}>
                  Licensing tokens are cryptographically signed using private keys held exclusively on the Central Licensing API. The desktop app validates licenses using the public key locally, with zero remote telemetry lockouts.
                </p>
              </div>

              <div className="guide-card" style={{ padding: "1.5rem" }}>
                <h4 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#0f172a", marginBottom: "0.5rem" }}>
                  4. Raw Spooler ESC/POS Printing
                </h4>
                <p style={{ fontSize: "0.875rem", color: "#64748b" }}>
                  Receipts are rendered directly into ESC/POS printer byte streams, bypassing the slow Windows print subsystem to pop the cash drawer and print invoices instantaneously.
                </p>
              </div>
            </div>

            <h2 style={{ fontSize: "1.6rem", fontWeight: 700, color: "#0f172a", marginTop: "2rem", marginBottom: "1rem" }}>
              Data Sovereignty: Your Data Remains Yours
            </h2>
            <p style={{ marginBottom: "1.25rem" }}>
              We believe pharmacy owners should maintain absolute sovereignty over their financial and customer records. Your supplier inwarding prices, customer Khata balances, sales revenue, and patient prescription registers remain strictly in your store's local SQLite database. We do not aggregate, resell, or monetize your pharmacy's commercial transactional data.
            </p>

            <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "10px", padding: "1.5rem", marginTop: "2rem", textAlign: "center" }}>
              <h3 style={{ fontSize: "1.25rem", fontWeight: 700, color: "#0f172a", marginBottom: "0.5rem" }}>
                Ready to Experience MediHisaab?
              </h3>
              <p style={{ color: "#64748b", fontSize: "0.95rem", marginBottom: "1.25rem" }}>
                Start evaluating MediHisaab today with a free 15-day trial on your Windows PC.
              </p>
              <div style={{ display: "flex", justifyContent: "center", gap: "1rem", flexWrap: "wrap" }}>
                <Link to="/download" className="btn-primary-download">
                  Download Windows Installer
                </Link>
                <Link to="/plans" className="btn-secondary-trial">
                  View Commercial Plans &rarr;
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};
