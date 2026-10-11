import React, { useState, useEffect } from "react";
import axios from "axios";
import FileUpload from "./src/components/fileUpload";
import Dashboard from "./src/components/Dashboard";
import Investigation from "./src/components/Investigation";
import AuditTable from "./src/components/AuditTable";
import RevenueLeakRadar from "./src/components/RevenueLeakRadar";
import EvidenceChain from "./src/components/EvidenceChain";
import FraudIntelligence from "./src/components/FraudIntelligence";
import AuditReports from "./src/components/AuditReports";
import SystemStatus from "./src/components/SystemStatus";
import "./src/App.css";

function App() {
  const [activeSection, setActiveSection] = useState("overview");
  const [auditData, setAuditData] = useState(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isSampleLoading, setIsSampleLoading] = useState(false);
  const [globalSearch, setGlobalSearch] = useState("");
  const [apiOnline, setApiOnline] = useState(true);

  // Check health on mount
  useEffect(() => {
    checkHealth();
  }, []);

  const checkHealth = async () => {
    try {
      const res = await axios.get("/health");
      setApiOnline(res.data?.status === "ok");
    } catch {
      setApiOnline(false);
    }
  };

  const handleLoadSample = async () => {
    setIsSampleLoading(true);
    try {
      const res = await axios.get("/sample-data");
      setAuditData(res.data);
      // Auto navigate to overview or investigation to see results
      if (activeSection === "ingest") {
        setActiveSection("overview");
      }
    } catch (err) {
      alert("Could not load sample data: " + (err.response?.data?.error || err.message));
    } finally {
      setIsSampleLoading(false);
    }
  };

  const getSectionTitle = () => {
    switch (activeSection) {
      case "overview":
        return "Executive Overview & Risk Dashboard";
      case "ingest":
        return "Data Ingestion & Audit Run";
      case "investigation":
        return "Auditor Investigation Workbench";
      case "registry":
        return "Transaction Registry & General Ledger";
      case "radar":
        return "Revenue Leak Radar";
      case "evidence":
        return "Cryptographic Evidence Chain";
      case "fraud":
        return "Fraud Intelligence & Autonomous ML";
      case "reports":
        return "Audit Reports & Statutory Exports";
      case "system":
        return "System Infrastructure & Diagnostics";
      default:
        return "AuditLens Enterprise Platform";
    }
  };

  const flaggedCount = auditData?.investigation?.length || 0;
  const criticalCount = auditData?.dashboard?.risk_distribution?.Critical || 0;
  const highCount = auditData?.dashboard?.risk_distribution?.High || 0;

  return (
    <div className={`enterprise-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
      {/* 1. Left-Hand Professional Navigation Sidebar */}
      <aside className="enterprise-sidebar">
        {/* Brand Header */}
        <div className="sidebar-brand">
          <div className="brand-emblem">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 2L3 6V12C3 17.52 6.84 22.74 12 24C17.16 22.74 21 17.52 21 12V6L12 2Z" fill="#2563EB" opacity="0.2"/>
              <path d="M12 2L3 6V12C3 17.52 6.84 22.74 12 24C17.16 22.74 21 17.52 21 12V6L12 2Z" stroke="#3B82F6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <circle cx="12" cy="11" r="4" stroke="#60A5FA" strokeWidth="2"/>
              <path d="M15 14L18 17" stroke="#93C5FD" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </div>
          <div className="brand-text-block">
            <div className="brand-title-row">
              <span className="brand-name">AuditLens</span>
              <span className="brand-badge">ENTERPRISE</span>
            </div>
            <span className="brand-subtitle">Financial Assurance & AI Audit</span>
          </div>
        </div>

        {/* Engagement Context Card */}
        <div className="engagement-card">
          <div className="engagement-header">
            <span className="engagement-dot"></span>
            <span className="engagement-status">LIVE ENGAGEMENT</span>
          </div>
          <div className="engagement-client">Apex Global Corp</div>
          <div className="engagement-desc">Q3 Statutory Audit • ISA 240 / SOX</div>
        </div>

        {/* Navigation Sections */}
        <nav className="sidebar-nav">
          {/* Section Group 1 */}
          <div className="nav-group-label">Core Audit & Assurance</div>

          <button
            className={`nav-item ${activeSection === "overview" ? "active" : ""}`}
            onClick={() => setActiveSection("overview")}
          >
            <span className="nav-icon">📊</span>
            <span className="nav-text">Executive Overview</span>
          </button>

          <button
            className={`nav-item ${activeSection === "ingest" ? "active" : ""}`}
            onClick={() => setActiveSection("ingest")}
          >
            <span className="nav-icon">📥</span>
            <span className="nav-text">Data Ingestion</span>
            {auditData && <span className="nav-pill pill-success">Loaded</span>}
          </button>

          <button
            className={`nav-item ${activeSection === "investigation" ? "active" : ""}`}
            onClick={() => setActiveSection("investigation")}
          >
            <span className="nav-icon">🔎</span>
            <span className="nav-text">Investigation Workbench</span>
            {flaggedCount > 0 && (
              <span className="nav-pill pill-danger">{flaggedCount}</span>
            )}
          </button>

          <button
            className={`nav-item ${activeSection === "registry" ? "active" : ""}`}
            onClick={() => setActiveSection("registry")}
          >
            <span className="nav-icon">📋</span>
            <span className="nav-text">Transaction Registry</span>
          </button>

          {/* Section Group 2 */}
          <div className="nav-group-label">Intelligent Risk Engines</div>

          <button
            className={`nav-item ${activeSection === "radar" ? "active" : ""}`}
            onClick={() => setActiveSection("radar")}
          >
            <span className="nav-icon">🎯</span>
            <span className="nav-text">Revenue Leak Radar</span>
            <span className="nav-pill pill-neutral">5 Rules</span>
          </button>

          <button
            className={`nav-item ${activeSection === "evidence" ? "active" : ""}`}
            onClick={() => setActiveSection("evidence")}
          >
            <span className="nav-icon">🔗</span>
            <span className="nav-text">Evidence Chain</span>
            <span className="nav-pill pill-neutral">SHA-256</span>
          </button>

          <button
            className={`nav-item ${activeSection === "fraud" ? "active" : ""}`}
            onClick={() => setActiveSection("fraud")}
          >
            <span className="nav-icon">🛡️</span>
            <span className="nav-text">Fraud ML Intelligence</span>
            <span className="nav-pill pill-ai">AI v2.1</span>
          </button>

          {/* Section Group 3 */}
          <div className="nav-group-label">Governance & System</div>

          <button
            className={`nav-item ${activeSection === "reports" ? "active" : ""}`}
            onClick={() => setActiveSection("reports")}
          >
            <span className="nav-icon">📑</span>
            <span className="nav-text">Reports & Exports</span>
          </button>

          <button
            className={`nav-item ${activeSection === "system" ? "active" : ""}`}
            onClick={() => setActiveSection("system")}
          >
            <span className="nav-icon">⚡</span>
            <span className="nav-text">System Diagnostics</span>
            <span className={`nav-pill ${apiOnline ? "pill-success" : "pill-danger"}`}>
              {apiOnline ? "Online" : "Down"}
            </span>
          </button>
        </nav>

        {/* Sidebar Footer: Auditor Profile & System Status */}
        <div className="sidebar-footer">
          <div className="auditor-profile-card">
            <div className="auditor-avatar">AM</div>
            <div className="auditor-info">
              <span className="auditor-name">Amar Mane</span>
              <span className="auditor-role">Lead Statutory Auditor</span>
            </div>
          </div>
          <div className="api-badge">
            <span className={`status-indicator-dot ${apiOnline ? "online" : "offline"}`}></span>
            <span>{apiOnline ? "Unified API • 127.0.0.1:5000" : "API Offline"}</span>
          </div>
        </div>
      </aside>

      {/* 2. Main Content Container */}
      <div className="enterprise-main">
        {/* Top Navigation Bar / App Bar */}
        <header className="enterprise-topbar">
          <div className="topbar-left">
            <button
              className="sidebar-toggle-btn"
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              title="Toggle Sidebar"
            >
              ☰
            </button>
            <div className="breadcrumb-nav">
              <span className="breadcrumb-root">AuditLens Enterprise</span>
              <span className="breadcrumb-sep">/</span>
              <span className="breadcrumb-group">Financial Assurance</span>
              <span className="breadcrumb-sep">/</span>
              <span className="breadcrumb-current">{getSectionTitle()}</span>
            </div>
          </div>

          <div className="topbar-right">
            {/* Quick Sample Button */}
            <button
              onClick={handleLoadSample}
              disabled={isSampleLoading}
              className="btn btn-quick-sample"
              title="Quickly test the platform with built-in financial dirty fraud transactions"
            >
              {isSampleLoading ? "⚡ Analyzing Data..." : "✨ Quick Sample Run"}
            </button>

            {/* Quick Export Report Button (if report available) */}
            {auditData?.report_url && (
              <a
                href={
                  auditData.report_url.startsWith("http")
                    ? auditData.report_url
                    : `http://127.0.0.1:5000${auditData.report_url}`
                }
                download
                className="btn btn-export-quick"
              >
                📥 Export Report (.xlsx)
              </a>
            )}

            {/* Notification Badge */}
            <div
              className="notification-badge-btn"
              title={`${criticalCount + highCount} High or Critical findings`}
              onClick={() => setActiveSection("investigation")}
            >
              <span>🔔</span>
              {(criticalCount > 0 || highCount > 0) && (
                <span className="badge-count">{criticalCount + highCount}</span>
              )}
            </div>

            {/* System Status Pill */}
            <div
              className={`system-ping-pill ${apiOnline ? "ping-online" : "ping-offline"}`}
              onClick={() => setActiveSection("system")}
              title="Click to view detailed micro-engine health"
            >
              <span className="ping-dot"></span>
              <span>{apiOnline ? "System Ready" : "API Error"}</span>
            </div>
          </div>
        </header>

        {/* Dynamic Section Viewport */}
        <main className="enterprise-viewport">
          {/* Section 1: Executive Overview */}
          {activeSection === "overview" && (
            <Dashboard
              data={auditData}
              onLoadSample={handleLoadSample}
              onNavigateSection={setActiveSection}
            />
          )}

          {/* Section 2: Data Ingestion Hub */}
          {activeSection === "ingest" && (
            <FileUpload
              setAuditData={setAuditData}
              onAnalysisComplete={() => setActiveSection("overview")}
            />
          )}

          {/* Section 3: Investigation Workbench */}
          {activeSection === "investigation" && (
            <Investigation
              transactions={auditData?.investigation}
              onLoadSample={handleLoadSample}
            />
          )}

          {/* Section 4: Transaction Registry */}
          {activeSection === "registry" && (
            <AuditTable
              details={auditData?.investigation}
              onLoadSample={handleLoadSample}
            />
          )}

          {/* Section 5: Revenue Leak Radar */}
          {activeSection === "radar" && <RevenueLeakRadar />}

          {/* Section 6: Cryptographic Evidence Chain */}
          {activeSection === "evidence" && <EvidenceChain />}

          {/* Section 7: Fraud ML Intelligence */}
          {activeSection === "fraud" && <FraudIntelligence />}

          {/* Section 8: Audit Reports & Exports */}
          {activeSection === "reports" && (
            <AuditReports
              auditData={auditData}
              onTriggerSample={handleLoadSample}
            />
          )}

          {/* Section 9: System Diagnostics */}
          {activeSection === "system" && <SystemStatus />}
        </main>
      </div>
    </div>
  );
}

export default App;
