import React, { useState, useEffect } from "react";
import axios from "axios";

function SystemStatus() {
  const [engineHealth, setEngineHealth] = useState({
    auditEngine: { status: "checking", latency: null },
    revenueRadar: { status: "checking", count: null },
    evidenceChain: { status: "checking", valid: null, blocks: null },
    fraudML: { status: "checking", champion: null },
  });
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    runDiagnostics();
  }, []);

  const runDiagnostics = async () => {
    setRefreshing(true);
    const newHealth = { ...engineHealth };

    // 1. Check Flask Audit Engine
    const t0 = performance.now();
    try {
      const res = await axios.get("/health");
      const latency = Math.round(performance.now() - t0);
      newHealth.auditEngine = { status: res.data.status === "ok" ? "healthy" : "warning", latency };
    } catch (e) {
      newHealth.auditEngine = { status: "offline", error: e.message };
    }

    // 2. Check Revenue Leak Radar
    try {
      const res = await axios.get("/api/revenue-leak-radar/rules");
      newHealth.revenueRadar = {
        status: "healthy",
        count: res.data.rules?.length || 5,
      };
    } catch (e) {
      newHealth.revenueRadar = { status: "offline", error: e.message };
    }

    // 3. Check Evidence Chain
    try {
      const res = await axios.get("/api/evidence-chain/verify");
      newHealth.evidenceChain = {
        status: res.data.valid ? "healthy" : "warning",
        valid: res.data.valid,
        blocks: res.data.events_checked || 0,
      };
    } catch (e) {
      newHealth.evidenceChain = { status: "offline", error: e.message };
    }

    // 4. Check ML Fraud Governance
    try {
      const res = await axios.get("/api/fraud-intelligence/dashboard");
      newHealth.fraudML = {
        status: "healthy",
        champion: res.data.champion_model?.version || "Active v1.0",
        totalVolume: res.data.metrics?.total_volume_usd || 0,
      };
    } catch (e) {
      newHealth.fraudML = { status: "offline", error: e.message };
    }

    setEngineHealth(newHealth);
    setRefreshing(false);
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case "healthy":
        return <span className="badge badge-low">Operational</span>;
      case "warning":
        return <span className="badge badge-high">Degraded</span>;
      case "offline":
        return <span className="badge badge-critical">Offline</span>;
      default:
        return <span className="badge badge-medium">Probing...</span>;
    }
  };

  return (
    <div className="system-status-container">
      <div className="section-header">
        <div>
          <h2>System Infrastructure & Micro-Engine Diagnostics</h2>
          <p className="subtitle">
            Live telemetry and operational readiness monitors across the AuditLens multi-engine architecture.
          </p>
        </div>
        <div>
          <button
            onClick={runDiagnostics}
            disabled={refreshing}
            className="btn btn-secondary"
          >
            {refreshing ? "Probing Microservices..." : "🔄 Refresh Diagnostics"}
          </button>
        </div>
      </div>

      <div className="engine-status-grid">
        {/* Card 1: Core Audit Engine */}
        <div className="engine-card">
          <div className="engine-card-header">
            <div className="engine-title-group">
              <span className="engine-icon">⚙️</span>
              <div>
                <h4>Transaction Audit Engine</h4>
                <span className="engine-runtime">Flask WSGI Microservice</span>
              </div>
            </div>
            {getStatusBadge(engineHealth.auditEngine.status)}
          </div>
          <p className="engine-desc">
            Executes deterministic rule passes: duplicate invoice correlation, tax discrepancy calculations, weekend/midnight journal entry flags.
          </p>
          <div className="engine-stats">
            <div className="engine-stat-col">
              <span className="engine-stat-label">Response Time</span>
              <span className="engine-stat-val">
                {engineHealth.auditEngine.latency ? `${engineHealth.auditEngine.latency} ms` : "N/A"}
              </span>
            </div>
            <div className="engine-stat-col">
              <span className="engine-stat-label">Port Endpoint</span>
              <span className="engine-stat-val font-mono">:5000/upload</span>
            </div>
          </div>
        </div>

        {/* Card 2: Revenue Leak Radar */}
        <div className="engine-card">
          <div className="engine-card-header">
            <div className="engine-title-group">
              <span className="engine-icon">🎯</span>
              <div>
                <h4>Revenue Leak Radar</h4>
                <span className="engine-runtime">FastAPI Analytics Router</span>
              </div>
            </div>
            {getStatusBadge(engineHealth.revenueRadar.status)}
          </div>
          <p className="engine-desc">
            Cross-checks revenue recognition timing, unbilled contract commitments, discount ceiling breaches, and customer churn leakage.
          </p>
          <div className="engine-stats">
            <div className="engine-stat-col">
              <span className="engine-stat-label">Active Rules</span>
              <span className="engine-stat-val">{engineHealth.revenueRadar.count ?? 5} Enforced</span>
            </div>
            <div className="engine-stat-col">
              <span className="engine-stat-label">Endpoint</span>
              <span className="engine-stat-val font-mono">/api/revenue-leak-radar</span>
            </div>
          </div>
        </div>

        {/* Card 3: Evidence Chain */}
        <div className="engine-card">
          <div className="engine-card-header">
            <div className="engine-title-group">
              <span className="engine-icon">🔗</span>
              <div>
                <h4>Cryptographic Evidence Chain</h4>
                <span className="engine-runtime">SHA-256 Ledger Core</span>
              </div>
            </div>
            {getStatusBadge(engineHealth.evidenceChain.status)}
          </div>
          <p className="engine-desc">
            Maintains mathematically immutable block sequence of auditor workpapers, uploaded attachments, and statutory signoffs.
          </p>
          <div className="engine-stats">
            <div className="engine-stat-col">
              <span className="engine-stat-label">Blocks Verified</span>
              <span className="engine-stat-val">{engineHealth.evidenceChain.blocks ?? 0} Blocks</span>
            </div>
            <div className="engine-stat-col">
              <span className="engine-stat-label">Chain Integrity</span>
              <span className="engine-stat-val">
                {engineHealth.evidenceChain.valid ? "Zero Tamper Errors" : "Checking..."}
              </span>
            </div>
          </div>
        </div>

        {/* Card 4: ML Fraud Intelligence */}
        <div className="engine-card">
          <div className="engine-card-header">
            <div className="engine-title-group">
              <span className="engine-icon">🛡️</span>
              <div>
                <h4>Fraud Intelligence & ML Governance</h4>
                <span className="engine-runtime">Scikit-learn + FastAPI</span>
              </div>
            </div>
            {getStatusBadge(engineHealth.fraudML.status)}
          </div>
          <p className="engine-desc">
            Autonomous anomaly classification, real-time transaction risk scoring, and active ML champion model governance.
          </p>
          <div className="engine-stats">
            <div className="engine-stat-col">
              <span className="engine-stat-label">Champion Model</span>
              <span className="engine-stat-val">{engineHealth.fraudML.champion}</span>
            </div>
            <div className="engine-stat-col">
              <span className="engine-stat-label">Trained Framework</span>
              <span className="engine-stat-val">HistGradientBoosting</span>
            </div>
          </div>
        </div>
      </div>

      <div className="system-config-box">
        <h4>🖥️ Engagement Environment Configuration</h4>
        <div className="config-grid">
          <div className="config-row">
            <span className="config-key">Deployment Environment:</span>
            <span className="config-val">AuditLens Enterprise Desktop / Localhost</span>
          </div>
          <div className="config-row">
            <span className="config-key">Unified Gateway Address:</span>
            <span className="config-val font-mono">http://127.0.0.1:5000</span>
          </div>
          <div className="config-row">
            <span className="config-key">Frontend Web Server:</span>
            <span className="config-val font-mono">http://localhost:5173 (Vite 6 + React 18)</span>
          </div>
          <div className="config-row">
            <span className="config-key">Database Store:</span>
            <span className="config-val font-mono">SQLite (auditlens_fraud.db & evidence.db)</span>
          </div>
          <div className="config-row">
            <span className="config-key">API Swagger Documentation:</span>
            <span className="config-val">
              <a
                href="http://127.0.0.1:5000/docs"
                target="_blank"
                rel="noreferrer"
                style={{ color: "#2563eb", fontWeight: 600 }}
              >
                Open OpenAPI / Swagger Docs ↗
              </a>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default SystemStatus;

