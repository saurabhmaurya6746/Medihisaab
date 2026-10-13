import React from "react";
import { Link } from "../router/Link";

export const NotFoundPage: React.FC = () => {
  return (
    <div className="page-wrapper" style={{ padding: "5rem 1rem", textAlign: "center", minHeight: "70vh" }}>
      <div className="container" style={{ maxWidth: "560px" }}>
        <span style={{ fontSize: "3rem", display: "block", marginBottom: "1rem" }}>🔍</span>
        <h1 style={{ fontSize: "2rem", fontWeight: 800, color: "#0f172a", marginBottom: "0.5rem" }}>
          Page Not Found (404)
        </h1>
        <p style={{ color: "#64748b", fontSize: "1rem", marginBottom: "2rem", lineHeight: 1.6 }}>
          The requested page could not be located. Please verify the URL or navigate to one of the main sections below.
        </p>

        <div style={{ display: "flex", justifyContent: "center", gap: "1rem", flexWrap: "wrap" }}>
          <Link to="/" className="btn-primary-download">
            Return to Home
          </Link>
          <Link to="/product" className="btn-secondary-trial">
            View Capabilities
          </Link>
          <Link to="/download" className="btn-secondary-trial">
            Download POS
          </Link>
        </div>
      </div>
    </div>
  );
};
