import React, { useEffect, useRef, useState } from "react";
import type { ScheduleH1Input } from "@pharmacy/api-contracts";

interface ScheduleH1ModalProps {
  isOpen: boolean;
  onClose: () => void;
  medicineName: string;
  initialData?: ScheduleH1Input | null;
  defaultCustomerName?: string;
  defaultDoctorName?: string;
  onSave: (data: ScheduleH1Input) => void;
}

export const ScheduleH1Modal: React.FC<ScheduleH1ModalProps> = ({
  isOpen,
  onClose,
  medicineName,
  initialData,
  defaultCustomerName = "",
  defaultDoctorName = "",
  onSave,
}) => {
  const [patientName, setPatientName] = useState<string>("");
  const [patientAddress, setPatientAddress] = useState<string>("");
  const [doctorName, setDoctorName] = useState<string>("");
  const [doctorAddress, setDoctorAddress] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const patientNameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setPatientName(initialData?.patient_name || defaultCustomerName || "");
      setPatientAddress(initialData?.patient_address || "");
      setDoctorName(initialData?.doctor_name || defaultDoctorName || "");
      setDoctorAddress(initialData?.doctor_address || "");
      setError(null);
      setTimeout(() => patientNameRef.current?.focus(), 50);
    }
  }, [isOpen, initialData, defaultCustomerName, defaultDoctorName]);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!patientName.trim()) {
      setError("Patient Name is a mandatory statutory requirement for Schedule H1 drugs.");
      return;
    }
    if (!patientAddress.trim()) {
      setError("Patient Address is mandatory by law under Drugs & Cosmetics Rules.");
      return;
    }
    if (!doctorName.trim()) {
      setError("Prescribing Doctor Name is mandatory for Schedule H1 dispensing.");
      return;
    }

    onSave({
      patient_name: patientName.trim(),
      patient_address: patientAddress.trim(),
      doctor_name: doctorName.trim(),
      doctor_address: doctorAddress.trim() || undefined,
    });
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="pos-modal-overlay">
      <div className="pos-modal-card" style={{ maxWidth: 540 }}>
        <div className="pos-modal-header" style={{ borderBottom: "2px solid var(--accent-danger)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span className="badge badge-danger" style={{ fontSize: "0.72rem" }}>Schedule H1</span>
            <h3>Prescription Record — {medicineName}</h3>
          </div>
          <button type="button" className="pos-modal-close" onClick={onClose} title="Close [Esc]">
            &times;
          </button>
        </div>

        <div style={{ padding: "10px 16px", backgroundColor: "rgba(239, 68, 68, 0.1)", borderBottom: "1px solid rgba(239, 68, 68, 0.2)", fontSize: "0.82rem", color: "#fca5a5" }}>
          Schedule H1 prescription drug. Patient and prescriber details are recorded for the compliance register.
        </div>

        <form onSubmit={handleSubmit}>
          <div className="pos-modal-body" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {error && (
              <div className="pos-alert pos-alert-error" style={{ margin: 0, padding: "8px 12px", fontSize: "0.85rem" }}>
                {error}
              </div>
            )}

            <div>
              <label className="pos-label" htmlFor="h1-patient-name">
                Patient Full Name <span style={{ color: "#ef4444" }}>*</span>
              </label>
              <input
                id="h1-patient-name"
                ref={patientNameRef}
                type="text"
                className="pos-input"
                placeholder="e.g. Ramesh Kumar"
                value={patientName}
                onChange={(e) => setPatientName(e.target.value)}
                required
              />
            </div>

            <div>
              <label className="pos-label" htmlFor="h1-patient-address">
                Patient Residential Address <span style={{ color: "#ef4444" }}>*</span>
              </label>
              <textarea
                id="h1-patient-address"
                className="pos-input"
                rows={2}
                placeholder="e.g. H.No 45, Sector 12, Main Market"
                value={patientAddress}
                onChange={(e) => setPatientAddress(e.target.value)}
                required
              />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div>
                <label className="pos-label" htmlFor="h1-doctor-name">
                  Prescribing Doctor <span style={{ color: "#ef4444" }}>*</span>
                </label>
                <input
                  id="h1-doctor-name"
                  type="text"
                  className="pos-input"
                  placeholder="e.g. Dr. A. K. Verma"
                  value={doctorName}
                  onChange={(e) => setDoctorName(e.target.value)}
                  required
                />
              </div>

              <div>
                <label className="pos-label" htmlFor="h1-doctor-address">
                  Clinic / Hospital Address
                </label>
                <input
                  id="h1-doctor-address"
                  type="text"
                  className="pos-input"
                  placeholder="e.g. Civil Hospital, Ward 3"
                  value={doctorAddress}
                  onChange={(e) => setDoctorAddress(e.target.value)}
                />
              </div>
            </div>
          </div>

          <div className="pos-modal-footer" style={{ display: "flex", justifyContent: "space-between" }}>
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Cancel [Esc]
            </button>
            <button type="submit" className="btn btn-danger">
              Save H1 Record [Enter]
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
