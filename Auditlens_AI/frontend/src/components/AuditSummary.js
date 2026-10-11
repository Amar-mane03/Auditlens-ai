import React from "react";

function AuditSummary({ summary, data }) {
  const d = summary || data?.dashboard;
  if (!d) return null;

  const totalRevenue = typeof d.total_revenue === "number" ? d.total_revenue : 0;
  const reportUrl = data?.report_url;

  return (
    <div className="audit-summary-card">
      <h3>Executive Audit Summary</h3>
      <div className="summary-grid">
        <div className="summary-stat">
          <span className="stat-label">Total Transactions</span>
          <span className="stat-value">{d.total_transactions ?? 0}</span>
        </div>
        <div className="summary-stat">
          <span className="stat-label">Total Volume</span>
          <span className="stat-value">₹{totalRevenue.toLocaleString()}</span>
        </div>
        <div className="summary-stat">
          <span className="stat-label">High / Critical Risk</span>
          <span className="stat-value highlight-red">{d.high_risk ?? 0}</span>
        </div>
        <div className="summary-stat">
          <span className="stat-label">Potential Leakage</span>
          <span className="stat-value highlight-orange">{d.potential_leakage ?? 0}</span>
        </div>
        <div className="summary-stat">
          <span className="stat-label">Duplicate Invoices</span>
          <span className="stat-value">{d.duplicates ?? 0}</span>
        </div>
        <div className="summary-stat">
          <span className="stat-label">Open Findings</span>
          <span className="stat-value">{d.open_findings ?? 0}</span>
        </div>
      </div>
      {reportUrl && (
        <div style={{ marginTop: "12px" }}>
          <a
            href={reportUrl.startsWith("http") ? reportUrl : `http://127.0.0.1:5000${reportUrl}`}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-download"
          >
            📥 Download Full Excel Audit Report
          </a>
        </div>
      )}
    </div>
  );
}

export default AuditSummary;
