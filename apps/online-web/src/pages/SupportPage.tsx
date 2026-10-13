import React, { useState, useEffect } from "react";
import { Link } from "../router/Link";
import { softwareApi } from "../api/client";
import type { SupportContacts } from "../types";

export const SupportPage: React.FC = () => {
  const [contacts, setContacts] = useState<SupportContacts>({
    phone: "+91 98765 43210",
    whatsapp: "+91 98765 43210",
    email: "support@apexhealth.com",
  });

  useEffect(() => {
    softwareApi
      .getSupportContacts()
      .then((data) => {
        setContacts(data);
      })
      .catch(() => {});
  }, []);

  return (
    <div className="page-wrapper">
      {/* Header Banner */}
      <section className="section-container" style={{ background: "linear-gradient(180deg, #ffffff 0%, #f1f5f9 100%)", borderBottom: "1px solid var(--border-color)", padding: "3.5rem 0" }}>
        <div className="container">
          <div className="section-header" style={{ marginBottom: "1rem" }}>
            <span className="section-label">Helpdesk & Assistance</span>
            <h1 className="section-title">Technical Support & Contact Details</h1>
            <p className="section-desc">
              Dedicated technical assistance for installation, multi-counter LAN configuration, receipt printer spoolers, and license renewals.
            </p>
          </div>
        </div>
      </section>

      {/* Main Support Grid */}
      <section className="section-container">
        <div className="container">
          {/* Live Contact Cards Row */}
          <div className="dashboard-metrics-grid" style={{ marginBottom: "3rem" }}>
            {/* Phone Card */}
            <div className="dashboard-metric-card" style={{ padding: "1.75rem", textAlign: "center" }}>
              <span style={{ fontSize: "2rem", display: "block", marginBottom: "0.5rem" }}>📞</span>
              <span className="metric-lbl">Helpline Telephone</span>
              <div style={{ fontSize: "1.35rem", fontWeight: 700, margin: "0.5rem 0" }}>
                <a href={`tel:${contacts.phone.replace(/\s+/g, "")}`} style={{ color: "var(--primary)", textDecoration: "none" }}>
                  {contacts.phone}
                </a>
              </div>
              <span className="metric-sub">Mon–Sat: 9:00 AM – 8:00 PM IST</span>
            </div>

            {/* WhatsApp Card */}
            <div className="dashboard-metric-card" style={{ padding: "1.75rem", textAlign: "center" }}>
              <span style={{ fontSize: "2rem", display: "block", marginBottom: "0.5rem" }}>💬</span>
              <span className="metric-lbl">WhatsApp Support</span>
              <div style={{ fontSize: "1.35rem", fontWeight: 700, margin: "0.5rem 0" }}>
                <a
                  href={`https://wa.me/${contacts.whatsapp.replace(/[^0-9]/g, "")}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: "#059669", textDecoration: "none" }}
                >
                  {contacts.whatsapp}
                </a>
              </div>
              <span className="metric-sub">Fast text chat for setup queries</span>
            </div>

            {/* Email Card */}
            <div className="dashboard-metric-card" style={{ padding: "1.75rem", textAlign: "center" }}>
              <span style={{ fontSize: "2rem", display: "block", marginBottom: "0.5rem" }}>✉️</span>
              <span className="metric-lbl">Technical Support Email</span>
              <div style={{ fontSize: "1.2rem", fontWeight: 700, margin: "0.5rem 0" }}>
                <a href={`mailto:${contacts.email}`} style={{ color: "var(--primary)", textDecoration: "none" }}>
                  {contacts.email}
                </a>
              </div>
              <span className="metric-sub">Detailed logs, invoices & renewal requests</span>
            </div>
          </div>

          {/* Operational Guidance Guides */}
          <div className="guides-grid">
            {/* Guide 1: Installation Assistance */}
            <div className="guide-card">
              <span className="guide-step-badge">Installation</span>
              <h3 className="guide-title">Windows Setup & First-Run</h3>
              <p className="guide-desc">
                Encountering Windows SmartScreen or daemon binding issues?
              </p>
              <ul className="guide-steps" style={{ listStyle: "disc" }}>
                <li><strong>Windows Defender / SmartScreen:</strong> If Windows prompts with "Windows protected your PC", click <em>"More info"</em> and then <em>"Run anyway"</em>.</li>
                <li><strong>Port 38291 Verification:</strong> Check if the local daemon is active by opening <code>http://127.0.0.1:38291/health</code> in any browser.</li>
                <li><strong>Installation Path:</strong> Installs cleanly to <code>%LOCALAPPDATA%\Programs\MediHisaab\</code> without requiring Administrator root rights.</li>
              </ul>
            </div>

            {/* Guide 2: License Renewal Assistance */}
            <div className="guide-card">
              <span className="guide-step-badge">Licensing</span>
              <h3 className="guide-title">License Renewal & Activation</h3>
              <p className="guide-desc">
                Need to renew your trial or commercial subscription?
              </p>
              <ul className="guide-steps" style={{ listStyle: "disc" }}>
                <li><strong>Online Renewal:</strong> Sign in to your <Link to="/client" style={{ color: "var(--primary)", fontWeight: 600 }}>Client Dashboard</Link>, select your desired plan, and enter your UPI UTR or bank reference.</li>
                <li><strong>Offline File Import:</strong> If your billing computer is permanently offline, contact support to receive your signed <code>.json</code> license token via WhatsApp/email, copy it onto a USB flash drive, and click <em>"Import License File"</em> in desktop Settings.</li>
                <li><strong>7-Day Grace Protection:</strong> Remember you have 7 full grace days to renew without counter billing disruption.</li>
              </ul>
            </div>

            {/* Guide 3: Hardware & Thermal Printers */}
            <div className="guide-card">
              <span className="guide-step-badge">Hardware</span>
              <h3 className="guide-title">Printer & Scanner Spooling</h3>
              <p className="guide-desc">
                Configuring thermal receipt printers and barcode readers.
              </p>
              <ul className="guide-steps" style={{ listStyle: "disc" }}>
                <li><strong>ESC/POS Printers (80mm / 58mm):</strong> Select your printer in MediHisaab Settings &gt; Hardware. Our raw byte spooler talks directly to USB thermal printers.</li>
                <li><strong>Cash Drawers:</strong> Connect the cash drawer's RJ-11 cable directly into the back of your thermal printer (DK port). The kick pulse fires automatically on bill completion.</li>
                <li><strong>Barcode Scanners:</strong> Ensure your USB barcode reader is programmed for standard factory default <em>[CR] (Enter)</em> suffix.</li>
              </ul>
            </div>
          </div>

          {/* Emergency Escalation Notice */}
          <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "10px", padding: "1.75rem", marginTop: "3rem", textAlign: "center" }}>
            <h3 style={{ fontSize: "1.25rem", fontWeight: 700, color: "#0f172a", marginBottom: "0.5rem" }}>
              Critical Counter Stoppage Hotline
            </h3>
            <p style={{ color: "#64748b", fontSize: "0.95rem", maxWidth: "640px", margin: "0 auto 1.25rem auto" }}>
              If your pharmacy counter is experiencing an emergency during active business hours, call our direct helpline for priority assistance.
            </p>
            <a href={`tel:${contacts.phone.replace(/\s+/g, "")}`} className="btn-primary-download" style={{ padding: "0.75rem 2rem" }}>
              Call Helpline: {contacts.phone}
            </a>
          </div>
        </div>
      </section>
    </div>
  );
};
