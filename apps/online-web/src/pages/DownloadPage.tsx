import React, { useState } from "react";
import { Link } from "../router/Link";
import { useAuth } from "../context/AuthContext";
import { softwareApi } from "../api/client";

export const DownloadPage: React.FC = () => {
  const { role, clientUser, token } = useAuth();
  const [downloading, setDownloading] = useState(false);
  const [downloadStatus, setDownloadStatus] = useState<string | null>(null);

  const handleDownload = async () => {
    setDownloading(true);
    setDownloadStatus(null);

    try {
      if (token) {
        await softwareApi.recordDownloadRequest("installer-windows", token);
        setDownloadStatus("Download request verified and recorded. Your download is starting...");
      }

      // Initiate download
      const link = document.createElement("a");
      link.href = "/MediHisaab-Setup-1.0.0.exe";
      link.download = "MediHisaab-Setup-1.0.0.exe";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch {
      setDownloadStatus("Starting installer download...");
      window.location.href = "/MediHisaab-Setup-1.0.0.exe";
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="page-wrapper" style={{ background: "#f8fafc", minHeight: "85vh", padding: "3rem 1rem" }}>
      <div className="container" style={{ maxWidth: "800px" }}>
        {/* Header */}
        <div style={{ textAlign: "center", marginBottom: "2rem" }}>
          <div className="hero-tag" style={{ margin: "0 auto 0.75rem auto" }}>
            Official Windows Release (v1.0.0)
          </div>
          <h1 style={{ fontSize: "2.25rem", fontWeight: 800, color: "#0f172a" }}>
            Download MediHisaab for Windows
          </h1>
          <p style={{ color: "#64748b", fontSize: "1.05rem", marginTop: "0.5rem" }}>
            Offline-first pharmacy management system, retail billing POS, and automated FEFO inventory ERP.
          </p>
        </div>

        {/* GATED CHECK: If unauthenticated, prompt to sign in or sign up */}
        {role !== "client" ? (
          <div className="card" style={{ padding: "2.5rem 2rem", textAlign: "center" }}>
            <div style={{ width: "56px", height: "56px", background: "#eff6ff", borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 1.25rem auto", fontSize: "1.75rem", color: "#2563eb" }}>
              🔒
            </div>
            <h2 style={{ fontSize: "1.4rem", fontWeight: 700, color: "#0f172a", marginBottom: "0.5rem" }}>
              Pharmacy Account Required for Download
            </h2>
            <p style={{ color: "#64748b", fontSize: "0.95rem", maxWidth: "560px", margin: "0 auto 1.75rem auto", lineHeight: 1.6 }}>
              To ensure every pharmacy receives an official Ed25519 digital evaluation license and verified software binary, please sign in or register your free trial account before downloading.
            </p>

            <div style={{ display: "flex", justifyContent: "center", gap: "1rem", flexWrap: "wrap" }}>
              <Link to="/account?next=/download" className="btn-primary-download" style={{ padding: "0.75rem 1.75rem" }}>
                Sign In to Download &rarr;
              </Link>
              <Link to="/account?tab=signup&next=/download" className="btn-secondary-trial" style={{ padding: "0.75rem 1.75rem" }}>
                Create Free Account (Start Trial)
              </Link>
            </div>

            <div style={{ borderTop: "1px solid #e2e8f0", marginTop: "2rem", paddingTop: "1.25rem", color: "#94a3b8", fontSize: "0.825rem" }}>
              ✓ 15-Day Free Evaluation • ✓ Zero Credit Card Required • ✓ 100% Offline Local Operation
            </div>
          </div>
        ) : (
          /* AUTHENTICATED DOWNLOAD INTERFACE */
          <div className="card" style={{ padding: "2.25rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem", borderBottom: "1px solid #e2e8f0", paddingBottom: "1.25rem", marginBottom: "1.5rem" }}>
              <div>
                <span className="guide-step-badge" style={{ background: "#059669" }}>
                  Verified Pharmacy Account: {clientUser?.client_code}
                </span>
                <h2 style={{ fontSize: "1.45rem", fontWeight: 700, color: "#0f172a", marginTop: "0.25rem" }}>
                  {clientUser?.business_name}
                </h2>
              </div>
              <span className="badge badge-active">Ready for Installation</span>
            </div>

            {/* Release Binary Verification Table */}
            <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "8px", padding: "1.25rem", marginBottom: "1.5rem" }}>
              <h4 style={{ fontSize: "0.9rem", fontWeight: 700, color: "#1e293b", marginBottom: "0.75rem" }}>
                Verified Release Package Metadata
              </h4>
              <div style={{ display: "grid", gridTemplateColumns: "140px 1fr", gap: "0.5rem", fontSize: "0.875rem" }}>
                <span style={{ color: "#64748b" }}>File:</span>
                <strong style={{ fontFamily: "var(--font-mono)" }}>MediHisaab-Setup-1.0.0.exe</strong>

                <span style={{ color: "#64748b" }}>Version:</span>
                <span>v1.0.0 (Commercial Production)</span>

                <span style={{ color: "#64748b" }}>File Size:</span>
                <span>91.0 MB (95,442,984 bytes)</span>

                <span style={{ color: "#64748b" }}>Operating System:</span>
                <span>Windows 10 / Windows 11 (64-bit editions)</span>

                <span style={{ color: "#64748b" }}>SHA-256 Checksum:</span>
                <code style={{ fontFamily: "var(--font-mono)", fontSize: "0.775rem", wordBreak: "break-all", background: "#f1f5f9", padding: "2px 6px", borderRadius: "4px" }}>
                  2e323e4b90768f866699b24c2aad6ba36f201e092acd65ba8cf6010b0f91c02f
                </code>
              </div>
            </div>

            {downloadStatus && (
              <div className="alert-info-box" style={{ marginBottom: "1.25rem", padding: "0.75rem 1rem", fontSize: "0.875rem" }}>
                {downloadStatus}
              </div>
            )}

            <button
              onClick={handleDownload}
              disabled={downloading}
              className="btn-primary-download"
              style={{ width: "100%", justifyContent: "center", padding: "0.9rem", fontSize: "1.1rem" }}
            >
              <svg width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2.2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              {downloading ? "Recording Request..." : "Download MediHisaab-Setup-1.0.0.exe (91.0 MB)"}
            </button>

            {/* Next Steps Guide */}
            <div style={{ marginTop: "2rem", borderTop: "1px solid #e2e8f0", paddingTop: "1.5rem" }}>
              <h3 style={{ fontSize: "1.05rem", fontWeight: 700, color: "#0f172a", marginBottom: "0.75rem" }}>
                What to do after installation:
              </h3>
              <ol style={{ paddingLeft: "1.25rem", fontSize: "0.875rem", color: "#334155", lineHeight: 1.7 }}>
                <li>Run <strong>MediHisaab-Setup-1.0.0.exe</strong> and accept the standard installation wizard.</li>
                <li>Launch MediHisaab from your Desktop shortcut.</li>
                <li>On the first-run welcome screen, click <strong>"I already have an account / Sign in"</strong>.</li>
                <li>
                  Enter your pharmacy email (<strong>{clientUser?.email}</strong>) and password. Your signed trial license activates automatically!
                </li>
                <li>Complete your store setup: add your Drug License number, GSTIN, and local cashier PINs.</li>
              </ol>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
