import React, { useState, useEffect, useCallback } from "react";
import type { SystemHealthResponse } from "@pharmacy/api-contracts";
import { getSystemHealth } from "../api/health";

export const HealthIndicator: React.FC = () => {
  const [health, setHealth] = useState<SystemHealthResponse | null>(null);
  const [isDaemonOffline, setIsDaemonOffline] = useState<boolean>(false);
  const [isInternetOnline, setIsInternetOnline] = useState<boolean>(navigator.onLine);
  const [showDetails, setShowDetails] = useState<boolean>(false);

  const fetchHealth = useCallback(async () => {
    try {
      const data = await getSystemHealth();
      setHealth(data);
      setIsDaemonOffline(false);
    } catch {
      setIsDaemonOffline(true);
      setHealth(null);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 15000);

    const handleOnline = () => setIsInternetOnline(true);
    const handleOffline = () => setIsInternetOnline(false);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      clearInterval(interval);
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, [fetchHealth]);

  const daemonReady = !isDaemonOffline && health?.status === "HEALTHY";

  return (
    <>
      <div
        className="health-badge"
        onClick={() => setShowDetails(!showDetails)}
        title={
          daemonReady
            ? `Local POS Station: Ready & Operational\nInternet: ${isInternetOnline ? "Connected" : "Offline (App remains 100% functional)"}\nClick for connection details`
            : "Cannot connect to local POS background service"
        }
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          padding: "4px 10px",
          borderRadius: "16px",
          fontSize: "0.74rem",
          cursor: "pointer",
          background: !daemonReady
            ? "rgba(239, 68, 68, 0.15)"
            : "rgba(16, 185, 129, 0.12)",
          border: `1px solid ${!daemonReady ? "#ef4444" : "#10b981"}`,
          color: !daemonReady ? "#ef4444" : "#10b981",
        }}
      >
        <span
          style={{
            width: 7,
            height: 7,
            borderRadius: "50%",
            backgroundColor: !daemonReady ? "#ef4444" : "#10b981",
          }}
        />
        <span>
          {!daemonReady
            ? "Station Offline"
            : isInternetOnline
            ? "Ready · Cloud Sync"
            : "Ready · Offline Mode"}
        </span>
      </div>

      {showDetails && (
        <div className="modal-backdrop" onClick={() => setShowDetails(false)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 480 }}>
            <div className="modal-header">
              <div className="modal-title">
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    display: "inline-block",
                    backgroundColor: daemonReady ? "#10b981" : "#ef4444",
                    marginRight: 6,
                  }}
                />
                <span>Connection & Station Status</span>
              </div>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => setShowDetails(false)}
              >
                ✕
              </button>
            </div>
            <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {/* Section 1: Local POS Readiness */}
              <div
                style={{
                  background: "var(--bg-secondary)",
                  border: "1px solid var(--border-color)",
                  borderRadius: "var(--radius-sm)",
                  padding: "12px 14px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                  <strong style={{ fontSize: "0.88rem", color: "var(--text-main)" }}>
                    Local POS Station
                  </strong>
                  <span
                    style={{
                      fontSize: "0.72rem",
                      fontWeight: 700,
                      color: daemonReady ? "#10b981" : "#ef4444",
                    }}
                  >
                    {daemonReady ? "OPERATIONAL" : "DISCONNECTED"}
                  </span>
                </div>
                <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", margin: 0 }}>
                  {daemonReady
                    ? "Local background service is running on 127.0.0.1:38291. SQLite database is responsive."
                    : "Local pharmacy daemon is not responding. Please check that MediHisaab background service is started."}
                </p>
                {health && (
                  <div style={{ fontSize: "0.75rem", color: "var(--text-dim)", marginTop: 6, fontFamily: "var(--font-mono)" }}>
                    Daemon v{health.version} · Uptime: {Math.floor(health.uptime_seconds)}s
                  </div>
                )}
              </div>

              {/* Section 2: Internet & Licensing Cloud Connectivity */}
              <div
                style={{
                  background: "var(--bg-secondary)",
                  border: "1px solid var(--border-color)",
                  borderRadius: "var(--radius-sm)",
                  padding: "12px 14px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                  <strong style={{ fontSize: "0.88rem", color: "var(--text-main)" }}>
                    Internet & Cloud Sync
                  </strong>
                  <span
                    style={{
                      fontSize: "0.72rem",
                      fontWeight: 700,
                      color: isInternetOnline ? "#10b981" : "#eab308",
                    }}
                  >
                    {isInternetOnline ? "CONNECTED" : "OFFLINE"}
                  </span>
                </div>
                <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", margin: 0 }}>
                  {isInternetOnline
                    ? "Internet connectivity is active. License checks and online portal sync operate normally."
                    : "Internet is unavailable. This terminal is operating in offline mode. All local billing, inventory, printing, and reports remain 100% functional without internet."}
                </p>
              </div>

              {/* Section 3: Offline Resilience Info */}
              <div
                style={{
                  background: "rgba(16, 185, 129, 0.08)",
                  border: "1px solid rgba(16, 185, 129, 0.25)",
                  borderRadius: "var(--radius-sm)",
                  padding: "10px 14px",
                  fontSize: "0.8rem",
                  color: "var(--text-main)",
                }}
              >
                <strong>Offline-First Guarantee:</strong> MediHisaab never blocks customer counter sales or billing during internet outages. Data is saved locally in SQLite with cryptographic audit logs.
              </div>
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={fetchHealth}
              >
                Re-check Status
              </button>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={() => setShowDetails(false)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
