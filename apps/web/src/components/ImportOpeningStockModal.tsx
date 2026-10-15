import React, { useState, useRef } from "react";
import type {
  OpeningStockImportPreviewResponse,
  OpeningStockImportRow,
  OpeningStockDuplicatePolicy,
  OpeningStockImportExecuteResponse,
} from "@pharmacy/api-contracts";
import { formatRupees } from "@pharmacy/api-contracts";
import {
  downloadOpeningStockImportTemplate,
  previewOpeningStockImport,
  executeOpeningStockImport,
} from "../api/inventory";

interface ImportOpeningStockModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const ImportOpeningStockModal: React.FC<ImportOpeningStockModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isPreviewLoading, setIsPreviewLoading] = useState<boolean>(false);
  const [previewData, setPreviewData] = useState<OpeningStockImportPreviewResponse | null>(null);
  const [duplicatePolicy, setDuplicatePolicy] = useState<OpeningStockDuplicatePolicy>("SKIP");
  const [isExecuting, setIsExecuting] = useState<boolean>(false);
  const [executeResult, setExecuteResult] = useState<OpeningStockImportExecuteResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleFileChange = async (file: File) => {
    setSelectedFile(file);
    setErrorMessage(null);
    setExecuteResult(null);
    // Do not leave the previous file's preview/commit action visible while the
    // newly selected file is being analyzed.
    setPreviewData(null);
    setIsPreviewLoading(true);

    try {
      const data = await previewOpeningStockImport(file);
      setPreviewData(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to analyze opening stock file";
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
      const res = await executeOpeningStockImport({
        staging_token: previewData.staging_token,
        duplicate_policy: duplicatePolicy,
        rows: previewData.rows,
      });
      setExecuteResult(res);
      onSuccess();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to execute opening stock import";
      setErrorMessage(msg);
    } finally {
      setIsExecuting(false);
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
          maxWidth: 1000,
          width: "94vw",
          maxHeight: "90vh",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Header */}
        <div className="modal-header">
          <div className="modal-title">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
              <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
            </svg>
            <span>Import Opening Stock & Batches</span>
          </div>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Close modal">
            ✕
          </button>
        </div>

        {/* Modal Body */}
        <div className="modal-body" style={{ overflowY: "auto", display: "flex", flexDirection: "column", gap: 16 }}>
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
                Opening Stock Sample File & Template
              </div>
              <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginTop: 2 }}>
                Download a ready-to-edit sample with example batches. Import its matching medicines first, then replace the sample quantities and batch details with your own.
              </div>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => downloadOpeningStockImportTemplate("xlsx")}
                title="Download Excel sample file with example opening-stock batches"
              >
                Download Sample Excel (.xlsx)
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => downloadOpeningStockImportTemplate("csv")}
                title="Download CSV sample file with example opening-stock batches"
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
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Batches Created</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: 700, color: "#10b981" }}>{executeResult.inserted_batches}</div>
                </div>
                <div style={{ background: "var(--bg-panel)", padding: "10px 18px", borderRadius: 6, border: "1px solid var(--border-color)" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Batches Merged</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: 700, color: "#3b82f6" }}>{executeResult.merged_batches}</div>
                </div>
                <div style={{ background: "var(--bg-panel)", padding: "10px 18px", borderRadius: 6, border: "1px solid var(--border-color)" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Batches Skipped</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: 700, color: "#eab308" }}>{executeResult.skipped_batches}</div>
                </div>
                <div style={{ background: "var(--bg-panel)", padding: "10px 18px", borderRadius: 6, border: "1px solid var(--border-color)" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Total Units Added</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: 700, color: "var(--accent-primary)" }}>{executeResult.total_units_added}</div>
                </div>
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
                  Done & Refresh Inventory
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
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              <div style={{ fontSize: "1rem", fontWeight: 600, color: "var(--text-main)" }}>
                {isPreviewLoading ? "Validating batch stock rows..." : "Click or drag & drop Opening Stock CSV or Excel file"}
              </div>
              <div style={{ fontSize: "0.82rem", color: "var(--text-muted)", marginTop: 6 }}>
                Validates medicine names against your master catalog, checks expiry dates, and verifies PTR/MRP.
              </div>
            </div>
          ) : (
            /* Preview mode */
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {/* File Info and Duplicate Policy */}
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
                    className="btn btn-secondary btn-sm"
                    onClick={() => {
                      if (fileInputRef.current) {
                        fileInputRef.current.value = "";
                        fileInputRef.current.click();
                      }
                    }}
                    style={{ fontSize: "0.8rem", padding: "4px 10px", display: "inline-flex", alignItems: "center", gap: 6, fontWeight: 600 }}
                    title="Choose a different file to preview"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="17 8 12 3 7 8" />
                      <line x1="12" y1="15" x2="12" y2="3" />
                    </svg>
                    <span>Change File</span>
                  </button>
                </div>

                {/* Duplicate Policy */}
                <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.82rem" }}>
                  <span style={{ color: "var(--text-muted)", fontWeight: 500 }}>Duplicate Batch Policy:</span>
                  <label style={{ display: "inline-flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
                    <input
                      type="radio"
                      name="openingStockDupPolicy"
                      value="SKIP"
                      checked={duplicatePolicy === "SKIP"}
                      onChange={() => setDuplicatePolicy("SKIP")}
                    />
                    <span>Skip Existing</span>
                  </label>
                  <label style={{ display: "inline-flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
                    <input
                      type="radio"
                      name="openingStockDupPolicy"
                      value="MERGE"
                      checked={duplicatePolicy === "MERGE"}
                      onChange={() => setDuplicatePolicy("MERGE")}
                    />
                    <span>Merge (Add Quantity)</span>
                  </label>
                </div>
              </div>

              {/* Status Chips */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: 8 }}>
                <div style={{ padding: "8px 12px", background: "var(--bg-panel)", borderRadius: 6, border: "1px solid var(--border-color)" }}>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>Total Rows</div>
                  <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--text-main)" }}>{previewData.total_rows}</div>
                </div>
                <div style={{ padding: "8px 12px", background: "rgba(16, 185, 129, 0.08)", borderRadius: 6, border: "1px solid rgba(16, 185, 129, 0.25)" }}>
                  <div style={{ fontSize: "0.72rem", color: "#10b981" }}>New Batches</div>
                  <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "#10b981" }}>{previewData.valid_rows}</div>
                </div>
                <div style={{ padding: "8px 12px", background: "rgba(234, 179, 8, 0.08)", borderRadius: 6, border: "1px solid rgba(234, 179, 8, 0.25)" }}>
                  <div style={{ fontSize: "0.72rem", color: "#eab308" }}>Existing Batches</div>
                  <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "#eab308" }}>{previewData.duplicate_rows}</div>
                </div>
                <div style={{ padding: "8px 12px", background: "rgba(239, 68, 68, 0.08)", borderRadius: 6, border: "1px solid rgba(239, 68, 68, 0.25)" }}>
                  <div style={{ fontSize: "0.72rem", color: "#ef4444" }}>Invalid Rows</div>
                  <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "#ef4444" }}>{previewData.error_rows}</div>
                </div>
              </div>

              {/* Warning Banner if all rows invalid */}
              {previewData.valid_rows === 0 && previewData.duplicate_rows === 0 && (
                <div
                  style={{
                    padding: "12px 16px",
                    background: "rgba(239, 68, 68, 0.12)",
                    border: "1px solid rgba(239, 68, 68, 0.35)",
                    borderRadius: "var(--radius-md)",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: 12,
                  }}
                >
                  <div style={{ fontSize: "0.84rem", color: "#f87171" }}>
                    <strong>⚠️ No valid opening stock batches found in this file.</strong>
                    <div style={{ marginTop: 3, color: "var(--text-muted)", fontSize: "0.78rem" }}>
                      This file may be a Medicines Catalog master file. Opening Stock requires Batch Number, Expiry Date, and Packs Quantity.
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => {
                      if (fileInputRef.current) {
                        fileInputRef.current.value = "";
                        fileInputRef.current.click();
                      }
                    }}
                    style={{ fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 6 }}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="17 8 12 3 7 8" />
                      <line x1="12" y1="15" x2="12" y2="3" />
                    </svg>
                    <span>Choose Different File</span>
                  </button>
                </div>
              )}

              {/* Preview Table */}
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
                      <th>Medicine</th>
                      <th style={{ width: 110 }}>Batch No</th>
                      <th style={{ width: 95 }}>Expiry</th>
                      <th style={{ width: 85 }}>Quantity</th>
                      <th style={{ width: 80 }}>PTR</th>
                      <th style={{ width: 80 }}>MRP</th>
                      <th style={{ width: 95 }}>Status</th>
                      <th>Validation Feedback</th>
                    </tr>
                  </thead>
                  <tbody>
                    {previewData.rows.map((row: OpeningStockImportRow) => {
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
                            <strong style={{ color: "var(--text-main)" }}>{row.medicine_name || "(Blank)"}</strong>
                            {row.medicine_code && (
                              <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                                {row.medicine_code}
                              </div>
                            )}
                          </td>
                          <td style={{ fontFamily: "var(--font-mono)" }}>{row.batch_number}</td>
                          <td style={{ fontFamily: "var(--font-mono)" }}>{row.expiry_date}</td>
                          <td>
                            <strong>{row.quantity}</strong> packs
                            <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                              ({row.quantity * row.pack_size} units)
                            </div>
                          </td>
                          <td>{formatRupees(row.purchase_rate_paise)}</td>
                          <td>{formatRupees(row.mrp_paise)}</td>
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
                                {duplicatePolicy === "MERGE"
                                  ? `Existing batch (${row.existing_quantity} units) will be increased by ${row.quantity * row.pack_size} units`
                                  : `Batch exists (${row.existing_quantity} units). Will skip.`}
                              </span>
                            ) : (
                              <span style={{ color: "#10b981", fontSize: "0.76rem" }}>Ready to create batch</span>
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
                  : "All rows passed verification."}
              </span>
            )}
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            {previewData && !executeResult && (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => {
                  if (fileInputRef.current) {
                    fileInputRef.current.value = "";
                    fileInputRef.current.click();
                  }
                }}
                disabled={isExecuting}
                style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
                <span>Select New File</span>
              </button>
            )}
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
                  ? "Importing Opening Stock..."
                  : `Commit Import (${previewData.valid_rows + (duplicatePolicy === "MERGE" ? previewData.duplicate_rows : 0)} batches)`}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
