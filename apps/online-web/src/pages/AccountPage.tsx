import React, { useState, useEffect } from "react";
import { useRouter } from "../router/RouterContext";
import { useAuth } from "../context/AuthContext";
import type { EvaluationSignupPayload } from "../types";

export const AccountPage: React.FC = () => {
  const { query, navigate } = useRouter();
  const { role, login, signup } = useAuth();

  const initialTab = query.get("tab") === "signup" ? "signup" : "signin";
  const nextDestination = query.get("next") || "/client";

  const [activeTab, setActiveTab] = useState<"signin" | "signup">(initialTab);

  // Sign In Form State
  const [signInEmail, setSignInEmail] = useState("");
  const [signInPassword, setSignInPassword] = useState("");
  const [signInLoading, setSignInLoading] = useState(false);
  const [signInError, setSignInError] = useState<string | null>(null);

  // Sign Up Form State
  const [signUpForm, setSignUpForm] = useState<EvaluationSignupPayload>({
    pharmacy_name: "",
    contact_person: "",
    email: "",
    phone: "",
    password: "",
  });
  const [signUpConfirmPassword, setSignUpConfirmPassword] = useState("");
  const [signUpLoading, setSignUpLoading] = useState(false);
  const [signUpError, setSignUpError] = useState<string | null>(null);

  // If already authenticated, redirect immediately
  useEffect(() => {
    if (role === "client") {
      navigate(nextDestination, { replace: true });
    } else if (role === "admin") {
      navigate("/vendor", { replace: true });
    }
  }, [role, nextDestination, navigate]);

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setSignInError(null);
    setSignInLoading(true);

    try {
      const res = await login({
        email: signInEmail.trim(),
        password: signInPassword,
      });

      if (res.role === "admin") {
        navigate("/vendor");
      } else {
        navigate(nextDestination);
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        setSignInError(err.message);
      } else {
        setSignInError("Invalid credentials. Please verify your email and password.");
      }
    } finally {
      setSignInLoading(false);
    }
  };

  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault();
    setSignUpError(null);

    if (signUpForm.password.length < 8) {
      setSignUpError("Password must be at least 8 characters in length.");
      return;
    }

    if (signUpForm.password !== signUpConfirmPassword) {
      setSignUpError("Passwords do not match. Please re-enter identical passwords.");
      return;
    }

    setSignUpLoading(true);

    try {
      await signup({
        ...signUpForm,
        email: signUpForm.email.trim(),
        phone: signUpForm.phone.trim(),
      });

      navigate(nextDestination.includes("download") ? "/download" : "/client?welcome=true");
    } catch (err: unknown) {
      if (err instanceof Error) {
        setSignUpError(err.message);
      } else {
        setSignUpError("Failed to create pharmacy account. Please try again.");
      }
    } finally {
      setSignUpLoading(false);
    }
  };

  return (
    <div className="page-wrapper" style={{ background: "#f8fafc", minHeight: "80vh", padding: "3rem 1rem" }}>
      <div className="auth-box-wrapper">
        <div className="auth-box-card">
          {/* Brand & Title */}
          <div style={{ textAlign: "center", marginBottom: "1.5rem" }}>
            <img src="/medihisaab-horizontal.png" alt="MediHisaab Logo" style={{ height: "38px", margin: "0 auto 0.75rem auto", display: "block" }} />
            <h1 style={{ fontSize: "1.5rem", fontWeight: 700, color: "#0f172a" }}>
              {activeTab === "signin" ? "Pharmacy & System Sign In" : "Create Pharmacy Account"}
            </h1>
            <p style={{ color: "#64748b", fontSize: "0.875rem", marginTop: "0.25rem" }}>
              {activeTab === "signin"
                ? "Unified sign in for pharmacy clients and system administrators."
                : "Register your pharmacy to receive an instant 15-day evaluation trial."}
            </p>
          </div>

          {/* Tab Selector */}
          <div className="auth-tabs-header">
            <button
              className={`auth-tab-btn ${activeTab === "signin" ? "active" : ""}`}
              onClick={() => {
                setActiveTab("signin");
                setSignInError(null);
              }}
            >
              Sign In
            </button>
            <button
              className={`auth-tab-btn ${activeTab === "signup" ? "active" : ""}`}
              onClick={() => {
                setActiveTab("signup");
                setSignUpError(null);
              }}
            >
              Create Account
            </button>
          </div>

          {/* SIGN IN TAB */}
          {activeTab === "signin" && (
            <form onSubmit={handleSignIn} className="auth-form-body">
              {signInError && <div className="form-error-alert">{signInError}</div>}

              {query.get("next") === "/download" && (
                <div className="alert-info-box" style={{ marginBottom: "1.25rem", padding: "0.75rem 1rem", background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: "6px", fontSize: "0.85rem", color: "#1e40af" }}>
                  ℹ️ Sign in with your pharmacy account to access your Windows installer download.
                </div>
              )}

              <div className="form-group">
                <label>Email Address</label>
                <input
                  type="email"
                  required
                  placeholder="pharmacy@example.com or admin@example.com"
                  value={signInEmail}
                  onChange={(e) => setSignInEmail(e.target.value)}
                  autoComplete="email"
                />
              </div>

              <div className="form-group">
                <label>Password</label>
                <input
                  type="password"
                  required
                  placeholder="Enter your password"
                  value={signInPassword}
                  onChange={(e) => setSignInPassword(e.target.value)}
                  autoComplete="current-password"
                />
              </div>

              <button
                type="submit"
                disabled={signInLoading}
                className="btn-primary-download"
                style={{ width: "100%", justifyContent: "center", marginTop: "0.5rem" }}
              >
                {signInLoading ? "Authenticating..." : "Sign In & Continue"}
              </button>

              <div style={{ marginTop: "1.5rem", borderTop: "1px solid #e2e8f0", paddingTop: "1rem", textAlign: "center" }}>
                <p style={{ fontSize: "0.825rem", color: "#64748b" }}>
                  New pharmacy owner?{" "}
                  <button
                    type="button"
                    onClick={() => setActiveTab("signup")}
                    style={{ background: "none", border: "none", color: "var(--primary)", fontWeight: 600, cursor: "pointer" }}
                  >
                    Start 15-Day Free Evaluation &rarr;
                  </button>
                </p>
                <p style={{ fontSize: "0.75rem", color: "#94a3b8", marginTop: "0.5rem" }}>
                  Administrator accounts are provisioned exclusively through vendor management.
                </p>
              </div>
            </form>
          )}

          {/* SIGN UP TAB */}
          {activeTab === "signup" && (
            <form onSubmit={handleSignUp} className="auth-form-body">
              {signUpError && <div className="form-error-alert">{signUpError}</div>}

              <div className="form-group">
                <label>Pharmacy / Chemist Store Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Metro Life Pharmacy"
                  value={signUpForm.pharmacy_name}
                  onChange={(e) => setSignUpForm({ ...signUpForm, pharmacy_name: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label>Owner / Pharmacist Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Ramesh K. Sharma"
                  value={signUpForm.contact_person}
                  onChange={(e) => setSignUpForm({ ...signUpForm, contact_person: e.target.value })}
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                <div className="form-group">
                  <label>Business Email</label>
                  <input
                    type="email"
                    required
                    placeholder="contact@pharmacy.com"
                    value={signUpForm.email}
                    onChange={(e) => setSignUpForm({ ...signUpForm, email: e.target.value })}
                    autoComplete="email"
                  />
                </div>

                <div className="form-group">
                  <label>Phone / Mobile</label>
                  <input
                    type="tel"
                    required
                    placeholder="+91 98765 43210"
                    value={signUpForm.phone}
                    onChange={(e) => setSignUpForm({ ...signUpForm, phone: e.target.value })}
                    autoComplete="tel"
                  />
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                <div className="form-group">
                  <label>Password (min 8 chars)</label>
                  <input
                    type="password"
                    required
                    minLength={8}
                    placeholder="Create secure password"
                    value={signUpForm.password}
                    onChange={(e) => setSignUpForm({ ...signUpForm, password: e.target.value })}
                    autoComplete="new-password"
                  />
                </div>

                <div className="form-group">
                  <label>Confirm Password</label>
                  <input
                    type="password"
                    required
                    minLength={8}
                    placeholder="Re-enter password"
                    value={signUpConfirmPassword}
                    onChange={(e) => setSignUpConfirmPassword(e.target.value)}
                    autoComplete="new-password"
                  />
                </div>
              </div>

              <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", padding: "0.65rem 0.85rem", borderRadius: "6px", fontSize: "0.775rem", color: "#64748b", marginBottom: "1rem" }}>
                🛡️ <strong>Single Account Identity:</strong> Use this email and password to log in here and activate your desktop installation. No credit card required.
              </div>

              <button
                type="submit"
                disabled={signUpLoading}
                className="btn-primary-download"
                style={{ width: "100%", justifyContent: "center" }}
              >
                {signUpLoading ? "Creating Pharmacy Account..." : "Create Account & Start Free Evaluation"}
              </button>

              <div style={{ marginTop: "1.25rem", borderTop: "1px solid #e2e8f0", paddingTop: "1rem", textAlign: "center" }}>
                <p style={{ fontSize: "0.825rem", color: "#64748b" }}>
                  Already have an account?{" "}
                  <button
                    type="button"
                    onClick={() => setActiveTab("signin")}
                    style={{ background: "none", border: "none", color: "var(--primary)", fontWeight: 600, cursor: "pointer" }}
                  >
                    Sign In instead
                  </button>
                </p>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
