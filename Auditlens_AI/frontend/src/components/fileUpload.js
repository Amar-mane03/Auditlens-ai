import React, { useState } from "react";
import axios from "axios";

function FileUpload({ setAuditData, onAnalysisComplete }) {
  const [files, setFiles] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");
  const [isDragging, setIsDragging] = useState(false);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      setFiles(Array.from(e.target.files));
      setStatusMessage("");
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setFiles(Array.from(e.dataTransfer.files));
      setStatusMessage("");
    }
  };

  const handleUpload = async () => {
    if (!files || files.length === 0) {
      alert("Please choose a CSV or Excel (.xlsx) file first.");
      return;
    }

    const formData = new FormData();
    if (files.length === 1) {
      formData.append("file", files[0]);
    }
    files.forEach((file) => {
      formData.append("files", file);
    });

    setIsLoading(true);
    setStatusMessage("Uploading and running AI statutory audit algorithms...");

    try {
      const res = await axios.post("/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setAuditData(res.data);
      setStatusMessage("Audit analysis completed successfully!");
      if (onAnalysisComplete) onAnalysisComplete(res.data);
    } catch (err) {
      const errorMsg =
        err.response?.data?.error ||
        err.response?.statusText ||
        err.message ||
        "Unknown network or server error";
      alert("Upload failed: " + errorMsg);
      setStatusMessage("Upload failed: " + errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleLoadSample = async () => {
    setIsLoading(true);
    setStatusMessage("Loading built-in sample audit transactions...");

    try {
      const res = await axios.get("/sample-data");
      setAuditData(res.data);
      setStatusMessage("Sample audit data loaded successfully!");
      if (onAnalysisComplete) onAnalysisComplete(res.data);
    } catch (err) {
      const errorMsg =
        err.response?.data?.error ||
        err.message ||
        "Could not load sample data. Ensure backend is running.";
      alert("Sample load failed: " + errorMsg);
      setStatusMessage("Sample load failed: " + errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return "0 KB";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / 1048576).toFixed(1) + " MB";
  };

  return (
    <div className="ingestion-hub-container">
      <div className="section-header">
        <div>
          <h2>Financial Ledger Data Ingestion</h2>
          <p className="subtitle">
            Ingest structured transaction journals, vendor invoices, and general ledgers for automated statutory audit and anomaly screening.
          </p>
        </div>
      </div>

      <div className="ingestion-grid">
        {/* Left: Drag & Drop Ingestion Card */}
        <div className="ingestion-card">
          <div
            className={`dropzone ${isDragging ? "dropzone-active" : ""}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <div className="dropzone-icon">📥</div>
            <h3 className="dropzone-title">Drag & Drop Ledger Files Here</h3>
            <p className="dropzone-sub">
              Supports CSV, TSV, and Excel (<code>.xlsx</code>, <code>.xls</code>) workpapers
            </p>

            <label className="btn btn-secondary file-browse-btn">
              Browse Files from Computer
              <input
                type="file"
                accept=".csv,.xlsx,.xls,.tsv"
                multiple
                onChange={handleFileChange}
                disabled={isLoading}
                style={{ display: "none" }}
              />
            </label>
          </div>

          {/* Selected File Preview List */}
          {files.length > 0 && (
            <div className="staged-files-box">
              <span className="staged-files-label">Staged Files for Audit ({files.length}):</span>
              <div className="staged-files-list">
                {files.map((f, i) => (
                  <div key={i} className="staged-file-item">
                    <span className="file-doc-icon">📄</span>
                    <span className="file-name">{f.name}</span>
                    <span className="file-size">{formatFileSize(f.size)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="upload-actions-bar">
            <button
              onClick={handleUpload}
              disabled={isLoading || files.length === 0}
              className="btn btn-primary btn-large"
            >
              {isLoading ? "Running Anomaly Engine..." : "🚀 Execute Statutory Audit"}
            </button>
            {files.length > 0 && (
              <button
                onClick={() => setFiles([])}
                disabled={isLoading}
                className="btn btn-secondary"
              >
                Clear Selection
              </button>
            )}
          </div>

          {statusMessage && (
            <div
              className={`status-pill ${
                statusMessage.includes("failed") ? "status-error" : "status-info"
              }`}
            >
              {statusMessage}
            </div>
          )}
        </div>

        {/* Right: Quick Ingestion Presets & Schema Guide */}
        <div className="ingestion-sidebar">
          {/* Preset Sample Data */}
          <div className="preset-card">
            <div className="preset-card-header">
              <span className="preset-icon">⚡</span>
              <div>
                <h4>Pre-Configured Audit Sandbox</h4>
                <p>Instant demonstration with dirty fraud test records</p>
              </div>
            </div>
            <p className="preset-desc">
              Instantly load a curated dataset containing duplicate invoices, off-hours weekend transactions, round-number journal manipulations, and tax anomalies.
            </p>
            <button
              onClick={handleLoadSample}
              disabled={isLoading}
              className="btn btn-preset"
            >
              ✨ Load 1-Click Sample Audit Dataset
            </button>
          </div>

          {/* Expected Data Schema */}
          <div className="schema-card">
            <h4>Expected Ledger Attributes</h4>
            <ul className="schema-list">
              <li>
                <code>transaction_id</code> <span>Unique journal entry identifier</span>
              </li>
              <li>
                <code>amount</code> <span>Transaction value or debit/credit</span>
              </li>
              <li>
                <code>date</code> <span>ISO or standard timestamp</span>
              </li>
              <li>
                <code>customer_id / vendor_id</code> <span>Counterparty entity identifiers</span>
              </li>
              <li>
                <code>tax_amount / discount</code> <span>Statutory statutory calculation inputs</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

export default FileUpload;
