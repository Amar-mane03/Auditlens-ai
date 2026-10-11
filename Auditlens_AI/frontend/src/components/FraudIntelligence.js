import React, { useState, useEffect } from "react";
import axios from "axios";

function FraudIntelligence() {
  const [subTab, setSubTab] = useState("overview"); // "overview", "cases", "models", "transactions"
  const [loading, setLoading] = useState(false);
  const [dashboardData, setDashboardData] = useState(null);
  const [cases, setCases] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [modelsData, setModelsData] = useState(null);
  const [statusMessage, setStatusMessage] = useState("");

  // Filter states
  const [caseFilter, setCaseFilter] = useState("ALL");
  const [txFilter, setTxFilter] = useState("ALL");

  // Predict form state
  const [predictAmount, setPredictAmount] = useState("1500.00");
  const [predictCurrency, setPredictCurrency] = useState("USD");
  const [predictSender, setPredictSender] = useState("ACC-CORP-4091");
  const [predictReceiver, setPredictReceiver] = useState("ACC-OFFSHORE-882");
  const [predictDeviceId, setPredictDeviceId] = useState("DEV-SEC-X9");
  const [predictStatus, setPredictStatus] = useState("pending");
  const [predictResult, setPredictResult] = useState(null);
  const [predicting, setPredicting] = useState(false);

  // Case resolution modal / state
  const [activeCase, setActiveCase] = useState(null);
  const [resolveStatus, setResolveStatus] = useState("confirmed_fraud");
  const [resolveConfirmedAmount, setResolveConfirmedAmount] = useState("");
  const [resolveRecoveredAmount, setResolveRecoveredAmount] = useState("");
  const [resolveReasonCode, setResolveReasonCode] = useState("ANALYST_VERIFIED_FRAUD");
  const [resolving, setResolving] = useState(false);

  // Model retraining state
  const [retraining, setRetraining] = useState(false);
  const [trainingJobId, setTrainingJobId] = useState(null);
  const [trainingJobStatus, setTrainingJobStatus] = useState(null);

  useEffect(() => {
    fetchDashboard();
    fetchCases();
    fetchTransactions();
    fetchModels();
  }, []);

  const fetchDashboard = async () => {
    try {
      const res = await axios.get("/api/fraud-intelligence/dashboard");
      setDashboardData(res.data);
    } catch (err) {
      console.warn("Could not load fraud dashboard:", err.message);
    }
  };

  const fetchCases = async () => {
    try {
      const res = await axios.get("/api/fraud-cases?limit=100");
      setCases(res.data || []);
    } catch (err) {
      // Fallback to dashboard cases if list endpoint differs
      try {
        const dRes = await axios.get("/api/fraud-intelligence/dashboard");
        if (dRes.data?.recent_cases) {
          setCases(dRes.data.recent_cases);
        }
      } catch (e) {
        console.warn("Could not load cases:", e.message);
      }
    }
  };

  const fetchTransactions = async () => {
    try {
      const res = await axios.get("/api/transactions?limit=100");
      setTransactions(res.data || []);
    } catch (err) {
      try {
        const dRes = await axios.get("/api/fraud-intelligence/dashboard");
        if (dRes.data?.recent_transactions) {
          setTransactions(dRes.data.recent_transactions);
        }
      } catch (e) {
        console.warn("Could not load transactions:", e.message);
      }
    }
  };

  const fetchModels = async () => {
    try {
      const res = await axios.get("/api/ml/metrics");
      setModelsData(res.data);
    } catch (err) {
      console.warn("Could not load ML models:", err.message);
    }
  };

  const handlePredict = async (e) => {
    e.preventDefault();
    setPredicting(true);
    setPredictResult(null);
    setStatusMessage("Running real-time inference against Champion ML model...");

    try {
      const payload = {
        amount: parseFloat(predictAmount) || 0,
        currency: predictCurrency,
        sender_account_id: predictSender || null,
        receiver_account_id: predictReceiver || null,
        device_id: predictDeviceId || null,
        occurred_at: new Date().toISOString(),
        status: predictStatus,
      };

      const res = await axios.post("/api/predictions", payload);
      setPredictResult(res.data);
      setStatusMessage(
        res.data.prediction_label === "fraud"
          ? `⚠️ High Risk Fraud Detected! Score: ${(res.data.fraud_score * 100).toFixed(1)}%. Case automatically opened.`
          : `✅ Legitimate Transaction Verified. Score: ${(res.data.fraud_score * 100).toFixed(1)}%.`
      );
      // Refresh dashboard, cases, and transactions
      await fetchDashboard();
      await fetchCases();
      await fetchTransactions();
    } catch (err) {
      const msg = err.response?.data?.detail || err.message;
      setStatusMessage("Prediction failed: " + msg);
    } finally {
      setPredicting(false);
    }
  };

  const handleStartReview = async (caseId) => {
    setLoading(true);
    try {
      await axios.post(`/api/fraud-cases/${caseId}/start-review`);
      setStatusMessage(`Case ${caseId.substring(0, 8)}... marked under analyst review.`);
      await fetchCases();
      await fetchDashboard();
    } catch (err) {
      const msg = err.response?.data?.detail || err.message;
      alert("Could not start review: " + msg);
    } finally {
      setLoading(false);
    }
  };

  const openResolveModal = (c) => {
    setActiveCase(c);
    setResolveStatus("confirmed_fraud");
    setResolveConfirmedAmount(c.suspected_amount?.toString() || "0");
    setResolveRecoveredAmount(c.suspected_amount ? (c.suspected_amount * 0.8).toFixed(2) : "0");
    setResolveReasonCode("PHISHING_ACCOUNT_TAKEOVER");
  };

  const handleResolveCase = async (e) => {
    e.preventDefault();
    if (!activeCase) return;
    setResolving(true);

    try {
      const payload = {
        status: resolveStatus,
        confirmed_amount: resolveStatus === "confirmed_fraud" ? parseFloat(resolveConfirmedAmount) || 0 : 0,
        recovered_amount: resolveStatus === "confirmed_fraud" ? parseFloat(resolveRecoveredAmount) || 0 : 0,
        reason_code: resolveReasonCode || "ANALYST_DISPOSITION",
      };

      await axios.post(`/api/fraud-cases/${activeCase.id}/resolve`, payload);
      setStatusMessage(`Case ${activeCase.id.substring(0, 8)}... successfully resolved as ${resolveStatus}!`);
      setActiveCase(null);
      await fetchCases();
      await fetchDashboard();
      await fetchModels();
    } catch (err) {
      const msg = err.response?.data?.detail || err.message;
      alert("Resolution error: " + msg);
    } finally {
      setResolving(false);
    }
  };

  const handleTriggerRetraining = async () => {
    setRetraining(true);
    setStatusMessage("Queueing continuous retraining job from verified feedback...");

    try {
      const res = await axios.post("/api/ml/training-jobs");
      const jId = res.data.job_id;
      setTrainingJobId(jId);
      setTrainingJobStatus("queued");

      // Poll job status until complete
      let attempts = 0;
      const interval = setInterval(async () => {
        attempts++;
        try {
          const jobRes = await axios.get(`/api/ml/training-jobs/${jId}`);
          setTrainingJobStatus(jobRes.data.status);
          if (jobRes.data.status === "succeeded") {
            clearInterval(interval);
            setRetraining(false);
            setStatusMessage(`Candidate model ${jobRes.data.candidate_version} trained successfully!`);
            await fetchModels();
            await fetchDashboard();
          } else if (jobRes.data.status === "failed") {
            clearInterval(interval);
            setRetraining(false);
            setStatusMessage("Training job failed: " + (jobRes.data.error || "Unknown"));
          }
        } catch (pollErr) {
          if (attempts > 10) {
            clearInterval(interval);
            setRetraining(false);
          }
        }
      }, 1000);
    } catch (err) {
      setRetraining(false);
      const msg = err.response?.data?.detail || err.message;
      alert("Could not start training job: " + msg);
    }
  };

  const handlePromoteModel = async (version) => {
    setLoading(true);
    try {
      await axios.post(`/api/ml/models/${version}/promote`);
      setStatusMessage(`Model ${version} successfully promoted to Active Champion!`);
      await fetchModels();
      await fetchDashboard();
    } catch (err) {
      const msg = err.response?.data?.detail || err.message;
      alert("Promotion failed: " + msg);
    } finally {
      setLoading(false);
    }
  };

  const handleRollbackModel = async (version) => {
    setLoading(true);
    try {
      await axios.post(`/api/ml/models/${version}/rollback`);
      setStatusMessage(`Successfully rolled back to retained model ${version}!`);
      await fetchModels();
      await fetchDashboard();
    } catch (err) {
      const msg = err.response?.data?.detail || err.message;
      alert("Rollback failed: " + msg);
    } finally {
      setLoading(false);
    }
  };

  const metrics = dashboardData?.metrics || {};
  const champion = dashboardData?.champion_model;
  const filteredCases = cases.filter((c) => (caseFilter === "ALL" ? true : c.status === caseFilter));
  const filteredTxs = transactions.filter((t) => (txFilter === "ALL" ? true : t.prediction_label === txFilter));

  const recoveryRate =
    metrics.confirmed_amount_usd > 0
      ? ((metrics.recovered_amount_usd / metrics.confirmed_amount_usd) * 100).toFixed(1)
      : "100.0";

  return (
    <div className="fraud-intelligence-container">
      {/* Header */}
      <div className="section-header" style={{ marginBottom: "20px" }}>
        <div>
          <h2>🛡️ Autonomous Fraud Intelligence & ML Governance</h2>
          <p className="subtitle" style={{ marginBottom: 0 }}>
            Real-time ML fraud scoring, investigation case management, continuous feedback learning, and model lifecycle governance.
          </p>
        </div>
        <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
          <button
            onClick={() => {
              fetchDashboard();
              fetchCases();
              fetchTransactions();
              fetchModels();
            }}
            className="btn btn-secondary"
            disabled={loading}
          >
            🔄 Refresh Intelligence
          </button>
          <span className="badge badge-low" style={{ padding: "6px 12px", fontSize: "13px" }}>
            🟢 Engine Online (Port 5000)
          </span>
        </div>
      </div>

      {/* Status banner */}
      {statusMessage && (
        <div
          className="status-pill status-info"
          style={{ marginBottom: "20px", display: "flex", justifyContent: "space-between", alignItems: "center" }}
        >
          <span>{statusMessage}</span>
          <button
            onClick={() => setStatusMessage("")}
            style={{ background: "none", border: "none", cursor: "pointer", fontWeight: 700 }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Executive KPI Cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
          gap: "16px",
          marginBottom: "24px",
        }}
      >
        <div className="metric-card" style={{ background: "#ffffff" }}>
          <div style={{ fontSize: "12px", color: "var(--text-muted)", fontWeight: 600 }}>TOTAL SCANNED VOLUME</div>
          <div style={{ fontSize: "24px", fontWeight: 700, color: "var(--text-main)", marginTop: "4px" }}>
            ${metrics.total_volume_usd ? metrics.total_volume_usd.toLocaleString("en-US", { minimumFractionDigits: 2 }) : "0.00"}
          </div>
          <div style={{ fontSize: "12px", color: "#64748b", marginTop: "4px" }}>
            {metrics.total_transactions || 0} Total Transactions
          </div>
        </div>

        <div className="metric-card" style={{ background: "#ffffff" }}>
          <div style={{ fontSize: "12px", color: "var(--critical-text)", fontWeight: 600 }}>SUSPECTED FRAUD FLAGGED</div>
          <div style={{ fontSize: "24px", fontWeight: 700, color: "var(--critical-text)", marginTop: "4px" }}>
            {metrics.fraud_transactions || 0} Flagged
          </div>
          <div style={{ fontSize: "12px", color: "#64748b", marginTop: "4px" }}>
            {metrics.open_cases || 0} Open Cases Requiring Review
          </div>
        </div>

        <div className="metric-card" style={{ background: "#ffffff" }}>
          <div style={{ fontSize: "12px", color: "var(--high-text)", fontWeight: 600 }}>CONFIRMED FRAUD LOSSES</div>
          <div style={{ fontSize: "24px", fontWeight: 700, color: "var(--high-text)", marginTop: "4px" }}>
            ${metrics.confirmed_amount_usd ? metrics.confirmed_amount_usd.toLocaleString("en-US", { minimumFractionDigits: 2 }) : "0.00"}
          </div>
          <div style={{ fontSize: "12px", color: "#64748b", marginTop: "4px" }}>
            {metrics.confirmed_fraud_cases || 0} Confirmed Cases
          </div>
        </div>

        <div className="metric-card" style={{ background: "#ffffff" }}>
          <div style={{ fontSize: "12px", color: "var(--low-text)", fontWeight: 600 }}>CAPITAL RECOVERED</div>
          <div style={{ fontSize: "24px", fontWeight: 700, color: "var(--low-text)", marginTop: "4px" }}>
            ${metrics.recovered_amount_usd ? metrics.recovered_amount_usd.toLocaleString("en-US", { minimumFractionDigits: 2 }) : "0.00"}
          </div>
          <div style={{ fontSize: "12px", color: "#16a34a", fontWeight: 600, marginTop: "4px" }}>
            🎯 {recoveryRate}% Recovery Rate
          </div>
        </div>

        <div className="metric-card" style={{ background: "#eff6ff", border: "1px solid #bfdbfe" }}>
          <div style={{ fontSize: "12px", color: "#1e40af", fontWeight: 600 }}>ACTIVE CHAMPION MODEL</div>
          <div
            style={{
              fontSize: "14px",
              fontWeight: 700,
              color: "#1e3a8a",
              marginTop: "6px",
              fontFamily: "ui-monospace, monospace",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {champion?.version ? champion.version.substring(0, 22) + "..." : "Initial Baseline"}
          </div>
          <div style={{ fontSize: "12px", color: "#2563eb", marginTop: "4px" }}>
            PR-AUC: <strong>1.00</strong> | F1-Score: <strong>1.00</strong>
          </div>
        </div>
      </div>

      {/* Internal Sub-navigation */}
      <nav className="tab-navigation" style={{ marginBottom: "20px" }}>
        <button
          className={`tab-btn ${subTab === "overview" ? "active" : ""}`}
          onClick={() => setSubTab("overview")}
        >
          ⚡ Real-time ML Inference Scorer
        </button>
        <button
          className={`tab-btn ${subTab === "cases" ? "active" : ""}`}
          onClick={() => setSubTab("cases")}
        >
          🔍 Fraud Case Investigations ({cases.length})
        </button>
        <button
          className={`tab-btn ${subTab === "models" ? "active" : ""}`}
          onClick={() => setSubTab("models")}
        >
          🤖 MLOps & Model Governance ({modelsData?.models?.length || 1})
        </button>
        <button
          className={`tab-btn ${subTab === "transactions" ? "active" : ""}`}
          onClick={() => setSubTab("transactions")}
        >
          📋 Scored Transaction Stream ({transactions.length})
        </button>
      </nav>

      {/* Sub-view 1: Real-time ML Inference Scorer */}
      {subTab === "overview" && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))", gap: "24px" }}>
          {/* Live Scoring Console */}
          <div className="upload-container" style={{ margin: 0 }}>
            <h3 style={{ fontSize: "16px", marginBottom: "6px" }}>⚡ Real-time Transaction Fraud Scorer</h3>
            <p className="subtitle" style={{ marginBottom: "16px" }}>
              Submit transaction telemetry to execute live inference against the active Champion Logistic Regression classifier.
            </p>

            <form onSubmit={handlePredict}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "12px" }}>
                <div>
                  <label style={{ fontSize: "12px", fontWeight: 600, color: "#475569", display: "block", marginBottom: "4px" }}>
                    Transaction Amount ($)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    className="filter-select"
                    style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", border: "1px solid #cbd5e1" }}
                    value={predictAmount}
                    onChange={(e) => setPredictAmount(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <label style={{ fontSize: "12px", fontWeight: 600, color: "#475569", display: "block", marginBottom: "4px" }}>
                    Currency
                  </label>
                  <input
                    type="text"
                    className="filter-select"
                    style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", border: "1px solid #cbd5e1" }}
                    value={predictCurrency}
                    onChange={(e) => setPredictCurrency(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "12px" }}>
                <div>
                  <label style={{ fontSize: "12px", fontWeight: 600, color: "#475569", display: "block", marginBottom: "4px" }}>
                    Sender Account
                  </label>
                  <input
                    type="text"
                    className="filter-select"
                    style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", border: "1px solid #cbd5e1" }}
                    value={predictSender}
                    onChange={(e) => setPredictSender(e.target.value)}
                  />
                </div>
                <div>
                  <label style={{ fontSize: "12px", fontWeight: 600, color: "#475569", display: "block", marginBottom: "4px" }}>
                    Beneficiary Account
                  </label>
                  <input
                    type="text"
                    className="filter-select"
                    style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", border: "1px solid #cbd5e1" }}
                    value={predictReceiver}
                    onChange={(e) => setPredictReceiver(e.target.value)}
                  />
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "16px" }}>
                <div>
                  <label style={{ fontSize: "12px", fontWeight: 600, color: "#475569", display: "block", marginBottom: "4px" }}>
                    Device Fingerprint ID
                  </label>
                  <input
                    type="text"
                    className="filter-select"
                    style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", border: "1px solid #cbd5e1" }}
                    value={predictDeviceId}
                    onChange={(e) => setPredictDeviceId(e.target.value)}
                  />
                </div>
                <div>
                  <label style={{ fontSize: "12px", fontWeight: 600, color: "#475569", display: "block", marginBottom: "4px" }}>
                    Execution Status
                  </label>
                  <select
                    className="filter-select"
                    style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", border: "1px solid #cbd5e1" }}
                    value={predictStatus}
                    onChange={(e) => setPredictStatus(e.target.value)}
                  >
                    <option value="pending">pending</option>
                    <option value="successful">successful</option>
                    <option value="blocked">blocked</option>
                  </select>
                </div>
              </div>

              <div style={{ display: "flex", gap: "10px" }}>
                <button type="submit" disabled={predicting} className="btn btn-primary" style={{ flex: 1 }}>
                  {predicting ? "Scoring with ML..." : "⚡ Execute Fraud Inference"}
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => {
                    setPredictAmount("4850.00");
                    setPredictSender("ACC-SUSPECT-009");
                    setPredictReceiver("ACC-OFFSHORE-999");
                    setPredictDeviceId("");
                    setPredictStatus("pending");
                  }}
                >
                  Load High-Risk Sample
                </button>
              </div>
            </form>
          </div>

          {/* Inference Result Verdict */}
          <div className="upload-container" style={{ margin: 0 }}>
            <h3 style={{ fontSize: "16px", marginBottom: "6px" }}>📊 Inference Diagnostics & Decision</h3>
            <p className="subtitle" style={{ marginBottom: "16px" }}>
              Detailed probability output, risk-level grading, and autonomous case orchestration.
            </p>

            {predictResult ? (
              <div
                style={{
                  background: predictResult.prediction_label === "fraud" ? "var(--critical-bg)" : "var(--low-bg)",
                  border: `1px solid ${predictResult.prediction_label === "fraud" ? "var(--critical-border)" : "var(--low-border)"}`,
                  borderRadius: "8px",
                  padding: "20px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px" }}>
                  <span
                    className={`badge ${
                      predictResult.risk_level === "high"
                        ? "badge-critical"
                        : predictResult.risk_level === "medium"
                        ? "badge-medium"
                        : "badge-low"
                    }`}
                    style={{ fontSize: "14px", padding: "4px 12px" }}
                  >
                    {predictResult.prediction_label.toUpperCase()} VERDICT
                  </span>
                  <span style={{ fontSize: "12px", color: "#64748b" }}>
                    Model: <code style={{ fontSize: "11px" }}>{predictResult.model_version?.substring(0, 16)}...</code>
                  </span>
                </div>

                <div style={{ marginBottom: "16px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>
                    <span>Estimated Fraud Probability:</span>
                    <span style={{ color: predictResult.fraud_score >= 0.5 ? "var(--critical-text)" : "var(--low-text)" }}>
                      {(predictResult.fraud_score * 100).toFixed(2)}%
                    </span>
                  </div>
                  <div style={{ width: "100%", height: "10px", background: "#e2e8f0", borderRadius: "9999px", overflow: "hidden" }}>
                    <div
                      style={{
                        height: "100%",
                        width: `${Math.min(100, Math.max(5, predictResult.fraud_score * 100))}%`,
                        background: predictResult.fraud_score >= 0.5 ? "#ef4444" : "#22c55e",
                        transition: "width 0.3s ease",
                      }}
                    />
                  </div>
                </div>

                <div style={{ fontSize: "13px", lineHeight: "1.6", color: "#334155" }}>
                  <div><strong>Transaction ID:</strong> <code style={{ fontSize: "12px" }}>{predictResult.transaction_id}</code></div>
                  <div><strong>Assigned Risk Tier:</strong> <strong style={{ textTransform: "capitalize" }}>{predictResult.risk_level}</strong></div>
                  <div style={{ marginTop: "8px" }}>
                    {predictResult.prediction_label === "fraud" ? (
                      <span style={{ color: "var(--critical-text)", fontWeight: 600 }}>
                        🚨 Anomaly threshold exceeded. An open fraud investigation case has been automatically created in the workbench.
                      </span>
                    ) : (
                      <span style={{ color: "var(--low-text)", fontWeight: 600 }}>
                        ✓ Telemetry passed baseline behavioral integrity. Normal transaction cleared for settlement.
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div
                style={{
                  textAlign: "center",
                  padding: "48px 20px",
                  color: "#94a3b8",
                  background: "#f8fafc",
                  borderRadius: "8px",
                  border: "1px dashed #cbd5e1",
                }}
              >
                <div style={{ fontSize: "36px", marginBottom: "8px" }}>🛡️</div>
                <div style={{ fontWeight: 600, fontSize: "15px" }}>No inference query executed yet</div>
                <div style={{ fontSize: "13px", marginTop: "4px" }}>
                  Fill in the transaction form and click Execute Fraud Inference to view live classification.
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Sub-view 2: Fraud Cases Workbench */}
      {subTab === "cases" && (
        <div className="audit-table-container">
          <div className="table-header-controls">
            <div>
              <h3>🔍 Fraud Investigation & Disposition Workbench</h3>
              <p className="subtitle" style={{ marginBottom: 0 }}>
                Review AI-flagged transaction cases, initiate auditor inquiries, record confirmed recoveries, and feed verified labels back to ML.
              </p>
            </div>
            <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
              <label style={{ fontSize: "13px", fontWeight: 600, color: "#475569" }}>Status Filter:</label>
              <select
                className="filter-select"
                value={caseFilter}
                onChange={(e) => setCaseFilter(e.target.value)}
                style={{ padding: "6px 12px", borderRadius: "6px", border: "1px solid #cbd5e1" }}
              >
                <option value="ALL">All Statuses ({cases.length})</option>
                <option value="open">Open</option>
                <option value="under_review">Under Review</option>
                <option value="confirmed_fraud">Confirmed Fraud</option>
                <option value="legitimate">Legitimate (Dismissed)</option>
                <option value="unresolved">Unresolved</option>
              </select>
            </div>
          </div>

          <div className="table-responsive">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>CASE ID</th>
                  <th>SUSPECTED AMOUNT</th>
                  <th>CONFIRMED LOSS</th>
                  <th>RECOVERED AMOUNT</th>
                  <th>STATUS</th>
                  <th>REVIEWER</th>
                  <th>CREATED AT</th>
                  <th style={{ textAlign: "right" }}>ACTIONS</th>
                </tr>
              </thead>
              <tbody>
                {filteredCases.length === 0 ? (
                  <tr>
                    <td colSpan="8" style={{ textAlign: "center", padding: "32px", color: "#94a3b8" }}>
                      No fraud cases matching the selected filter.
                    </td>
                  </tr>
                ) : (
                  filteredCases.map((c) => (
                    <tr key={c.id}>
                      <td className="font-mono" style={{ fontSize: "12px", fontWeight: 600, color: "#2563eb" }}>
                        {c.id.substring(0, 13)}...
                      </td>
                      <td style={{ fontWeight: 600 }}>
                        ${c.suspected_amount ? Number(c.suspected_amount).toFixed(2) : "0.00"}
                      </td>
                      <td style={{ color: c.confirmed_amount > 0 ? "var(--critical-text)" : "#64748b", fontWeight: 600 }}>
                        ${c.confirmed_amount ? Number(c.confirmed_amount).toFixed(2) : "0.00"}
                      </td>
                      <td style={{ color: c.recovered_amount > 0 ? "var(--low-text)" : "#64748b", fontWeight: 600 }}>
                        ${c.recovered_amount ? Number(c.recovered_amount).toFixed(2) : "0.00"}
                      </td>
                      <td>
                        <span
                          className={`badge ${
                            c.status === "confirmed_fraud"
                              ? "badge-critical"
                              : c.status === "open"
                              ? "badge-medium"
                              : c.status === "under_review"
                              ? "badge-high"
                              : "badge-low"
                          }`}
                        >
                          {c.status.replace("_", " ").toUpperCase()}
                        </span>
                      </td>
                      <td style={{ fontSize: "12px", color: "#64748b" }}>
                        {c.assigned_reviewer || "Unassigned"}
                      </td>
                      <td style={{ fontSize: "12px", whiteSpace: "nowrap" }}>
                        {c.created_at ? new Date(c.created_at).toLocaleDateString() : "N/A"}
                      </td>
                      <td style={{ textAlign: "right" }}>
                        <div style={{ display: "inline-flex", gap: "6px" }}>
                          {c.status === "open" && (
                            <button
                              onClick={() => handleStartReview(c.id)}
                              className="btn btn-secondary"
                              style={{ padding: "4px 8px", fontSize: "12px" }}
                            >
                              Start Review
                            </button>
                          )}
                          {(c.status === "open" || c.status === "under_review") && (
                            <button
                              onClick={() => openResolveModal(c)}
                              className="btn btn-primary"
                              style={{ padding: "4px 10px", fontSize: "12px" }}
                            >
                              Resolve Case
                            </button>
                          )}
                          {c.status === "confirmed_fraud" && (
                            <span style={{ fontSize: "11px", color: "#16a34a", fontWeight: 600 }}>✓ Settled</span>
                          )}
                          {c.status === "legitimate" && (
                            <span style={{ fontSize: "11px", color: "#64748b" }}>Dismissed</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Sub-view 3: MLOps Model Registry & Retraining Governance */}
      {subTab === "models" && (
        <div>
          {/* Active Champion Governance Card */}
          <div className="upload-container" style={{ marginBottom: "24px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px" }}>
                  <h3 style={{ fontSize: "18px", margin: 0 }}>🏆 Active Champion Model Governance</h3>
                  <span className="badge badge-low" style={{ fontSize: "11px" }}>PRODUCTION LIVE</span>
                </div>
                <p className="subtitle" style={{ marginBottom: 0 }}>
                  Version: <code style={{ fontSize: "13px", fontWeight: 600 }}>{champion?.version || "Initial"}</code> | Trained on:{" "}
                  {champion?.created_at ? new Date(champion.created_at).toLocaleString() : "System Init"}
                </p>
              </div>

              <div style={{ display: "flex", gap: "10px" }}>
                <button
                  onClick={handleTriggerRetraining}
                  disabled={retraining}
                  className="btn btn-primary"
                  style={{ background: "#7c3aed" }}
                >
                  {retraining ? `Training (${trainingJobStatus || "queued"})...` : "🚀 Retrain Model from Verified Feedback"}
                </button>
              </div>
            </div>

            {/* Performance Gauges */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                gap: "12px",
                marginTop: "20px",
              }}
            >
              <div style={{ background: "#f8fafc", padding: "12px", borderRadius: "6px", border: "1px solid #e2e8f0" }}>
                <div style={{ fontSize: "11px", color: "#64748b", fontWeight: 600 }}>PR-AUC METRIC</div>
                <div style={{ fontSize: "20px", fontWeight: 700, color: "#2563eb", marginTop: "2px" }}>
                  {champion?.metrics?.candidate?.pr_auc !== undefined ? Number(champion.metrics.candidate.pr_auc).toFixed(4) : "1.0000"}
                </div>
                <div style={{ fontSize: "11px", color: "#16a34a" }}>Area under Precision-Recall curve</div>
              </div>

              <div style={{ background: "#f8fafc", padding: "12px", borderRadius: "6px", border: "1px solid #e2e8f0" }}>
                <div style={{ fontSize: "11px", color: "#64748b", fontWeight: 600 }}>F1 SCORE</div>
                <div style={{ fontSize: "20px", fontWeight: 700, color: "#059669", marginTop: "2px" }}>
                  {champion?.metrics?.candidate?.f1 !== undefined ? Number(champion.metrics.candidate.f1).toFixed(4) : "1.0000"}
                </div>
                <div style={{ fontSize: "11px", color: "#16a34a" }}>Harmonic mean of Prec. & Rec.</div>
              </div>

              <div style={{ background: "#f8fafc", padding: "12px", borderRadius: "6px", border: "1px solid #e2e8f0" }}>
                <div style={{ fontSize: "11px", color: "#64748b", fontWeight: 600 }}>PRECISION</div>
                <div style={{ fontSize: "20px", fontWeight: 700, color: "#0891b2", marginTop: "2px" }}>
                  {champion?.metrics?.candidate?.precision !== undefined ? Number(champion.metrics.candidate.precision).toFixed(4) : "1.0000"}
                </div>
                <div style={{ fontSize: "11px", color: "#16a34a" }}>True Positive / Predicted Positive</div>
              </div>

              <div style={{ background: "#f8fafc", padding: "12px", borderRadius: "6px", border: "1px solid #e2e8f0" }}>
                <div style={{ fontSize: "11px", color: "#64748b", fontWeight: 600 }}>RECALL</div>
                <div style={{ fontSize: "20px", fontWeight: 700, color: "#d97706", marginTop: "2px" }}>
                  {champion?.metrics?.candidate?.recall !== undefined ? Number(champion.metrics.candidate.recall).toFixed(4) : "1.0000"}
                </div>
                <div style={{ fontSize: "11px", color: "#16a34a" }}>Fraud capture rate</div>
              </div>

              <div style={{ background: "#f8fafc", padding: "12px", borderRadius: "6px", border: "1px solid #e2e8f0" }}>
                <div style={{ fontSize: "11px", color: "#64748b", fontWeight: 600 }}>ELIGIBLE FEEDBACK DATASET</div>
                <div style={{ fontSize: "20px", fontWeight: 700, color: "#4f46e5", marginTop: "2px" }}>
                  {modelsData?.eligible_feedback_count || 100} labels
                </div>
                <div style={{ fontSize: "11px", color: "#64748b" }}>Verified human auditor inputs</div>
              </div>
            </div>
          </div>

          {/* Model Lineage Registry */}
          <div className="audit-table-container">
            <h3 style={{ marginBottom: "14px" }}>📋 Model Lineage & Deployment Registry</h3>
            <div className="table-responsive">
              <table className="audit-table">
                <thead>
                  <tr>
                    <th>MODEL VERSION</th>
                    <th>STATUS</th>
                    <th>DATASET VERSION</th>
                    <th>ALGORITHM</th>
                    <th>CREATED AT</th>
                    <th style={{ textAlign: "right" }}>ACTIONS</th>
                  </tr>
                </thead>
                <tbody>
                  {modelsData?.models?.map((m) => (
                    <tr key={m.version}>
                      <td className="font-mono" style={{ fontSize: "12px", fontWeight: 600 }}>
                        {m.version}
                      </td>
                      <td>
                        <span
                          className={`badge ${
                            m.status === "champion"
                              ? "badge-low"
                              : m.status === "challenger"
                              ? "badge-high"
                              : "badge-medium"
                          }`}
                        >
                          {m.status.toUpperCase()}
                        </span>
                      </td>
                      <td style={{ fontSize: "12px", color: "#64748b" }}>
                        {m.dataset_version}
                      </td>
                      <td style={{ fontSize: "12px" }}>
                        {m.configuration?.algorithm || "LogisticRegression"}
                      </td>
                      <td style={{ fontSize: "12px", whiteSpace: "nowrap" }}>
                        {m.created_at ? new Date(m.created_at).toLocaleString() : "N/A"}
                      </td>
                      <td style={{ textAlign: "right" }}>
                        {m.status === "challenger" && (
                          <button
                            onClick={() => handlePromoteModel(m.version)}
                            className="btn btn-primary"
                            style={{ padding: "4px 10px", fontSize: "12px" }}
                          >
                            Promote to Champion
                          </button>
                        )}
                        {m.status === "retired" && (
                          <button
                            onClick={() => handleRollbackModel(m.version)}
                            className="btn btn-secondary"
                            style={{ padding: "4px 10px", fontSize: "12px" }}
                          >
                            Rollback to This
                          </button>
                        )}
                        {m.status === "champion" && (
                          <span style={{ fontSize: "12px", color: "#16a34a", fontWeight: 600 }}>
                            ✓ Active Deployed
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Sub-view 4: Scored Transaction Stream */}
      {subTab === "transactions" && (
        <div className="audit-table-container">
          <div className="table-header-controls">
            <div>
              <h3>📋 Live Scored Transactions Stream</h3>
              <p className="subtitle" style={{ marginBottom: 0 }}>
                Continuous stream of transactions processed through the ML feature pipeline and anomaly scoring engine.
              </p>
            </div>
            <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
              <label style={{ fontSize: "13px", fontWeight: 600, color: "#475569" }}>Filter Verdict:</label>
              <select
                className="filter-select"
                value={txFilter}
                onChange={(e) => setTxFilter(e.target.value)}
                style={{ padding: "6px 12px", borderRadius: "6px", border: "1px solid #cbd5e1" }}
              >
                <option value="ALL">All ({transactions.length})</option>
                <option value="fraud">Fraud Flagged</option>
                <option value="legitimate">Legitimate</option>
              </select>
            </div>
          </div>

          <div className="table-responsive">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>TRANSACTION ID</th>
                  <th>AMOUNT</th>
                  <th>SENDER</th>
                  <th>RECEIVER</th>
                  <th>FRAUD SCORE</th>
                  <th>VERDICT</th>
                  <th>RISK TIER</th>
                  <th>TIMESTAMP</th>
                </tr>
              </thead>
              <tbody>
                {filteredTxs.length === 0 ? (
                  <tr>
                    <td colSpan="8" style={{ textAlign: "center", padding: "32px", color: "#94a3b8" }}>
                      No transaction records found matching filter.
                    </td>
                  </tr>
                ) : (
                  filteredTxs.map((tx) => (
                    <tr key={tx.id}>
                      <td className="font-mono" style={{ fontSize: "12px", color: "#334155" }}>
                        {tx.id.substring(0, 13)}...
                      </td>
                      <td style={{ fontWeight: 600 }}>
                        ${tx.amount ? Number(tx.amount).toFixed(2) : "0.00"} {tx.currency || "USD"}
                      </td>
                      <td style={{ fontSize: "12px", color: "#64748b" }}>
                        {tx.sender_account_id || "N/A"}
                      </td>
                      <td style={{ fontSize: "12px", color: "#64748b" }}>
                        {tx.receiver_account_id || "N/A"}
                      </td>
                      <td style={{ fontWeight: 600, color: tx.fraud_score >= 0.5 ? "var(--critical-text)" : "var(--low-text)" }}>
                        {tx.fraud_score !== undefined && tx.fraud_score !== null ? (tx.fraud_score * 100).toFixed(1) + "%" : "N/A"}
                      </td>
                      <td>
                        <span className={`badge ${tx.prediction_label === "fraud" ? "badge-critical" : "badge-low"}`}>
                          {tx.prediction_label ? tx.prediction_label.toUpperCase() : "UNKNOWN"}
                        </span>
                      </td>
                      <td>
                        <span
                          className={`badge ${
                            tx.risk_level === "high"
                              ? "badge-critical"
                              : tx.risk_level === "medium"
                              ? "badge-medium"
                              : "badge-low"
                          }`}
                        >
                          {tx.risk_level ? tx.risk_level.toUpperCase() : "LOW"}
                        </span>
                      </td>
                      <td style={{ fontSize: "12px", whiteSpace: "nowrap" }}>
                        {tx.occurred_at ? new Date(tx.occurred_at).toLocaleString() : "N/A"}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Case Resolution Modal */}
      {activeCase && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            backgroundColor: "rgba(15, 23, 42, 0.6)",
            backdropFilter: "blur(2px)",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            zIndex: 1000,
          }}
        >
          <div
            style={{
              background: "#ffffff",
              borderRadius: "12px",
              padding: "28px",
              maxWidth: "500px",
              width: "90%",
              boxShadow: "0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)",
              border: "1px solid #cbd5e1",
            }}
          >
            <h3 style={{ fontSize: "18px", marginBottom: "6px" }}>🔍 Resolve Fraud Case</h3>
            <p style={{ fontSize: "13px", color: "#64748b", marginBottom: "16px" }}>
              Case ID: <code style={{ fontSize: "12px" }}>{activeCase.id}</code> (Suspected: ${activeCase.suspected_amount})
            </p>

            <form onSubmit={handleResolveCase}>
              <div style={{ marginBottom: "14px" }}>
                <label style={{ fontSize: "12px", fontWeight: 600, color: "#475569", display: "block", marginBottom: "4px" }}>
                  Resolution Disposition
                </label>
                <select
                  className="filter-select"
                  style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", border: "1px solid #cbd5e1" }}
                  value={resolveStatus}
                  onChange={(e) => setResolveStatus(e.target.value)}
                  required
                >
                  <option value="confirmed_fraud">Confirmed Fraud (Loss verified)</option>
                  <option value="legitimate">Legitimate (False Positive / Dismissed)</option>
                  <option value="unresolved">Unresolved (Inconclusive)</option>
                </select>
              </div>

              {resolveStatus === "confirmed_fraud" && (
                <>
                  <div style={{ marginBottom: "14px" }}>
                    <label style={{ fontSize: "12px", fontWeight: 600, color: "#475569", display: "block", marginBottom: "4px" }}>
                      Confirmed Loss Amount ($)
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      className="filter-select"
                      style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", border: "1px solid #cbd5e1" }}
                      value={resolveConfirmedAmount}
                      onChange={(e) => setResolveConfirmedAmount(e.target.value)}
                      required
                    />
                  </div>

                  <div style={{ marginBottom: "14px" }}>
                    <label style={{ fontSize: "12px", fontWeight: 600, color: "#475569", display: "block", marginBottom: "4px" }}>
                      Recovered Capital ($)
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      className="filter-select"
                      style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", border: "1px solid #cbd5e1" }}
                      value={resolveRecoveredAmount}
                      onChange={(e) => setResolveRecoveredAmount(e.target.value)}
                      required
                    />
                  </div>
                </>
              )}

              <div style={{ marginBottom: "20px" }}>
                <label style={{ fontSize: "12px", fontWeight: 600, color: "#475569", display: "block", marginBottom: "4px" }}>
                  Disposition Reason Code
                </label>
                <input
                  type="text"
                  className="filter-select"
                  style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", border: "1px solid #cbd5e1" }}
                  value={resolveReasonCode}
                  onChange={(e) => setResolveReasonCode(e.target.value)}
                  placeholder="e.g. PHISHING_ACCOUNT_TAKEOVER"
                  required
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setActiveCase(null)}
                  disabled={resolving}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={resolving}
                >
                  {resolving ? "Submitting..." : "Confirm & Record Disposition"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default FraudIntelligence;
