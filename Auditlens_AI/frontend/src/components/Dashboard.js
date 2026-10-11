import React from "react";

function Dashboard({ data, onLoadSample, onNavigateSection }) {
  if (!data || !data.dashboard) {
    return (
      <div className="overview-welcome-hero">
        <div className="hero-banner">
          <div className="hero-badge">AUDITLENS ENTERPRISE SUITE • v2.1</div>
          <h2 className="hero-title">Autonomous Statutory Assurance & Financial Intelligence</h2>
          <p className="hero-subtitle">
            Unified platform combining deterministic statutory audit algorithms, automated revenue leak detection, cryptographic SHA-256 evidence logging, and machine learning fraud prediction.
          </p>

          <div className="hero-actions">
            <button onClick={onLoadSample} className="btn btn-primary btn-large">
              ✨ Launch Built-In Sample Audit (1-Click)
            </button>
            <button
              onClick={() => onNavigateSection && onNavigateSection("ingest")}
              className="btn btn-secondary btn-large"
            >
              📁 Ingest Custom Ledger (.csv / .xlsx)
            </button>
          </div>
        </div>

        <div className="hero-capabilities-grid">
          <div className="capability-card" onClick={() => onNavigateSection && onNavigateSection("radar")}>
            <div className="capability-icon">🎯</div>
            <h4>Revenue Leak Radar</h4>
            <p>Identifies unbilled contracts, discount threshold breaches, and pricing slippage across customer ledgers.</p>
            <span className="capability-link">Explore Engine →</span>
          </div>

          <div className="capability-card" onClick={() => onNavigateSection && onNavigateSection("evidence")}>
            <div className="capability-icon">🔗</div>
            <h4>Cryptographic Evidence Chain</h4>
            <p>Immutable block ledger verifying SHA-256 digests of invoices, contracts, and auditor workpaper signoffs.</p>
            <span className="capability-link">Verify Chain →</span>
          </div>

          <div className="capability-card" onClick={() => onNavigateSection && onNavigateSection("fraud")}>
            <div className="capability-icon">🛡️</div>
            <h4>ML Fraud Intelligence</h4>
            <p>Active champion gradient-boosting models providing real-time inference scoring and case management triage.</p>
            <span className="capability-link">View Models →</span>
          </div>

          <div className="capability-card" onClick={() => onNavigateSection && onNavigateSection("reports")}>
            <div className="capability-icon">📑</div>
            <h4>Statutory Reporting</h4>
            <p>One-click compilation of ISA 240 / SOX compliant workpapers with certified Excel workbook exports.</p>
            <span className="capability-link">View Reports →</span>
          </div>
        </div>
      </div>
    );
  }

  const d = data.dashboard;
  const dist = d.risk_distribution || { Low: 0, Medium: 0, High: 0, Critical: 0 };
  const totalRev = typeof d.total_revenue === "number" ? d.total_revenue : 0;
  const reportUrl = data.report_url;

  return (
    <div className="dashboard-container">
      {/* Top Banner */}
      <div className="engagement-summary-banner">
        <div>
          <span className="badge badge-low" style={{ marginBottom: "6px" }}>Engagement Active</span>
          <h3>Statutory Audit Executive Summary</h3>
          <p className="subtitle" style={{ marginBottom: 0 }}>
            Automated analysis completed across {d.total_transactions ?? 0} journal entries.
          </p>
        </div>
        {reportUrl && (
          <a
            href={reportUrl.startsWith("http") ? reportUrl : `http://127.0.0.1:5000${reportUrl}`}
            download
            className="btn btn-primary"
          >
            📥 Download Certified Report (.xlsx)
          </a>
        )}
      </div>

      <div className="metrics-grid">
        <div
          className="metric-card clickable-metric"
          onClick={() => onNavigateSection && onNavigateSection("registry")}
        >
          <div className="metric-header-row">
            <span className="metric-title">Total Transactions</span>
            <span className="metric-icon">📑</span>
          </div>
          <div className="metric-value">{d.total_transactions ?? 0}</div>
          <div className="metric-sub">Analyzed: {d.transactions_analyzed ?? 0} entries</div>
        </div>

        <div className="metric-card">
          <div className="metric-header-row">
            <span className="metric-title">Total Ledger Volume</span>
            <span className="metric-icon">💰</span>
          </div>
          <div className="metric-value">₹{totalRev.toLocaleString()}</div>
          <div className="metric-sub">Processed transaction volume</div>
        </div>

        <div
          className="metric-card alert-card clickable-metric"
          onClick={() => onNavigateSection && onNavigateSection("investigation")}
        >
          <div className="metric-header-row">
            <span className="metric-title">High & Critical Risk</span>
            <span className="metric-icon">🚨</span>
          </div>
          <div className="metric-value highlight-red">{d.high_risk ?? 0}</div>
          <div className="metric-sub">Immediate auditor triage required</div>
        </div>

        <div className="metric-card warning-card">
          <div className="metric-header-row">
            <span className="metric-title">Potential Leakage</span>
            <span className="metric-icon">⚠️</span>
          </div>
          <div className="metric-value highlight-orange">{d.potential_leakage ?? 0}</div>
          <div className="metric-sub">Unusual or outlier transaction values</div>
        </div>

        <div className="metric-card">
          <div className="metric-header-row">
            <span className="metric-title">Duplicate Invoices</span>
            <span className="metric-icon">🔁</span>
          </div>
          <div className="metric-value">{d.duplicates ?? 0}</div>
          <div className="metric-sub">Cross-referenced duplicates</div>
        </div>

        <div className="metric-card">
          <div className="metric-header-row">
            <span className="metric-title">Period-End Anomalies</span>
            <span className="metric-icon">⏳</span>
          </div>
          <div className="metric-value">{d.revenue_recognition_issues ?? 0}</div>
          <div className="metric-sub">Cutoff & round-number journal entries</div>
        </div>
      </div>

      <div className="risk-distribution-section">
        <div className="section-header" style={{ marginBottom: "16px" }}>
          <div>
            <h3>Algorithmic Risk Distribution Breakdown</h3>
            <p className="subtitle" style={{ marginBottom: 0 }}>
              Classified using statutory audit heuristics (ISA 240 / SOX) and statistical distribution scoring.
            </p>
          </div>
          <button
            onClick={() => onNavigateSection && onNavigateSection("investigation")}
            className="btn btn-secondary"
            style={{ fontSize: "12px", padding: "6px 12px" }}
          >
            Open Investigation Workbench →
          </button>
        </div>

        <div className="risk-bars">
          <div className="risk-bar-item">
            <div className="risk-bar-label">
              <span className="badge badge-critical">Critical</span>
              <span className="risk-count">{dist.Critical ?? 0} entries</span>
            </div>
            <div className="progress-bg">
              <div
                className="progress-fill progress-critical"
                style={{ width: `${d.total_transactions ? ((dist.Critical ?? 0) / d.total_transactions) * 100 : 0}%` }}
              />
            </div>
          </div>

          <div className="risk-bar-item">
            <div className="risk-bar-label">
              <span className="badge badge-high">High</span>
              <span className="risk-count">{dist.High ?? 0} entries</span>
            </div>
            <div className="progress-bg">
              <div
                className="progress-fill progress-high"
                style={{ width: `${d.total_transactions ? ((dist.High ?? 0) / d.total_transactions) * 100 : 0}%` }}
              />
            </div>
          </div>

          <div className="risk-bar-item">
            <div className="risk-bar-label">
              <span className="badge badge-medium">Medium</span>
              <span className="risk-count">{dist.Medium ?? 0} entries</span>
            </div>
            <div className="progress-bg">
              <div
                className="progress-fill progress-medium"
                style={{ width: `${d.total_transactions ? ((dist.Medium ?? 0) / d.total_transactions) * 100 : 0}%` }}
              />
            </div>
          </div>

          <div className="risk-bar-item">
            <div className="risk-bar-label">
              <span className="badge badge-low">Low</span>
              <span className="risk-count">{dist.Low ?? 0} entries</span>
            </div>
            <div className="progress-bg">
              <div
                className="progress-fill progress-low"
                style={{ width: `${d.total_transactions ? ((dist.Low ?? 0) / d.total_transactions) * 100 : 0}%` }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
