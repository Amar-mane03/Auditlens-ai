import React, { useState } from "react";

function Investigation({ transactions, onLoadSample }) {
  const [filterRisk, setFilterRisk] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [decisions, setDecisions] = useState({});

  if (!transactions || transactions.length === 0) {
    return (
      <div className="empty-state-card">
        <div className="empty-state-icon">🔎</div>
        <h3>No Ingested Transactions in Workbench</h3>
        <p>
          To inspect AI-flagged anomalies, review raw evidentiary findings, and record statutory judgements, ingest a ledger or launch our test audit.
        </p>
        {onLoadSample && (
          <div style={{ marginTop: "16px" }}>
            <button onClick={onLoadSample} className="btn btn-primary">
              ✨ Load Built-In Sample Audit Dataset
            </button>
          </div>
        )}
      </div>
    );
  }

  const handleDecisionToggle = (id) => {
    setDecisions((prev) => {
      const current = prev[id] || "Pending";
      const next = current === "Pending" ? "Reviewed" : current === "Reviewed" ? "Escalated" : "Pending";
      return { ...prev, [id]: next };
    });
  };

  const filtered = transactions.filter((t) => {
    if (filterRisk !== "ALL" && t.classification !== filterRisk) {
      return false;
    }
    if (searchQuery.trim() !== "") {
      const q = searchQuery.toLowerCase();
      const idMatch = String(t.transaction_id || "").toLowerCase().includes(q);
      const custMatch = String(t.customer_id || "").toLowerCase().includes(q);
      const vendMatch = String(t.vendor_id || "").toLowerCase().includes(q);
      const flagMatch = Array.isArray(t.flags) && t.flags.some((f) => f.toLowerCase().includes(q));
      return idMatch || custMatch || vendMatch || flagMatch;
    }
    return true;
  });

  const reviewedCount = Object.values(decisions).filter((d) => d === "Reviewed").length;
  const escalatedCount = Object.values(decisions).filter((d) => d === "Escalated").length;
  const pendingCount = transactions.length - reviewedCount - escalatedCount;

  return (
    <div className="investigation-container">
      {/* Top Banner / Triage Counters */}
      <div className="triage-status-bar">
        <div className="triage-stat">
          <span className="triage-label">Total Flagged:</span>
          <span className="triage-val">{transactions.length}</span>
        </div>
        <div className="triage-divider"></div>
        <div className="triage-stat">
          <span className="triage-label">Pending Review:</span>
          <span className="triage-val highlight-orange">{pendingCount}</span>
        </div>
        <div className="triage-divider"></div>
        <div className="triage-stat">
          <span className="triage-label">Auditor Verified:</span>
          <span className="triage-val highlight-green">{reviewedCount}</span>
        </div>
        <div className="triage-divider"></div>
        <div className="triage-stat">
          <span className="triage-label">Escalated to Management:</span>
          <span className="triage-val highlight-red">{escalatedCount}</span>
        </div>
      </div>

      <div className="section-header">
        <div>
          <h2>Auditor Investigation Workbench</h2>
          <p className="subtitle">
            Inspect AI-flagged anomalies, review raw evidentiary data, and record auditor judgements.
          </p>
        </div>
        <div className="filter-controls">
          <input
            type="text"
            placeholder="Search anomaly, customer, vendor, flags..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="search-input"
            style={{ width: "260px" }}
          />
          <select
            value={filterRisk}
            onChange={(e) => setFilterRisk(e.target.value)}
            className="filter-select"
          >
            <option value="ALL">All Risk Levels ({transactions.length})</option>
            <option value="Critical">Critical</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
            <option value="Low">Low</option>
          </select>
        </div>
      </div>

      <div className="table-responsive">
        <table className="audit-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Amount</th>
              <th>Risk Score</th>
              <th>Classification</th>
              <th>Flagged Reasons</th>
              <th>Customer / Vendor</th>
              <th>Supporting Evidence</th>
              <th>AI Explanation</th>
              <th>Auditor Action</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((t, idx) => {
              const id = t.transaction_id ?? `txn-${idx}`;
              const decision = decisions[id] || t.auditor_decision || "Pending";
              const flagsText = Array.isArray(t.flags)
                ? (t.flags.length > 0 ? t.flags.join(", ") : "None")
                : String(t.flags || "None");
              const classificationClass = `badge badge-${(t.classification || "low").toLowerCase()}`;

              return (
                <tr key={id}>
                  <td className="font-mono">{t.transaction_id}</td>
                  <td style={{ fontWeight: 600 }}>₹{Number(t.amount || 0).toLocaleString()}</td>
                  <td>
                    <span className="score-pill">{t.risk_score}</span>
                  </td>
                  <td>
                    <span className={classificationClass}>{t.classification}</span>
                  </td>
                  <td className="flags-cell">{flagsText}</td>
                  <td>
                    <div style={{ fontSize: "12px", lineHeight: "1.3" }}>
                      <div><strong>Cust:</strong> {t.customer_id || "N/A"}</div>
                      <div style={{ color: "#64748b" }}><strong>Vend:</strong> {t.vendor_id || "N/A"}</div>
                    </div>
                  </td>
                  <td className="evidence-cell">
                    <span title={t.supporting_evidence}>{t.supporting_evidence || "None"}</span>
                  </td>
                  <td className="explanation-cell">{t.ai_explanation}</td>
                  <td>
                    <button
                      onClick={() => handleDecisionToggle(id)}
                      className={`btn btn-decision btn-${decision.toLowerCase()}`}
                      title="Click to cycle status: Pending -> Reviewed -> Escalated"
                    >
                      {decision === "Pending" ? "⏳ Mark Reviewed" : decision === "Reviewed" ? "✅ Reviewed" : "🚨 Escalated"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default Investigation;
