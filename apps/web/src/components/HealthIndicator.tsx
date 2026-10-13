import React, { useState, useEffect, useCallback } from "react";
import type { SystemHealthResponse } from "@pharmacy/api-contracts";
import { getSystemHealth } from "../api/health";

export const HealthIndicator: React.FC = () => {
  const [health, setHealth] = useState<SystemHealthResponse | null>(null);
  const [isOffline, setIsOffline] = useState<boolean>(false);
  const [showDetails, setShowDetails] = useState<boolean>(false);

  const fetchHealth = useCallback(async () => {
    try {
      const data = await getSystemHealth();
      setHealth(data);
      setIsOffline(false);
    } catch {
      setIsOffline(true);
      setHealth(null);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    // Check system status periodically
    const interval = setInterval(fetchHealth, 15000);
    return () => clearInterval(interval);
  }, [fetchHealth]);

  const statusClass = isOffline
    ? "offline"
    : health?.status === "DEGRADED"
    ? "degraded"
    : "healthy";

  const statusLabel = isOffline
    ? "Offline"
    : health?.status === "DEGRADED"
    ? "System Degraded"
    : "System Online";

  return (
    <>
      <div
        className="health-badge"
        onClick={() => setShowDetails(!showDetails)}
        title={`System status: ${statusLabel}`}
      >
        <span className={`pulse-dot ${statusClass}`} />
        <span>{statusLabel}</span>
      </div>

      {showDetails && (
        <div className="modal-backdrop" onClick={() => setShowDetails(false)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title">
                <span className={`pulse-dot ${statusClass}`} />
                <span>System Status</span>
              </div>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => setShowDetails(false)}
              >
                ✕
              </button>
            </div>
            <div className="modal-body">
              {isOffline ? (
                <div className="auth-error-banner">
                  <strong>System Offline</strong>
                  <p style={{ marginTop: 4 }}>
                    Cannot connect to the local pharmacy server. Please ensure the background service is running.
                  </p>
                </div>
              ) : health ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 10, fontSize: "0.85rem" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border-subtle)", paddingBottom: 6 }}>
                    <span style={{ color: "var(--text-muted)" }}>Status:</span>
                    <strong style={{ color: "var(--accent-success)" }}>
                      {health.status === "HEALTHY" ? "Online & Healthy" : health.status}
                    </strong>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border-subtle)", paddingBottom: 6 }}>
                    <span style={{ color: "var(--text-muted)" }}>Application Version:</span>
                    <span>v{health.version}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border-subtle)", paddingBottom: 6 }}>
                    <span style={{ color: "var(--text-muted)" }}>Service Port:</span>
                    <span style={{ fontFamily: "var(--font-mono)" }}>{health.port}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border-subtle)", paddingBottom: 6 }}>
                    <span style={{ color: "var(--text-muted)" }}>Database:</span>
                    <span style={{ color: "var(--accent-success)", fontWeight: 600 }}>Connected</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--text-muted)" }}>Uptime:</span>
                    <span>{Math.floor(health.uptime_seconds)} seconds</span>
                  </div>
                </div>
              ) : null}
            </div>
            <div className="modal-footer">
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => {
                  fetchHealth();
                }}
              >
                Refresh
              </button>
              <button
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
