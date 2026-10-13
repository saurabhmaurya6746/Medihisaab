import React, { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useRouter } from "../router/RouterContext";
import type { EvaluationSignupPayload } from "../types";

interface TrialSignupModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const TrialSignupModal: React.FC<TrialSignupModalProps> = ({ isOpen, onClose }) => {
  const { signup } = useAuth();
  const { navigate } = useRouter();

  const [formData, setFormData] = useState<EvaluationSignupPayload>({
    email: "",
    password: "",
    pharmacy_name: "",
    contact_person: "",
    phone: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<boolean>(false);
  const [clientCode, setClientCode] = useState<string | null>(null);
  const [trialDays, setTrialDays] = useState<number>(15);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    if (formData.password.length < 8) {
      setError("Password must be at least 8 characters long.");
      setLoading(false);
      return;
    }

    try {
      const res = await signup(formData);
      setSuccess(true);
      setClientCode(res.client.client_code);
      setTrialDays(res.trial_days || 15);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("An unexpected error occurred while registering account.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleGoToDashboard = () => {
    onClose();
    navigate("/client?welcome=true");
  };

  const handleGoToDownload = () => {
    onClose();
    navigate("/download");
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close-btn" onClick={onClose} aria-label="Close modal">
          &times;
        </button>

        <div style={{ marginBottom: "1.25rem" }}>
          <span className="notice-badge">Instant Activation</span>
          <h2 style={{ fontSize: "1.5rem", fontWeight: 700, marginTop: "0.5rem", color: "#0f172a" }}>
            Start Free Pharmacy POS Evaluation
          </h2>
          <p style={{ color: "#64748b", fontSize: "0.875rem" }}>
            Register your pharmacy to receive an instant Ed25519 evaluation trial. Use these credentials to sign in and activate your installed Windows application.
          </p>
        </div>

        {error && <div className="form-error-alert">{error}</div>}

        {success ? (
          <div>
            <div className="form-success-alert">
              <strong>Trial Account Created Successfully!</strong>
              <p style={{ marginTop: "0.25rem" }}>
                Client Account Code: <strong>{clientCode}</strong>. Your {trialDays}-day full-featured evaluation trial is active.
              </p>
            </div>
            <p style={{ fontSize: "0.875rem", color: "#334155", marginBottom: "1.5rem" }}>
              Your account is ready. You can now download the Windows installer or visit your Client Dashboard to inspect license details.
            </p>
            <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
              <button
                onClick={handleGoToDownload}
                className="btn-primary-download"
                style={{ flex: 1, justifyContent: "center", padding: "0.65rem 1rem", fontSize: "0.95rem" }}
              >
                Download Installer &rarr;
              </button>
              <button
                onClick={handleGoToDashboard}
                className="btn-secondary-trial"
                style={{ flex: 1, justifyContent: "center", padding: "0.65rem 1rem", fontSize: "0.95rem" }}
              >
                Client Dashboard
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label>Pharmacy / Business Name</label>
              <input
                type="text"
                required
                placeholder="e.g. Metro Life Chemist"
                value={formData.pharmacy_name}
                onChange={(e) => setFormData({ ...formData, pharmacy_name: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label>Owner / Pharmacist Name</label>
              <input
                type="text"
                required
                placeholder="e.g. Ramesh K. Sharma"
                value={formData.contact_person}
                onChange={(e) => setFormData({ ...formData, contact_person: e.target.value })}
              />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
              <div className="form-group">
                <label>Business Email</label>
                <input
                  type="email"
                  required
                  placeholder="pharmacy@example.com"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label>Phone / Mobile</label>
                <input
                  type="tel"
                  required
                  placeholder="+91 98765 43210"
                  value={formData.phone}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                />
              </div>
            </div>

            <div className="form-group">
              <label>Account Password (min 8 characters)</label>
              <input
                type="password"
                required
                minLength={8}
                placeholder="Create secure password"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              />
              <small style={{ color: "#64748b", fontSize: "0.75rem", marginTop: "2px", display: "block" }}>
                Use this same password to sign in and activate your desktop POS after installation.
              </small>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary-download"
              style={{ width: "100%", justifyContent: "center", marginTop: "0.75rem" }}
            >
              {loading ? "Creating Pharmacy Account..." : "Create Account & Start Free Evaluation"}
            </button>

            <p style={{ textAlign: "center", fontSize: "0.75rem", color: "#94a3b8", marginTop: "1rem" }}>
              Already registered?{" "}
              <button
                type="button"
                onClick={() => {
                  onClose();
                  navigate("/account");
                }}
                style={{ background: "none", border: "none", color: "var(--primary)", fontWeight: 600, cursor: "pointer", padding: 0 }}
              >
                Sign in to your account
              </button>
            </p>
          </form>
        )}
      </div>
    </div>
  );
};
