import React, { useState } from "react";
import { Link } from "../router/Link";
import { useRouter } from "../router/RouterContext";
import { useAuth } from "../context/AuthContext";

interface FaqItem {
  question: string;
  category: "General" | "Billing" | "Hardware & LAN" | "Licensing & Backup";
  answer: string | React.ReactNode;
}

export const FaqPage: React.FC = () => {
  const { navigate } = useRouter();
  const { role } = useAuth();
  const [selectedCategory, setSelectedCategory] = useState<string>("All");
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  const handleDownloadClick = (e: React.MouseEvent) => {
    e.preventDefault();
    if (role === "client") {
      navigate("/download");
    } else {
      navigate("/account?next=/download");
    }
  };

  const faqs: FaqItem[] = [
    {
      question: "Does MediHisaab need an active internet connection to bill medicines?",
      category: "Billing",
      answer: (
        <>
          <strong>No.</strong> Daily billing, medicine stock lookup, FEFO batch selection, blister strip loose tablet cutting, and receipt printing are 100% offline. The database runs locally on your PC via SQLite Write-Ahead Logging (WAL). An internet connection is needed only once during initial setup to activate your signed digital license, or when renewing subscriptions.
        </>
      ),
    },
    {
      question: "How do I start using MediHisaab after downloading the installer?",
      category: "General",
      answer: (
        <>
          The workflow takes less than 3 minutes:
          <ol style={{ paddingLeft: "1.25rem", marginTop: "0.5rem" }}>
            <li>Run <code>MediHisaab-Setup-1.0.0.exe</code> and finish the standard installation wizard.</li>
            <li>Launch MediHisaab from your Desktop shortcut.</li>
            <li>On the welcome screen, choose <em>"I already have an account / Sign in"</em> and enter your pharmacy email and password. Your signed trial license activates automatically.</li>
            <li>Complete the store setup wizard with your pharmacy name, Drug License No., and GSTIN.</li>
          </ol>
        </>
      ),
    },
    {
      question: "Can I run multiple billing counters across my store simultaneously?",
      category: "Hardware & LAN",
      answer: (
        <>
          <strong>Yes.</strong> MediHisaab includes built-in Multi-Counter LAN Server Mode running on port 38291. Your primary computer acts as the local store server. Secondary counter terminals connect via store Wi-Fi or Ethernet by opening <code>http://[SERVER-IP]:38291</code> in any standard web browser (Chrome, Edge, Firefox). SQLite WAL concurrency allows all counters to bill simultaneously without data conflicts.
        </>
      ),
    },
    {
      question: "What happens when my free evaluation trial expires?",
      category: "Licensing & Backup",
      answer: (
        <>
          When your evaluation period ends, MediHisaab automatically enters a <strong>7-day operational grace period</strong>. Your pharmacy counters will continue to bill medicines normally without interruption, displaying a polite countdown reminder. You can submit a renewal request from your Client Dashboard or contact vendor support anytime during the grace period.
        </>
      ),
    },
    {
      question: "Can I sell loose tablets from a blister strip?",
      category: "Billing",
      answer: (
        <>
          <strong>Yes.</strong> MediHisaab has built-in blister strip fractional cutting math. When selling loose tablets (for example, 4 tablets from a strip of 10), enter the loose quantity directly. The system calculates exact fractional MRP and landed cost pricing without floating-point rounding errors.
        </>
      ),
    },
    {
      question: "Is the Schedule H1 drug register compliant with Drug Inspector rules?",
      category: "Billing",
      answer: (
        <>
          <strong>Yes.</strong> MediHisaab enforces regulatory compliance under Rule 65(3)(h) of the Drugs and Cosmetics Rules. When dispensing Schedule H1 restricted antibiotics or habit-forming medicines, the system prompts for patient name, address, prescribing doctor, and batch ID. You can instantly export statutory registers to CSV or print official audit reports for Drug Inspector inspections.
        </>
      ),
    },
    {
      question: "Which thermal receipt printers and barcode scanners are supported?",
      category: "Hardware & LAN",
      answer: (
        <>
          MediHisaab features a direct ESC/POS raw byte spooler. All standard USB ESC/POS thermal printers (both 80mm and 58mm formats) from brands like Epson (TM-T82), TVS (RP-3200), Posiflex, NGX, and Everycom are supported. Any standard USB HID barcode scanner programmed for factory default Enter (Carriage Return) suffix works out-of-the-box. Standard RJ-11 cash drawers trigger automatically via printer kick pulse.
        </>
      ),
    },
    {
      question: "How do I take backups of my pharmacy records?",
      category: "Licensing & Backup",
      answer: (
        <>
          MediHisaab includes an automated hot backup engine utilizing SQLite's <code>VACUUM INTO</code> mechanism. You can create a hot backup anytime from Settings &gt; Disaster Recovery without stopping active counter billing. The system produces a compressed <code>.pbk</code> archive with a SHA-256 cryptographic manifest. We recommend copying backup files to an external USB flash drive weekly.
        </>
      ),
    },
    {
      question: "How do I renew my license if my store computer has no internet access?",
      category: "Licensing & Backup",
      answer: (
        <>
          MediHisaab supports 100% offline license renewal via <strong>Signed License Import</strong>. After submitting your renewal, vendor support can send you your renewed signed license file (<code>.json</code>) via WhatsApp or email. Copy this file to a USB flash drive, plug it into your store computer, open MediHisaab Settings &gt; Licensing, and click <em>"Import License File"</em>. The daemon validates the Ed25519 cryptographic signature locally and updates your validity immediately.
        </>
      ),
    },
    {
      question: "Are local cashier accounts kept separate from my web account?",
      category: "General",
      answer: (
        <>
          <strong>Yes.</strong> Your central web account credentials (email and password) are used only for licensing entitlements, client portal access, and the initial 1-time desktop activation. Your local pharmacy cashier PINs, staff usernames, and store administrator credentials reside strictly in your local store's database and are never uploaded to the licensing server.
        </>
      ),
    },
  ];

  const categories = ["All", "General", "Billing", "Hardware & LAN", "Licensing & Backup"];

  const filteredFaqs = selectedCategory === "All"
    ? faqs
    : faqs.filter((f) => f.category === selectedCategory);

  return (
    <div className="page-wrapper">
      {/* Header Banner */}
      <section className="section-container" style={{ background: "linear-gradient(180deg, #ffffff 0%, #f1f5f9 100%)", borderBottom: "1px solid var(--border-color)", padding: "3.5rem 0" }}>
        <div className="container">
          <div className="section-header" style={{ marginBottom: "1rem" }}>
            <span className="section-label">Questions & Answers</span>
            <h1 className="section-title">Frequently Asked Questions</h1>
            <p className="section-desc">
              Practical answers to operational questions about installation, offline billing, hardware peripherals, and licensing.
            </p>
          </div>
        </div>
      </section>

      {/* Main FAQ Accordion Section */}
      <section className="section-container">
        <div className="container" style={{ maxWidth: "860px" }}>
          {/* Category Filter Tabs */}
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", justifyContent: "center", marginBottom: "2rem" }}>
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`btn ${selectedCategory === cat ? "btn-primary" : "btn-secondary"}`}
                style={{ borderRadius: "20px", padding: "0.4rem 1rem", fontSize: "0.85rem" }}
              >
                {cat}
              </button>
            ))}
          </div>

          {/* Accordion List */}
          <div className="faq-accordion-list">
            {filteredFaqs.map((faq, idx) => {
              const isOpen = openIndex === idx;
              return (
                <div key={idx} className="faq-item-card" style={{ background: "#ffffff", border: "1px solid var(--border-color)", borderRadius: "8px", marginBottom: "1rem", overflow: "hidden" }}>
                  <button
                    onClick={() => setOpenIndex(isOpen ? null : idx)}
                    style={{ width: "100%", padding: "1.25rem 1.5rem", background: "none", border: "none", display: "flex", justifyContent: "space-between", alignItems: "center", textAlign: "left", cursor: "pointer", gap: "1rem" }}
                  >
                    <span style={{ fontSize: "1.05rem", fontWeight: 700, color: "#0f172a" }}>
                      {faq.question}
                    </span>
                    <span style={{ fontSize: "1.25rem", color: "var(--primary)", fontWeight: "bold" }}>
                      {isOpen ? "−" : "+"}
                    </span>
                  </button>

                  {isOpen && (
                    <div style={{ padding: "0 1.5rem 1.25rem 1.5rem", borderTop: "1px solid #f1f5f9", color: "#475569", fontSize: "0.95rem", lineHeight: 1.7, marginTop: "0.5rem" }}>
                      {faq.answer}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Help Contact Banner */}
          <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "10px", padding: "1.75rem", marginTop: "3rem", textAlign: "center" }}>
            <h3 style={{ fontSize: "1.2rem", fontWeight: 700, color: "#0f172a", marginBottom: "0.5rem" }}>
              Have a specific question not covered here?
            </h3>
            <p style={{ color: "#64748b", fontSize: "0.925rem", marginBottom: "1.25rem" }}>
              Our support team is available by telephone, WhatsApp, and email to assist you.
            </p>
            <div style={{ display: "flex", justifyContent: "center", gap: "1rem", flexWrap: "wrap" }}>
              <Link to="/support" className="btn-secondary-trial">
                Visit Support Helpdesk
              </Link>
              <a href="/download" onClick={handleDownloadClick} className="btn-primary-download">
                Download Free Evaluation
              </a>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};
