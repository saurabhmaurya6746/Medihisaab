import React, { useState, useEffect } from "react";
import { Link } from "../router/Link";
import { softwareApi } from "../api/client";
import type { SupportContacts } from "../types";

export const Footer: React.FC = () => {
  const [contacts, setContacts] = useState<SupportContacts>({
    phone: "+91 98765 43210",
    whatsapp: "+91 98765 43210",
    email: "support@apexhealth.com",
  });

  useEffect(() => {
    softwareApi.getSupportContacts().then(setContacts).catch(() => {});
  }, []);

  return (
    <footer className="footer-container" id="support">
      <div className="container footer-grid">
        <div className="footer-brand">
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "0.75rem" }}>
            <img
              src="/medihisaab-horizontal.png"
              alt="MediHisaab Logo"
              style={{ height: "36px", filter: "brightness(0) invert(1)" }}
            />
          </div>
          <p>
            MediHisaab is an offline-first retail pharmacy management system and POS ERP engineered for Indian retail chemists. Built for high-speed keyboard billing, automated FEFO batch allocation, Rule 65(3)(h) Schedule H1 statutory records, customer Khata ledger, and local multi-counter LAN concurrency.
          </p>
          <div style={{ marginTop: "1rem", fontSize: "0.825rem", color: "#64748b" }}>
            <span>Architecture: Single-Port Local FastAPI Daemon (Port 38291) • SQLite WAL Concurrency • React 19 Frontend</span>
          </div>
        </div>

        <div className="footer-col">
          <h4>Product & Navigation</h4>
          <ul>
            <li><Link to="/product">Features & Capabilities</Link></li>
            <li><Link to="/how-it-works">7-Step Deployment Guide</Link></li>
            <li><Link to="/plans">Plans & Free Evaluation</Link></li>
            <li><Link to="/download">Windows Installer Download</Link></li>
            <li><Link to="/about">About MediHisaab</Link></li>
            <li><Link to="/faq">Frequently Asked Questions</Link></li>
          </ul>
        </div>

        <div className="footer-col">
          <h4>Trust & Operations</h4>
          <ul>
            <li><Link to="/support">Technical Support & Helpdesk</Link></li>
            <li><Link to="/privacy">Local Data Privacy Guarantee</Link></li>
            <li><Link to="/account">Pharmacy Account Sign In</Link></li>
            <li><a href="/vendor">Vendor Administration Console</a></li>
            <li><strong>Helpline:</strong> <a href={`tel:${contacts.phone.replace(/\s+/g, "")}`}>{contacts.phone}</a></li>
            <li><strong>Support Email:</strong> <a href={`mailto:${contacts.email}`}>{contacts.email}</a></li>
          </ul>
        </div>
      </div>

      <div className="container footer-bottom">
        <p>
          MediHisaab &copy; 2026 Apex Health Software Solutions. Commercial Retail Pharmacy Management System. All rights reserved. Zero customer e-commerce or medicine shopping features. All pharmacy sales and stock inventory remain strictly local.
        </p>
      </div>
    </footer>
  );
};
