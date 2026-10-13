import React from "react";

interface PlaceholderViewProps {
  title: string;
  description: string;
  milestoneTag: string;
  iconType: "billing" | "medicines" | "suppliers" | "customers";
  shortcutKey: string;
}

export const PlaceholderView: React.FC<PlaceholderViewProps> = ({
  title,
  description,
  milestoneTag,
  iconType,
  shortcutKey,
}) => {
  return (
    <div className="placeholder-view-container">
      <div className="placeholder-icon">
        {iconType === "billing" && (
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="2" y="4" width="20" height="16" rx="2" />
            <line x1="2" y1="10" x2="22" y2="10" />
          </svg>
        )}
        {iconType === "medicines" && (
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="m10.5 20.5 10-10a4.95 4.95 0 1 0-7-7l-10 10a4.95 4.95 0 1 0 7 7Z" />
            <path d="m8.5 8.5 7 7" />
          </svg>
        )}
        {iconType === "suppliers" && (
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="1" y="3" width="15" height="13" />
            <polygon points="16 8 20 8 23 11 23 16 16 16 16 8" />
            <circle cx="5.5" cy="18.5" r="2.5" />
            <circle cx="18.5" cy="18.5" r="2.5" />
          </svg>
        )}
        {iconType === "customers" && (
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
          </svg>
        )}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <h2 className="placeholder-title">{title}</h2>
        <kbd>{shortcutKey}</kbd>
      </div>

      <p className="placeholder-desc">{description}</p>

      <div className="placeholder-roadmap-tag">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
        <span>Scheduled Deliverable: {milestoneTag}</span>
      </div>
    </div>
  );
};
