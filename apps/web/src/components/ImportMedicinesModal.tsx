import React, { useState, useRef } from "react";
import type {
  MedicineImportPreviewResponse,
  MedicineImportRow,
  DuplicatePolicy,
  MedicineImportExecuteResponse,
} from "@pharmacy/api-contracts";
import {
  downloadMedicineImportTemplate,
  previewMedicineImport,
  executeMedicineImport,
} from "../api/masters";

interface ImportMedicinesModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const ImportMedicinesModal: React.FC<ImportMedicinesModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isPreviewLoading, setIsPreviewLoading] = useState<boolean>(false);
  const [previewData, setPreviewData] = useState<MedicineImportPreviewResponse | null>(null);
  const [duplicatePolicy, setDuplicatePolicy] = useState<DuplicatePolicy>("SKIP");
  const [isExecuting, setIsExecuting] = useState<boolean>(false);
  const [isDownloadingSample, setIsDownloadingSample] = useState<boolean>(false);
  const [executeResult, setExecuteResult] = useState<MedicineImportExecuteResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleFileChange = async (file: File) => {
    setSelectedFile(file);
    setErrorMessage(null);
    setExecuteResult(null);
    setIsPreviewLoading(true);

    try {
      const data = await previewMedicineImport(file);
      setPreviewData(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to analyze import file";
      setErrorMessage(msg);
      setPreviewData(null);
    } finally {
      setIsPreviewLoading(false);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      handleFileChange(file);
    }
  };

  const handleExecute = async () => {
    if (!previewData) return;
    setIsExecuting(true);
    setErrorMessage(null);

    try {
      const res = await executeMedicineImport({
        staging_token: previewData.staging_token,
        duplicate_policy: duplicatePolicy,
        rows: previewData.rows,
      });
      setExecuteResult(res);
      onSuccess();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to execute medicine import";
      setErrorMessage(msg);
    } finally {
      setIsExecuting(false);
    }
  };

  const handleDownloadSample = async (format: "csv" | "xlsx") => {
    setIsDownloadingSample(true);
    setErrorMessage(null);
    try {
      await downloadMedicineImportTemplate(format);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Could not download the medicines sample file");
    } finally {
      setIsDownloadingSample(false);
    }
  };

  const handleReset = () => {
    setSelectedFile(null);
    setPreviewData(null);
    setExecuteResult(null);
    setErrorMessage(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose} style={{ zIndex: 1100 }}>
      <div
        className="modal-dialog"
        onClick={(e) => e.stopPropagation()}
        style={{
          maxWidth: 960,
          width: "92vw",
          maxHeight: "88vh",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Header */}
        <div className="modal-header">
          <div className="modal-title">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            <span>Import Medicines Catalog</span>
          </div>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Close modal">
            ✕
          </button>
        </div>

        {/* Modal Body */}
        <div className="modal-body" style={{ overflowY: "auto", display: "flex", flexDirection: "column", gap: 16 }}>
          {errorMessage && (
            <div className="auth-error-banner" style={{ margin: 0 }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Template Download strip */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 12,
              padding: "12px 16px",
              background: "var(--bg-secondary)",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-color)",
            }}
          >
            <div>
              <div style={{ fontSize: "0.9rem", fontWeight: 600, color: "var(--text-main)" }}>
                Medicines Sample File & Template
              </div>
              <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginTop: 2 }}>
                Download a ready-to-edit sample with example medicines, then replace the examples with your catalog data. Existing medicines can be skipped or updated during import.
              </div>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => void handleDownloadSample("xlsx")}
                disabled={isDownloadingSample}
                title="Download Excel sample file with example medicine rows"
              >
                Download Sample Excel (.xlsx)
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => void handleDownloadSample("csv")}
                disabled={isDownloadingSample}
                title="Download CSV sample file with example medicine rows"
              >
                Download Sample CSV
              </button>
            </div>
          </div>

          {/* Success summary view */}
          {executeResult ? (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 16,
                padding: 24,
                textAlign: "center",
                background: "rgba(16, 185, 129, 0.08)",
                border: "1px solid rgba(16, 185, 129, 0.3)",
                borderRadius: "var(--radius-md)",
              }}
            >
              <div style={{ color: "#10b981", fontSize: "1.2rem", fontWeight: 700 }}>
                {executeResult.message}
              </div>
              <div style={{ display: "flex", justifyContent: "center", gap: 20, flexWrap: "wrap" }}>
                <div style={{ background: "var(--bg-panel)", padding: "10px 18px", borderRadius: 6, border: "1px solid var(--border-color)" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Inserted New</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: 700, color: "#10b981" }}>{executeResult.inserted_count}</div>
                </div>
                <div style={{ background: "var(--bg-panel)", padding: "10px 18px", borderRadius: 6, border: "1px solid var(--border-color)" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Updated Existing</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: 700, color: "#3b82f6" }}>{executeResult.updated_count}</div>
                </div>
                <div style={{ background: "var(--bg-panel)", padding: "10px 18px", borderRadius: 6, border: "1px solid var(--border-color)" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Skipped</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: 700, color: "#eab308" }}>{executeResult.skipped_count}</div>
                </div>
                {executeResult.failed_count > 0 && (
                  <div style={{ background: "var(--bg-panel)", padding: "10px 18px", borderRadius: 6, border: "1px solid var(--border-color)" }}>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Failed</div>
                    <div style={{ fontSize: "1.3rem", fontWeight: 700, color: "#ef4444" }}>{executeResult.failed_count}</div>
                  </div>
                )}
              </div>
              <div style={{ marginTop: 10 }}>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => {
                    handleReset();
                    onClose();
                  }}
                >
                  Done & Refresh Catalog
                </button>
              </div>
            </div>
          ) : !previewData ? (
            /* Upload dropzone */
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
              style={{
                border: "2px dashed var(--border-color)",
                borderRadius: "var(--radius-lg)",
                padding: "36px 20px",
                textAlign: "center",
                background: "var(--bg-secondary)",
                cursor: "pointer",
                transition: "border-color 0.2s",
              }}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv, .xlsx, .xls, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, text/csv"
                style={{ display: "none" }}
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    handleFileChange(e.target.files[0]);
                  }
                }}
              />
              <svg
                width="40"
                height="40"
                viewBox="0 0 24 24"
                fill="none"
                stroke="var(--accent-primary)"
                strokeWidth="1.5"
                style={{ margin: "0 auto 12px" }}
              >
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
              <div style={{ fontSize: "1rem", fontWeight: 600, color: "var(--text-main)" }}>
                {isPreviewLoading ? "Analyzing and validating rows..." : "Click or drag & drop CSV or Excel file here"}
              </div>
              <div style={{ fontSize: "0.82rem", color: "var(--text-muted)", marginTop: 6 }}>
                Supports .xlsx and .csv files. Rows are previewed and validated before saving.
              </div>
            </div>
          ) : (
            /* Preview mode */
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {/* File Info and Controls Strip */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: 12,
                  padding: "10px 14px",
                  background: "var(--bg-secondary)",
                  borderRadius: "var(--radius-md)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ fontWeight: 600, color: "var(--text-main)", fontSize: "0.9rem" }}>
                    {selectedFile?.name}
                  </span>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                    ({((selectedFile?.size || 0) / 1024).toFixed(1)} KB)
                  </span>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={handleReset}
                    style={{ fontSize: "0.76rem" }}
                  >
                    Change File
                  </button>
                </div>

                {/* Duplicate Policy Toggle */}
                <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.82rem" }}>
                  <span style={{ color: "var(--text-muted)", fontWeight: 500 }}>Duplicate Policy:</span>
                  <label style={{ display: "inline-flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
                    <input
                      type="radio"
                      name="medDuplicatePolicy"
                      value="SKIP"
                      checked={duplicatePolicy === "SKIP"}
                      onChange={() => setDuplicatePolicy("SKIP")}
                    />
                    <span>Skip Existing</span>
                  </label>
                  <label style={{ display: "inline-flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
                    <input
                      type="radio"
                      name="medDuplicatePolicy"
                      value="UPDATE"
                      checked={duplicatePolicy === "UPDATE"}
                      onChange={() => setDuplicatePolicy("UPDATE")}
                    />
                    <span>Update Existing</span>
                  </label>
                </div>
              </div>

              {/* Status Metric Chips */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: 8 }}>
                <div style={{ padding: "8px 12px", background: "var(--bg-panel)", borderRadius: 6, border: "1px solid var(--border-color)" }}>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>Total In File</div>
                  <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--text-main)" }}>{previewData.total_rows}</div>
                </div>
                <div style={{ padding: "8px 12px", background: "rgba(16, 185, 129, 0.08)", borderRadius: 6, border: "1px solid rgba(16, 185, 129, 0.25)" }}>
                  <div style={{ fontSize: "0.72rem", color: "#10b981" }}>New Medicines</div>
                  <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "#10b981" }}>{previewData.valid_rows}</div>
                </div>
                <div style={{ padding: "8px 12px", background: "rgba(234, 179, 8, 0.08)", borderRadius: 6, border: "1px solid rgba(234, 179, 8, 0.25)" }}>
                  <div style={{ fontSize: "0.72rem", color: "#eab308" }}>Duplicates in Catalog</div>
                  <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "#eab308" }}>{previewData.duplicate_rows}</div>
                </div>
                <div style={{ padding: "8px 12px", background: "rgba(239, 68, 68, 0.08)", borderRadius: 6, border: "1px solid rgba(239, 68, 68, 0.25)" }}>
                  <div style={{ fontSize: "0.72rem", color: "#ef4444" }}>Invalid Rows</div>
                  <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "#ef4444" }}>{previewData.error_rows}</div>
                </div>
              </div>

              {/* Preview Rows Table */}
              <div
                style={{
                  maxHeight: "360px",
                  overflowY: "auto",
                  border: "1px solid var(--border-color)",
                  borderRadius: "var(--radius-md)",
                }}
              >
                <table className="data-table" style={{ fontSize: "0.82rem", margin: 0 }}>
                  <thead>
                    <tr>
                      <th style={{ width: 45 }}>#</th>
                      <th>Brand Name & Salt</th>
                      <th style={{ width: 110 }}>Form & Pack</th>
                      <th style={{ width: 140 }}>Manufacturer</th>
                      <th style={{ width: 85 }}>GST</th>
                      <th style={{ width: 100 }}>Status</th>
                      <th>Validation Feedback</th>
                    </tr>
                  </thead>
                  <tbody>
                    {previewData.rows.map((row: MedicineImportRow) => {
                      const isErr = row.status === "INVALID";
                      const isDup = row.status === "DUPLICATE";
                      return (
                        <tr
                          key={row.row_number}
                          style={{
                            backgroundColor: isErr
                              ? "rgba(239, 68, 68, 0.07)"
                              : isDup
                              ? "rgba(234, 179, 8, 0.05)"
                              : undefined,
                          }}
                        >
                          <td style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                            {row.row_number}
                          </td>
                          <td>
                            <strong style={{ color: "var(--text-main)" }}>{row.brand_name || "(Blank)"}</strong>
                            <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
                              {row.generic_salt || "No composition"}
                            </div>
                          </td>
                          <td>
                            <span>{row.dosage_form}</span>
                            <span style={{ color: "var(--text-muted)", marginLeft: 4 }}>
                              ({row.pack_size} units)
                            </span>
                          </td>
                          <td style={{ color: "var(--text-muted)" }}>
                            {row.manufacturer_name || "—"}
                          </td>
                          <td>{row.gst_rate}%</td>
                          <td>
                            <span
                              style={{
                                fontSize: "0.7rem",
                                fontWeight: 600,
                                padding: "2px 6px",
                                borderRadius: 4,
                                textTransform: "uppercase",
                                backgroundColor: isErr
                                  ? "#ef4444"
                                  : isDup
                                  ? "#d97706"
                                  : "#10b981",
                                color: "#ffffff",
                              }}
                            >
                              {row.status}
                            </span>
                          </td>
                          <td>
                            {row.errors && row.errors.length > 0 ? (
                              <div style={{ color: "#ef4444", fontSize: "0.76rem" }}>
                                {row.errors.join("; ")}
                              </div>
                            ) : isDup ? (
                              <span style={{ color: "#d97706", fontSize: "0.76rem" }}>
                                {duplicatePolicy === "UPDATE"
                                  ? "Will update existing catalog entry"
                                  : "Will skip (already exists)"}
                              </span>
                            ) : (
                              <span style={{ color: "#10b981", fontSize: "0.76rem" }}>Ready to create</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="modal-footer" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            {previewData && !executeResult && (
              <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                {previewData.error_rows > 0
                  ? `Note: ${previewData.error_rows} invalid row(s) will be automatically skipped.`
                  : "All rows are valid and ready to import."}
              </span>
            )}
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={isExecuting}>
              {executeResult ? "Close" : "Cancel"}
            </button>
            {previewData && !executeResult && (
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleExecute}
                disabled={isExecuting || (previewData.valid_rows === 0 && previewData.duplicate_rows === 0)}
              >
                {isExecuting
                  ? "Importing..."
                  : `Commit Import (${previewData.valid_rows + (duplicatePolicy === "UPDATE" ? previewData.duplicate_rows : 0)} items)`}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
