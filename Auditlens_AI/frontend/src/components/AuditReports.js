import React from "react";

function AuditReports({ auditData, onTriggerSample }) {
  const d = auditData?.dashboard;
  const reportUrl = auditData?.report_url;
  const reportFilename = auditData?.report_filename || "statutory_audit_report.xlsx";
  const findingsCount = auditData?.investigation?.length || 0;

  const downloadHref = reportUrl
    ? reportUrl.startsWith("http")
      ? reportUrl
      : `http://127.0.0.1:5000${reportUrl}`
    : null;

  return (
    <div className="reports-section-container">
      <div className="section-header">
        <div>
          <h2>Statutory Audit Reports & Compliance Documentation</h2>
          <p className="subtitle">
            Generate, certify, and download ISA 240 / SOX compliant workpapers, Excel audit trails, and executive finding packs.
          </p>
        </div>
      </div>

      {auditData ? (
        <div className="report-deck-grid">
          {/* Main Active Report Card */}
          <div className="report-active-card">
            <div className="report-badge-row">
              <span className="badge badge-low">Generated & Certified</span>
              <span className="report-format-tag">XLSX • Excel Workbook</span>
            </div>
            <div className="report-title-row">
              <div className="report-icon-box">📊</div>
              <div>
                <h3>Comprehensive Audit Finding Ledger</h3>
                <p className="report-file-name">{reportFilename}</p>
              </div>
            </div>

            <div className="report-meta-grid">
              <div className="report-meta-item">
                <span className="report-meta-label">Transactions Analyzed</span>
                <span className="report-meta-val">{d?.total_transactions ?? findingsCount}</span>
              </div>
              <div className="report-meta-item">
                <span className="report-meta-label">Anomalies Documented</span>
                <span className="report-meta-val highlight-red">{d?.high_risk ?? 0} Critical / High</span>
              </div>
              <div className="report-meta-item">
                <span className="report-meta-label">Total Volume Verified</span>
                <span className="report-meta-val">₹{(d?.total_revenue || 0).toLocaleString()}</span>
              </div>
              <div className="report-meta-item">
                <span className="report-meta-label">Audit Engine Version</span>
                <span className="report-meta-val">AuditLens Enterprise v2.1</span>
              </div>
            </div>

            <div className="report-actions-row">
              {downloadHref ? (
                <a
                  href={downloadHref}
                  download={reportFilename}
                  className="btn btn-primary btn-large"
                >
                  📥 Download Certified Excel Workpaper (.xlsx)
                </a>
              ) : (
                <button disabled className="btn btn-secondary">
                  Report Generating...
                </button>
              )}
            </div>
          </div>

          {/* Statutory Signoff Box */}
          <div className="statutory-signoff-card">
            <h4>📋 Statutory Compliance & Workpaper Checklist</h4>
            <div className="checklist-items">
              <div className="checklist-item">
                <span className="check-icon">✓</span>
                <div>
                  <strong>ISA 240 Fraud Anomaly Scan</strong>
                  <p>Comprehensive algorithmic test for journal entry manipulations and round-sum anomalies.</p>
                </div>
              </div>
              <div className="checklist-item">
                <span className="check-icon">✓</span>
                <div>
                  <strong>Duplicate Invoice & Dual-Billing Check</strong>
                  <p>Cross-referenced vendor IDs, invoice amounts, and date proximity indices.</p>
                </div>
              </div>
              <div className="checklist-item">
                <span className="check-icon">✓</span>
                <div>
                  <strong>Period-End Revenue Cutoff Verification</strong>
                  <p>Analyzed transaction spikes and reversal patterns within 48h of accounting closes.</p>
                </div>
              </div>
              <div className="checklist-item">
                <span className="check-icon">✓</span>
                <div>
                  <strong>Cryptographic Audit Trail Ready</strong>
                  <p>Hashes eligible for notarization into the SHA-256 immutable evidence ledger.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="empty-state-card">
          <div className="empty-state-icon">📑</div>
          <h3>No Audit Run Loaded Yet</h3>
          <p>
            Upload a transaction ledger or run our sample dataset to automatically generate certified Excel workpapers and statutory anomaly reports.
          </p>
          <div style={{ marginTop: "16px" }}>
            <button onClick={onTriggerSample} className="btn btn-primary">
              ✨ Load Built-In Sample Dataset & Generate Report
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default AuditReports;

