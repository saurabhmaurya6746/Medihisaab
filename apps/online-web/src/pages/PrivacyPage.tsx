import React from "react";

export const PrivacyPage: React.FC = () => {
  return (
    <div className="page-wrapper">
      {/* Header Banner */}
      <section className="section-container" style={{ background: "linear-gradient(180deg, #ffffff 0%, #f1f5f9 100%)", borderBottom: "1px solid var(--border-color)", padding: "3.5rem 0" }}>
        <div className="container">
          <div className="section-header" style={{ marginBottom: "1rem" }}>
            <span className="section-label">Data Protection & Privacy</span>
            <h1 className="section-title">Privacy Policy & Local Data Sovereignty</h1>
            <p className="section-desc">
              Clear disclosure of what data the Central Licensing API collects, and our architectural commitment to local pharmacy data sovereignty.
            </p>
          </div>
        </div>
      </section>

      {/* Main Content */}
      <section className="section-container">
        <div className="container" style={{ maxWidth: "860px" }}>
          <div className="about-content-section" style={{ lineHeight: 1.8, fontSize: "1rem", color: "#334155" }}>
            {/* Core Summary Callout */}
            <div className="alert-box" style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: "10px", padding: "1.5rem", marginBottom: "2rem" }}>
              <h3 style={{ color: "#166534", fontSize: "1.1rem", fontWeight: 700, marginBottom: "0.5rem" }}>
                Key Summary: Your Pharmacy Ledger Remains on Your Computer
              </h3>
              <p style={{ color: "#166534", fontSize: "0.925rem", lineHeight: 1.6 }}>
                MediHisaab is an offline-first system. Your sales bills, customer Khata balances, medicine stock, supplier costs, and patient prescriptions reside strictly on your local PC in SQLite. They are never uploaded, centralized, or monetized by our licensing service.
              </p>
            </div>

            <h2 style={{ fontSize: "1.45rem", fontWeight: 700, color: "#0f172a", marginBottom: "1rem" }}>
              1. Central Licensing API: What We Collect & Why
            </h2>
            <p style={{ marginBottom: "1rem" }}>
              When you create an account on this website or in the desktop application, the Central Licensing API collects only the minimal information required to manage software entitlements and security:
            </p>

            <div className="specs-wrapper" style={{ marginBottom: "2rem" }}>
              <table className="specs-table">
                <thead>
                  <tr>
                    <th>Data Category</th>
                    <th>Exact Fields</th>
                    <th>Operational Purpose</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td><strong>Account Identity</strong></td>
                    <td>Pharmacy/Business Name, Owner/Contact Name, Business Email, Phone Number</td>
                    <td>Provisioning your client account code (e.g. <code>CL-1001</code>), delivering renewal notices, and identity verification for support.</td>
                  </tr>
                  <tr>
                    <td><strong>Security Credentials</strong></td>
                    <td>Cryptographic salted password hashes (Argon2 / bcrypt)</td>
                    <td>Authentication for client portal and desktop activation. Plaintext passwords are never stored or logged.</td>
                  </tr>
                  <tr>
                    <td><strong>Subscription Entitlements</strong></td>
                    <td>Plan code, trial/subscription start and expiry dates, permitted LAN workstation terminal count</td>
                    <td>Generating signed Ed25519 digital license tokens matching your purchased entitlements.</td>
                  </tr>
                  <tr>
                    <td><strong>Audit Records</strong></td>
                    <td>Timestamps, IP addresses, action type (e.g. <code>CLIENT_SIGNUP</code>, <code>CLIENT_LOGIN</code>, <code>CLIENT_DOWNLOAD_REQUEST</code>)</td>
                    <td>Security monitoring, brute-force rate limit enforcement, and fraud prevention. Passwords and secrets are strictly redacted.</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <h2 style={{ fontSize: "1.45rem", fontWeight: 700, color: "#0f172a", marginTop: "2.5rem", marginBottom: "1rem" }}>
              2. Local Pharmacy Database: What Remains Exclusively Yours
            </h2>
            <p style={{ marginBottom: "1rem" }}>
              All daily retail pharmacy operations are stored solely on your local computer's SQLite database (located by default at <code>%LOCALAPPDATA%\PharmacyApp\</code>). The central licensing server does NOT collect or access:
            </p>

            <ul className="feature-bullets" style={{ marginBottom: "2rem" }}>
              <li className="feature-bullet">
                <span className="feature-bullet-check">&bull;</span>
                <span><strong>Sales & Billing Transactions:</strong> Customer invoices, total revenues, daily cash/UPI sales volumes, discounts, and counter checkout records.</span>
              </li>
              <li className="feature-bullet">
                <span className="feature-bullet-check">&bull;</span>
                <span><strong>Patient & Doctor Information:</strong> Patient names, phone numbers, addresses, and prescribing physician details recorded in Rule 65(3)(h) Schedule H1 registers.</span>
              </li>
              <li className="feature-bullet">
                <span className="feature-bullet-check">&bull;</span>
                <span><strong>Customer Credit Khata:</strong> Outstanding ledger balances, customer aging buckets, and loan repayments.</span>
              </li>
              <li className="feature-bullet">
                <span className="feature-bullet-check">&bull;</span>
                <span><strong>Distributor & Inventory Data:</strong> Medicine master lists, purchase invoices, landed purchase costs, trade discounts (TD%), and batch stock balances.</span>
              </li>
              <li className="feature-bullet">
                <span className="feature-bullet-check">&bull;</span>
                <span><strong>Local Counter Staff Credentials:</strong> Local store cashier PINs and internal store administrator passwords.</span>
              </li>
            </ul>

            <h2 style={{ fontSize: "1.45rem", fontWeight: 700, color: "#0f172a", marginTop: "2.5rem", marginBottom: "1rem" }}>
              3. Licensing Telemetry & Cryptographic Verification
            </h2>
            <p style={{ marginBottom: "1rem" }}>
              To ensure transparency regarding network activity:
            </p>
            <ul className="guide-steps" style={{ listStyle: "disc", paddingLeft: "1.25rem", marginBottom: "1.5rem" }}>
              <li>
                <strong>Periodic Entitlement Checks:</strong> When the desktop application has an active internet connection, it periodically contacts the Central Licensing API to check if an updated license, renewal confirmation, or trial extension is available.
              </li>
              <li>
                <strong>No Hard Lockout on Outages:</strong> If your internet is unavailable, MediHisaab continues billing without interruption using your existing signed license and local hardware clock.
              </li>
              <li>
                <strong>Zero Commercial Tracking:</strong> We do not track, profile, or sell data on medicines sold, prescribing trends, or consumer purchase behavior.
              </li>
            </ul>

            <h2 style={{ fontSize: "1.45rem", fontWeight: 700, color: "#0f172a", marginTop: "2.5rem", marginBottom: "1rem" }}>
              4. Security Measures & Encryption
            </h2>
            <p style={{ marginBottom: "1.25rem" }}>
              All network transmissions between your browser, desktop application, and our Central Licensing API use Transport Layer Security (TLS 1.3 / HTTPS). Licensing tokens are signed using high-security Ed25519 elliptic curve digital signatures. Private signing keys are held strictly in secure server-side key storage and are never distributed with the desktop installer or web code.
            </p>

            <div style={{ borderTop: "1px solid #e2e8f0", paddingTop: "1.5rem", marginTop: "2rem" }}>
              <p style={{ fontSize: "0.875rem", color: "#64748b" }}>
                For inquiries regarding data privacy or security architecture, contact our technical team at{" "}
                <a href="mailto:support@apexhealth.com" style={{ color: "var(--primary)", fontWeight: 600 }}>
                  support@apexhealth.com
                </a>.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};
