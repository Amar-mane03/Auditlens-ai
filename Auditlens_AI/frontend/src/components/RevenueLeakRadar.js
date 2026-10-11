import React, { useState, useEffect } from "react";
import axios from "axios";

function RevenueLeakRadar() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");
  const [summary, setSummary] = useState(null);
  const [findings, setFindings] = useState([]);
  const [rules, setRules] = useState([]);
  const [filterRisk, setFilterRisk] = useState("ALL");
  const [filterStatus, setFilterStatus] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedFinding, setSelectedFinding] = useState(null);
  const [reviewerName, setReviewerName] = useState("auditor@company.com");
  const [actionComments, setActionComments] = useState("");
  const [actionType, setActionType] = useState("review"); // "review" or "resolve"

  useEffect(() => {
    fetchRules();
    fetchFindings();
    fetchSummary();
  }, []);

  const fetchRules = async () => {
    try {
      const res = await axios.get("/api/revenue-leak-radar/rules");
      setRules(res.data.rules || []);
    } catch (err) {
      console.warn("Could not load rules:", err.message);
    }
  };

  const fetchSummary = async () => {
    try {
      const res = await axios.get("/api/revenue-leak-radar/summary");
      if (res.data && res.data.total_eligible_revenue !== undefined) {
        setSummary(res.data);
      }
    } catch (err) {
      // Summary might be empty before first run
    }
  };

  const fetchFindings = async () => {
    try {
      const res = await axios.get("/api/revenue-leak-radar/findings?limit=200");
      setFindings(res.data.items || []);
    } catch (err) {
      console.warn("Could not load findings:", err.message);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleUploadAndAnalyze = async () => {
    if (!file) {
      alert("Please select a revenue ledger file (.csv, .xlsx).");
      return;
    }

    setLoading(true);
    setStatusMessage("Uploading revenue ledger...");

    try {
      const formData = new FormData();
      formData.append("file", file);

      const upRes = await axios.post("/api/revenue-leak-radar/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      const jobId = upRes.data.job_id;
      setStatusMessage("Running deterministic & statistical detection rules on ledger...");

      const analyzeRes = await axios.post("/api/revenue-leak-radar/analyze", {
        job_id: jobId,
        analysis_name: file.name,
      });

      setSummary(analyzeRes.data.summary);
      setStatusMessage("Revenue leakage analysis complete!");
      await fetchFindings();
    } catch (err) {
      const msg = err.response?.data?.detail || err.response?.data?.error || err.message;
      alert("Analysis failed: " + msg);
      setStatusMessage("Analysis failed: " + msg);
    } finally {
      setLoading(false);
    }
  };

  const handleDemoAnalyze = async () => {
    setLoading(true);
    setStatusMessage("Running analysis on pre-built synthetic revenue ledger...");

    try {
      const res = await axios.get("/api/revenue-leak-radar/demo-analyze");
      setSummary(res.data.summary);
      setStatusMessage("Demo ledger analyzed successfully!");
      await fetchFindings();
    } catch (err) {
      const msg = err.response?.data?.detail || err.message;
      alert("Demo analysis failed: " + msg);
      setStatusMessage("Demo analysis failed: " + msg);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenAction = (finding, type) => {
    setSelectedFinding(finding);
    setActionType(type);
    setActionComments("");
  };

  const handleSubmitAction = async () => {
    if (!selectedFinding) return;

    try {
      if (actionType === "review") {
        await axios.patch(`/api/revenue-leak-radar/findings/${selectedFinding.finding_id}/review`, {
          status: "UNDER_REVIEW",
          reviewer: reviewerName,
          comments: actionComments || "Marked under review by auditor.",
        });
      } else {
        await axios.post(`/api/revenue-leak-radar/findings/${selectedFinding.finding_id}/resolve`, {
          status: "RESOLVED",
          reviewer: reviewerName,
          resolution_notes: actionComments || "Finding accepted and resolved.",
        });
      }

      setSelectedFinding(null);
      await fetchFindings();
      await fetchSummary();
    } catch (err) {
      const msg = err.response?.data?.detail || err.message;
      alert("Action failed: " + msg);
    }
  };

  const filteredFindings = findings.filter((f) => {
    if (filterRisk !== "ALL" && f.risk_level !== filterRisk) return false;
    if (filterStatus !== "ALL" && f.status !== filterStatus) return false;
    if (searchQuery.trim() !== "") {
      const q = searchQuery.toLowerCase();
      const idMatch = String(f.finding_id || "").toLowerCase().includes(q);
      const custMatch = String(f.customer_id || "").toLowerCase().includes(q);
      const invMatch = String(f.invoice_number || "").toLowerCase().includes(q);
      const ruleMatch = String(f.rule_name || "").toLowerCase().includes(q);
      return idMatch || custMatch || invMatch || ruleMatch;
    }
    return true;
  });

  return (
    <div className="radar-container">
      <div className="section-header">
        <div>
          <h2>🎯 Revenue Leak Radar</h2>
          <p className="subtitle">
            Autonomous detection of revenue underbilling, cutoff risks, unauthorized credit notes, duplicate billings, and statistical pricing anomalies.
          </p>
        </div>
        <div className="export-actions">
          <a href="/api/revenue-leak-radar/export/csv" download className="btn btn-secondary">
            📥 CSV Export
          </a>
          <a href="/api/revenue-leak-radar/export/excel" download className="btn btn-secondary">
            📥 Excel Export
          </a>
          <a href="/api/revenue-leak-radar/export/pdf" download className="btn btn-download">
            📥 PDF Report
          </a>
        </div>
      </div>

      <div className="upload-container" style={{ marginBottom: "20px" }}>
        <div className="upload-controls">
          <label className="file-input-wrapper">
            <input type="file" accept=".csv,.xlsx" onChange={handleFileChange} disabled={loading} />
            <span className="file-input-btn">📁 Choose Revenue Ledger</span>
            <span className="selected-files-text">{file ? file.name : "Select ledger (.csv, .xlsx)"}</span>
          </label>

          <button onClick={handleUploadAndAnalyze} disabled={loading || !file} className="btn btn-primary">
            {loading ? "Analyzing..." : "🚀 Analyze Revenue Leakage"}
          </button>

          <button onClick={handleDemoAnalyze} disabled={loading} className="btn btn-secondary" title="Analyze demo revenue ledger">
            ✨ Load Demo Revenue Ledger
          </button>
        </div>

        {statusMessage && (
          <div className={`status-pill ${statusMessage.includes("failed") ? "status-error" : "status-info"}`}>
            {statusMessage}
          </div>
        )}
      </div>

      {summary && (
        <div className="dashboard-container" style={{ marginBottom: "20px" }}>
          <h3>Executive Leakage Metrics</h3>
          <div className="metrics-grid">
            <div className="metric-card">
              <div className="metric-title">Eligible Revenue Analyzed</div>
              <div className="metric-value">₹{Number(summary.total_eligible_revenue || 0).toLocaleString()}</div>
              <div className="metric-sub">{summary.transactions_analyzed || 0} transactions</div>
            </div>

            <div className="metric-card alert-card">
              <div className="metric-title">Potential Shortfall / Leakage</div>
              <div className="metric-value highlight-red">₹{Number(summary.potential_shortfall || 0).toLocaleString()}</div>
              <div className="metric-sub">Underbilled benchmark gap</div>
            </div>

            <div className="metric-card warning-card">
              <div className="metric-title">Flagged Transactions</div>
              <div className="metric-value highlight-orange">{summary.flagged_transactions || 0}</div>
              <div className="metric-sub">{summary.unique_affected_invoices || 0} affected invoices</div>
            </div>

            <div className="metric-card alert-card">
              <div className="metric-title">High & Critical Risks</div>
              <div className="metric-value highlight-red">{summary.high_and_critical_risk_count || 0}</div>
              <div className="metric-sub">Requires urgent auditor intervention</div>
            </div>
          </div>
        </div>
      )}

      <div className="audit-table-container">
        <div className="table-header-controls">
          <h3>Leakage Findings Registry ({filteredFindings.length} of {findings.length})</h3>
          <div className="filters">
            <input
              type="text"
              placeholder="Search findings, customer, invoice..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="search-input"
            />
            <select value={filterRisk} onChange={(e) => setFilterRisk(e.target.value)} className="filter-select">
              <option value="ALL">All Risk Levels</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>
            <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} className="filter-select">
              <option value="ALL">All Statuses</option>
              <option value="NEW">New</option>
              <option value="UNDER_REVIEW">Under Review</option>
              <option value="RESOLVED">Resolved</option>
            </select>
          </div>
        </div>

        {filteredFindings.length === 0 ? (
          <p style={{ color: "#64748b", padding: "16px 0" }}>
            No revenue leak findings matching the selected filters. Upload a ledger or click "Load Demo Revenue Ledger" above.
          </p>
        ) : (
          <div className="table-responsive">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>Finding ID</th>
                  <th>Rule</th>
                  <th>Risk</th>
                  <th>Score</th>
                  <th>Gross Amount</th>
                  <th>Potential Shortfall</th>
                  <th>Customer / Invoice</th>
                  <th>Status</th>
                  <th>Auditor Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredFindings.map((f) => {
                  const riskClass = `badge badge-${(f.risk_level || "low").toLowerCase()}`;
                  return (
                    <tr key={f.finding_id}>
                      <td className="font-mono">{f.finding_id}</td>
                      <td>
                        <strong>{f.rule_name || f.rule_id}</strong>
                        <div style={{ fontSize: "11px", color: "#64748b" }}>{f.description}</div>
                      </td>
                      <td>
                        <span className={riskClass}>{f.risk_level}</span>
                      </td>
                      <td>
                        <span className="score-pill">{f.risk_score}</span>
                      </td>
                      <td>₹{Number(f.gross_amount || 0).toLocaleString()}</td>
                      <td style={{ color: f.potential_shortfall > 0 ? "#dc2626" : "inherit", fontWeight: 600 }}>
                        {f.potential_shortfall > 0 ? `₹${Number(f.potential_shortfall).toLocaleString()}` : "-"}
                      </td>
                      <td>
                        {f.customer_id || "N/A"} / {f.invoice_number || "N/A"}
                      </td>
                      <td>
                        <span className={`badge badge-${f.status === "RESOLVED" ? "low" : f.status === "UNDER_REVIEW" ? "medium" : "high"}`}>
                          {f.status}
                        </span>
                      </td>
                      <td>
                        <div style={{ display: "flex", gap: "6px" }}>
                          <button onClick={() => handleOpenAction(f, "review")} className="btn btn-secondary" style={{ padding: "4px 8px", fontSize: "11px" }}>
                            Review
                          </button>
                          <button onClick={() => handleOpenAction(f, "resolve")} className="btn btn-primary" style={{ padding: "4px 8px", fontSize: "11px" }}>
                            Resolve
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selectedFinding && (
        <div style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: "rgba(0,0,0,0.5)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 1000,
        }}>
          <div style={{
            background: "#ffffff",
            padding: "24px",
            borderRadius: "8px",
            maxWidth: "480px",
            width: "90%",
            boxShadow: "0 10px 25px rgba(0,0,0,0.2)",
          }}>
            <h3>{actionType === "review" ? "Put Finding Under Review" : "Resolve Finding"}</h3>
            <p style={{ fontSize: "13px", color: "#64748b", margin: "8px 0 16px" }}>
              Finding: <strong>{selectedFinding.finding_id}</strong> ({selectedFinding.rule_name})
            </p>

            <div style={{ marginBottom: "12px" }}>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "4px" }}>
                Auditor Identity:
              </label>
              <input
                type="text"
                value={reviewerName}
                onChange={(e) => setReviewerName(e.target.value)}
                style={{ width: "100%", padding: "8px", border: "1px solid #cbd5e1", borderRadius: "6px" }}
              />
            </div>

            <div style={{ marginBottom: "16px" }}>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "4px" }}>
                Resolution / Review Notes:
              </label>
              <textarea
                rows={3}
                value={actionComments}
                onChange={(e) => setActionComments(e.target.value)}
                placeholder="Enter audit investigation comments..."
                style={{ width: "100%", padding: "8px", border: "1px solid #cbd5e1", borderRadius: "6px" }}
              />
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px" }}>
              <button onClick={() => setSelectedFinding(null)} className="btn btn-secondary">
                Cancel
              </button>
              <button onClick={handleSubmitAction} className="btn btn-primary">
                {actionType === "review" ? "Confirm Under Review" : "Confirm Resolve"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default RevenueLeakRadar;

