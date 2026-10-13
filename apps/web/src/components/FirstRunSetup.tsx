import React, { useState, useEffect } from "react";
import type { FirstRunSetupInput } from "@pharmacy/api-contracts";
import { useAuth } from "../context/AuthContext";
import { MEDIHISAAB_ICON_BASE64 } from "../assets/brand";

interface FirstRunSetupProps {
  initialPrefill?: {
    store_name?: string;
    store_phone?: string;
    store_dl?: string;
    store_gstin?: string;
  };
}

export const FirstRunSetup: React.FC<FirstRunSetupProps> = ({ initialPrefill }) => {
  const { performFirstRunSetup, error: globalError, clearError, storeName } = useAuth();

  const [formData, setFormData] = useState<FirstRunSetupInput>({
    store_name: initialPrefill?.store_name || storeName || "",
    store_address: "",
    store_phone: initialPrefill?.store_phone || "",
    store_dl_number_20b: initialPrefill?.store_dl || "",
    store_dl_number_21b: "",
    store_gstin: initialPrefill?.store_gstin || "",
    username: "",
    full_name: "",
    password: "",
    confirm_password: "",
    pin: "",
  });

  useEffect(() => {
    if (initialPrefill) {
      setFormData((prev) => ({
        ...prev,
        store_name: initialPrefill.store_name || prev.store_name,
        store_phone: initialPrefill.store_phone || prev.store_phone,
        store_dl_number_20b: initialPrefill.store_dl || prev.store_dl_number_20b,
        store_gstin: initialPrefill.store_gstin || prev.store_gstin,
      }));
    } else if (storeName && !formData.store_name) {
      setFormData((prev) => ({ ...prev, store_name: storeName }));
    }
  }, [initialPrefill, storeName]);

  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [localError, setLocalError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};

    if (!formData.store_name.trim()) {
      errors.store_name = "Pharmacy / Store Name is required.";
    }

    if (!formData.full_name.trim()) {
      errors.full_name = "Administrator Full Name is required.";
    }

    if (!formData.username.trim()) {
      errors.username = "Username is required.";
    } else if (formData.username.trim().length < 3) {
      errors.username = "Username must be at least 3 characters.";
    }

    if (!formData.password) {
      errors.password = "Password is required.";
    } else if (formData.password.length < 6) {
      errors.password = "Password must be at least 6 characters.";
    }

    if (formData.password !== formData.confirm_password) {
      errors.confirm_password = "Passwords do not match.";
    }

    if (formData.pin && !/^\d{4}$/.test(formData.pin)) {
      errors.pin = "PIN must be exactly 4 numeric digits.";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (fieldErrors[name]) {
      setFieldErrors((prev) => {
        const updated = { ...prev };
        delete updated[name];
        return updated;
      });
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    setLocalError(null);

    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);
    try {
      const payload: FirstRunSetupInput = {
        store_name: formData.store_name.trim(),
        store_address: formData.store_address?.trim() || null,
        store_phone: formData.store_phone?.trim() || null,
        store_dl_number_20b: formData.store_dl_number_20b?.trim() || null,
        store_dl_number_21b: formData.store_dl_number_21b?.trim() || null,
        store_gstin: formData.store_gstin?.trim() || null,
        username: formData.username.trim(),
        full_name: formData.full_name.trim(),
        password: formData.password,
        confirm_password: formData.confirm_password,
        pin: formData.pin?.trim() || null,
      };

      await performFirstRunSetup(payload);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "First-run initialization failed.";
      setLocalError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const displayError = localError || globalError;

  return (
    <div className="auth-page-wrapper">
      <div className="auth-modal-box auth-modal-wide">
        <div className="auth-header">
          <div className="auth-brand-logo" style={{ background: "transparent", width: "56px", height: "56px" }}>
            <img
              src={MEDIHISAAB_ICON_BASE64}
              alt="MediHisaab"
              style={{ width: "56px", height: "56px", objectFit: "contain" }}
            />
          </div>
          <h1 className="auth-title">MediHisaab — First-Run Store Initialization</h1>
          <p className="auth-subtitle">
            Step 2 of 2: Create Local Store Administrator & Configure Station Details
          </p>
        </div>

        <div className="auth-body">
          {displayError && (
            <div className="auth-error-banner">
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                style={{ flexShrink: 0, marginTop: 2 }}
              >
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              <span>{displayError}</span>
            </div>
          )}

          <form onSubmit={handleSubmit}>
            {/* Section 1: Store Identification */}
            <div style={{ marginBottom: 20 }}>
              <h3
                style={{
                  fontSize: "0.95rem",
                  fontWeight: 700,
                  color: "#38bdf8",
                  borderBottom: "1px solid var(--border-subtle)",
                  paddingBottom: 6,
                  marginBottom: 12,
                }}
              >
                1. Pharmacy & Store Details
              </h3>

              <div className="form-group">
                <label className="form-label form-label-required" htmlFor="setup-store-name">
                  Store / Chemist Name
                </label>
                <input
                  id="setup-store-name"
                  name="store_name"
                  className={`form-input ${fieldErrors.store_name ? "form-input-error" : ""}`}
                  type="text"
                  placeholder="e.g. Apex Health & Medicos"
                  value={formData.store_name}
                  onChange={handleChange}
                  disabled={isSubmitting}
                  autoFocus
                />
                {fieldErrors.store_name && (
                  <span className="form-error-text">{fieldErrors.store_name}</span>
                )}
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div className="form-group">
                  <label className="form-label" htmlFor="setup-store-phone">
                    Contact Phone
                  </label>
                  <input
                    id="setup-store-phone"
                    name="store_phone"
                    className="form-input"
                    type="text"
                    placeholder="e.g. 011-23456789 / 9876543210"
                    value={formData.store_phone || ""}
                    onChange={handleChange}
                    disabled={isSubmitting}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="setup-store-gstin">
                    GSTIN (Optional)
                  </label>
                  <input
                    id="setup-store-gstin"
                    name="store_gstin"
                    className="form-input"
                    type="text"
                    placeholder="e.g. 07AAAAA0000A1Z5"
                    value={formData.store_gstin || ""}
                    onChange={handleChange}
                    disabled={isSubmitting}
                  />
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div className="form-group">
                  <label className="form-label" htmlFor="setup-dl-20b">
                    Drug License 20B (Retail)
                  </label>
                  <input
                    id="setup-dl-20b"
                    name="store_dl_number_20b"
                    className="form-input"
                    type="text"
                    placeholder="e.g. DL-20B-12345"
                    value={formData.store_dl_number_20b || ""}
                    onChange={handleChange}
                    disabled={isSubmitting}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="setup-dl-21b">
                    Drug License 21B (Retail)
                  </label>
                  <input
                    id="setup-dl-21b"
                    name="store_dl_number_21b"
                    className="form-input"
                    type="text"
                    placeholder="e.g. DL-21B-12345"
                    value={formData.store_dl_number_21b || ""}
                    onChange={handleChange}
                    disabled={isSubmitting}
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="setup-store-address">
                  Physical Store Address
                </label>
                <input
                  id="setup-store-address"
                  name="store_address"
                  className="form-input"
                  type="text"
                  placeholder="e.g. Shop No 4, Market Complex, Main Road"
                  value={formData.store_address || ""}
                  onChange={handleChange}
                  disabled={isSubmitting}
                />
              </div>
            </div>

            {/* Section 2: Store Owner / Administrator Credentials */}
            <div>
              <h3
                style={{
                  fontSize: "0.95rem",
                  fontWeight: 700,
                  color: "#38bdf8",
                  borderBottom: "1px solid var(--border-subtle)",
                  paddingBottom: 6,
                  marginBottom: 12,
                }}
              >
                2. Store Owner (ADMIN) Account
              </h3>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div className="form-group">
                  <label className="form-label form-label-required" htmlFor="setup-admin-user">
                    Admin Username
                  </label>
                  <input
                    id="setup-admin-user"
                    name="username"
                    className={`form-input ${fieldErrors.username ? "form-input-error" : ""}`}
                    type="text"
                    placeholder="e.g. admin or dr_sharma"
                    value={formData.username}
                    onChange={handleChange}
                    disabled={isSubmitting}
                  />
                  {fieldErrors.username && (
                    <span className="form-error-text">{fieldErrors.username}</span>
                  )}
                </div>

                <div className="form-group">
                  <label className="form-label form-label-required" htmlFor="setup-admin-name">
                    Full Name
                  </label>
                  <input
                    id="setup-admin-name"
                    name="full_name"
                    className={`form-input ${fieldErrors.full_name ? "form-input-error" : ""}`}
                    type="text"
                    placeholder="e.g. Dr. Rajesh Sharma"
                    value={formData.full_name}
                    onChange={handleChange}
                    disabled={isSubmitting}
                  />
                  {fieldErrors.full_name && (
                    <span className="form-error-text">{fieldErrors.full_name}</span>
                  )}
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div className="form-group">
                  <label className="form-label form-label-required" htmlFor="setup-admin-pass">
                    Admin Password
                  </label>
                  <input
                    id="setup-admin-pass"
                    name="password"
                    className={`form-input ${fieldErrors.password ? "form-input-error" : ""}`}
                    type="password"
                    placeholder="Minimum 6 characters"
                    value={formData.password}
                    onChange={handleChange}
                    disabled={isSubmitting}
                  />
                  {fieldErrors.password && (
                    <span className="form-error-text">{fieldErrors.password}</span>
                  )}
                </div>

                <div className="form-group">
                  <label className="form-label form-label-required" htmlFor="setup-admin-confirm">
                    Confirm Password
                  </label>
                  <input
                    id="setup-admin-confirm"
                    name="confirm_password"
                    className={`form-input ${fieldErrors.confirm_password ? "form-input-error" : ""}`}
                    type="password"
                    placeholder="Repeat password"
                    value={formData.confirm_password}
                    onChange={handleChange}
                    disabled={isSubmitting}
                  />
                  {fieldErrors.confirm_password && (
                    <span className="form-error-text">{fieldErrors.confirm_password}</span>
                  )}
                </div>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="setup-admin-pin">
                  Optional 4-Digit Cashier Switch PIN
                </label>
                <input
                  id="setup-admin-pin"
                  name="pin"
                  className={`form-input ${fieldErrors.pin ? "form-input-error" : ""}`}
                  type="password"
                  maxLength={4}
                  placeholder="e.g. 5678 (numeric)"
                  value={formData.pin || ""}
                  onChange={handleChange}
                  disabled={isSubmitting}
                />
                <span className="form-help-text">
                  Enables rapid counter handover and lock/unlock without typing full password.
                </span>
                {fieldErrors.pin && <span className="form-error-text">{fieldErrors.pin}</span>}
              </div>
            </div>

            <div style={{ marginTop: 24 }}>
              <button
                type="submit"
                className="btn btn-primary"
                style={{ width: "100%", padding: "12px 20px", fontSize: "1rem" }}
                disabled={isSubmitting}
              >
                {isSubmitting ? "Initializing Pharmacy System..." : "Complete Setup & Enter Terminal"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};
