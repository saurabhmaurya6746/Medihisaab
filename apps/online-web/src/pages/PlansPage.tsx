import React, { useState, useEffect } from "react";
import { useRouter } from "../router/RouterContext";
import { useAuth } from "../context/AuthContext";
import { softwareApi } from "../api/client";
import type { ClientPlan } from "../types";

interface PlansPageProps {
  onOpenTrial: () => void;
}

export const PlansPage: React.FC<PlansPageProps> = ({ onOpenTrial }) => {
  const { navigate } = useRouter();
  const { role } = useAuth();
  const [plans, setPlans] = useState<ClientPlan[]>([]);

  useEffect(() => {
    softwareApi
      .getCommercialPlans()
      .then((data) => {
        setPlans(data);
      })
      .catch(() => {});
  }, []);

  const formatPrice = (paise: number) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(paise / 100);
  };

  const handleStartTrial = () => {
    if (role === "client") {
      navigate("/client");
    } else {
      onOpenTrial();
    }
  };

  const handleRenewClick = () => {
    if (role === "client") {
      navigate("/client#renew");
    } else {
      navigate("/account?next=/client");
    }
  };

  return (
    <div className="page-wrapper">
      {/* Header Banner */}
      <section className="section-container" style={{ background: "linear-gradient(180deg, #ffffff 0%, #f1f5f9 100%)", borderBottom: "1px solid var(--border-color)", padding: "3.5rem 0" }}>
        <div className="container">
          <div className="section-header" style={{ marginBottom: "1rem" }}>
            <span className="section-label">Transparent Licensing</span>
            <h1 className="section-title">Evaluation Trial & Commercial Plans</h1>
            <p className="section-desc">
              Straightforward pricing for standalone chemists and multi-terminal pharmacy stores. No hidden transaction cuts or forced merchant hardware.
            </p>
          </div>
        </div>
      </section>

      {/* Pricing Cards Grid */}
      <section className="section-container">
        <div className="container">
          <div className="pricing-grid">
            {/* Free Trial Card */}
            <div className="pricing-card">
              <div className="pricing-badge">Evaluation Trial</div>
              <h3 className="pricing-title">15-Day Free Evaluation</h3>
              <p className="pricing-desc">
                Evaluate full retail billing, FEFO batch allocation, Schedule H1 registers, and hot backups on your Windows PC.
              </p>
              <div className="pricing-price-box">
                <span className="pricing-amount">₹0</span>
                <span className="pricing-period">/ 15 days</span>
              </div>
              <ul className="pricing-features">
                <li><span className="pricing-check">&check;</span> 1 Full Terminal Counter</li>
                <li><span className="pricing-check">&check;</span> Sub-second keyboard billing (F2)</li>
                <li><span className="pricing-check">&check;</span> Loose tablet blister cutting</li>
                <li><span className="pricing-check">&check;</span> Rule 65(3)(h) Schedule H1 Register</li>
                <li><span className="pricing-check">&check;</span> Customer Khata credit & aging buckets</li>
                <li><span className="pricing-check">&check;</span> Automated hot SQLite backups (.pbk)</li>
                <li><span className="pricing-check">&check;</span> Ed25519 cryptographically signed license</li>
              </ul>
              <button onClick={handleStartTrial} className="btn-primary-download" style={{ width: "100%", justifyContent: "center" }}>
                {role === "client" ? "View in Dashboard" : "Start 15-Day Free Trial"}
              </button>
            </div>

            {/* Dynamic Commercial Plans */}
            {plans.map((p) => {
              const isAnnual = p.plan_code.toLowerCase().includes("annual");
              return (
                <div key={p.id} className={`pricing-card ${isAnnual ? "pricing-featured" : ""}`}>
                  {isAnnual && <div className="pricing-badge featured-badge">Recommended for Multi-Counter</div>}
                  <h3 className="pricing-title">{p.name}</h3>
                  <p className="pricing-desc">{p.description}</p>
                  <div className="pricing-price-box">
                    <span className="pricing-amount">{formatPrice(p.price)}</span>
                    <span className="pricing-period">
                      / {p.duration_days >= 365 ? "year" : `${p.duration_days} days`}
                    </span>
                  </div>
                  <ul className="pricing-features">
                    <li><span className="pricing-check">&check;</span> Up to {p.maximum_terminals} Concurrent Workstations</li>
                    <li><span className="pricing-check">&check;</span> Multi-counter LAN concurrency (Port 38291)</li>
                    <li><span className="pricing-check">&check;</span> 100% Offline local database operations</li>
                    <li><span className="pricing-check">&check;</span> High-speed distributor purchase inwarding (F3)</li>
                    <li><span className="pricing-check">&check;</span> Rule 65(3)(h) Drug Inspector compliance export</li>
                    <li><span className="pricing-check">&check;</span> ESC/POS thermal receipt & laser tax invoice printing</li>
                    <li><span className="pricing-check">&check;</span> 7-Day operational grace period on renewal</li>
                    {isAnnual && <li><span className="pricing-check">&check;</span> Priority telephone hotline support</li>}
                  </ul>
                  <button onClick={handleRenewClick} className={isAnnual ? "btn-primary-download" : "btn-secondary-trial"} style={{ width: "100%", justifyContent: "center" }}>
                    {role === "client" ? "Select Plan in Dashboard" : "Sign In to Choose Plan"}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Renewal & Grace Period Policy */}
      <section className="section-container" style={{ background: "#f8fafc", borderTop: "1px solid var(--border-color)", borderBottom: "1px solid var(--border-color)" }}>
        <div className="container">
          <div className="section-header">
            <span className="section-label">Fair & Predictable</span>
            <h2 className="section-title">How Renewal and Grace Periods Work</h2>
            <p className="section-desc">
              We do not automatically charge credit cards or disable your store counter during business hours.
            </p>
          </div>

          <div className="guides-grid">
            <div className="guide-card">
              <span className="guide-step-badge">Renewal Policy</span>
              <h3 className="guide-title">Manual, Transparent Renewal</h3>
              <p className="guide-desc">
                When renewal is due, the pharmacy owner submits a renewal request directly from the Client Dashboard or desktop app with a payment reference (e.g. UPI UTR or bank transfer receipt).
              </p>
              <ul className="feature-bullets">
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> Zero automatic card recurring debits without your approval.</li>
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> Payment references are reviewed and approved by the vendor administration.</li>
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> A renewed Ed25519 digital license is issued immediately upon confirmation.</li>
              </ul>
            </div>

            <div className="guide-card">
              <span className="guide-step-badge">Safety Margin</span>
              <h3 className="guide-title">7-Day Operational Grace Period</h3>
              <p className="guide-desc">
                If your trial or commercial plan expires, MediHisaab provides an automatic 7-day grace window. Your pharmacy counter continues to bill medicines normally without stoppage.
              </p>
              <ul className="feature-bullets">
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> The desktop app displays a polite remaining-days countdown.</li>
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> Billing, printing, and inventory lookup remain fully operational.</li>
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> You can contact support or submit a renewal anytime during the grace period.</li>
              </ul>
            </div>

            <div className="guide-card">
              <span className="guide-step-badge">Offline Support</span>
              <h3 className="guide-title">Offline License Import</h3>
              <p className="guide-desc">
                If your store computer has no internet access during renewal, you can receive your signed license token (<code>.json</code>) on a mobile device or USB drive and import it locally.
              </p>
              <ul className="feature-bullets">
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> Works 100% offline via 'Import License File' in Settings.</li>
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> Cryptographically verified against the server's public key.</li>
                <li className="feature-bullet"><span className="feature-bullet-check">&check;</span> Immediate local activation without dialing remote APIs.</li>
              </ul>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};
