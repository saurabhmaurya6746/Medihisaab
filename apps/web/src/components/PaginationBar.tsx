import React from "react";

interface PaginationBarProps {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
  onPageChange: (newPage: number) => void;
  onPageSizeChange?: (newPageSize: number) => void;
}

export const PaginationBar: React.FC<PaginationBarProps> = ({
  page,
  pageSize,
  total,
  totalPages,
  onPageChange,
  onPageSizeChange,
}) => {
  if (total === 0) {
    return (
      <div className="pagination-container">
        <span>No records found</span>
      </div>
    );
  }

  const startRecord = (page - 1) * pageSize + 1;
  const endRecord = Math.min(page * pageSize, total);

  return (
    <div className="pagination-container">
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <span>
          Showing <strong>{startRecord}</strong>–<strong>{endRecord}</strong> of{" "}
          <strong>{total}</strong> records
        </span>

        {onPageSizeChange && (
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>Per page:</span>
            <select
              className="select-filter"
              style={{ padding: "3px 8px", fontSize: "0.75rem" }}
              value={pageSize}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
            >
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
          </div>
        )}
      </div>

      <div className="pagination-controls">
        <button
          className="btn btn-secondary btn-sm"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
          title="Previous Page"
        >
          ‹ Prev
        </button>

        <span style={{ padding: "0 8px", fontWeight: 600, color: "var(--text-main)" }}>
          Page {page} of {totalPages}
        </span>

        <button
          className="btn btn-secondary btn-sm"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
          title="Next Page"
        >
          Next ›
        </button>
      </div>
    </div>
  );
};
