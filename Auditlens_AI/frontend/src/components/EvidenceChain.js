import React, { useState, useEffect } from "react";
import axios from "axios";

function EvidenceChain() {
  const [events, setEvents] = useState([]);
  const [verification, setVerification] = useState(null);
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");

  // Upload Evidence state
  const [evidenceFile, setEvidenceFile] = useState(null);
  const [evidenceActor, setEvidenceActor] = useState("lead.auditor@firm.com");
  const [evidenceTxnId, setEvidenceTxnId] = useState("TXN-101");

  // Log Event state
  const [logActor, setLogActor] = useState("compliance.officer@firm.com");
  const [logEventType, setLogEventType] = useState("AUDIT_TEST_RUN");
  const [logTxnId, setLogTxnId] = useState("TXN-101");
  const [logDetails, setLogDetails] = useState("Verified 3-way match between PO, Goods Receipt, and Invoice.");

  useEffect(() => {
    fetchEvents();
    handleVerifyChain();
  }, []);

  const fetchEvents = async () => {
    try {
      const res = await axios.get("/api/evidence-chain/events?limit=100");
      setEvents(res.data.events || []);
    } catch (err) {
      console.warn("Could not fetch evidence events:", err.message);
    }
  };

  const handleVerifyChain = async () => {
    setLoading(true);
    setStatusMessage("Verifying cryptographic SHA-256 chain and stored evidence hashes...");

    try {
      const res = await axios.get("/api/evidence-chain/verify");
      setVerification(res.data);
      setStatusMessage(
        res.data.valid
          ? `Cryptographic chain intact! Verified ${res.data.events_checked} block(s) with zero tamper errors.`
          : `WARNING: Integrity check failed! ${res.data.errors?.length || 0} anomaly(ies) detected.`
      );
    } catch (err) {
      const msg = err.response?.data?.detail || err.message;
      setStatusMessage("Verification error: " + msg);
    } finally {
      setLoading(false);
    }
  };

  const handleUploadEvidence = async (e) => {
    e.preventDefault();
    if (!evidenceFile) {
      alert("Please select a file to store in the evidence chain.");
      return;
    }

    setLoading(true);
    setStatusMessage("Calculating SHA-256 digest and appending immutable evidence block...");

    try {
      const formData = new FormData();
      formData.append("file", evidenceFile);
      formData.append("actor", evidenceActor);
      formData.append("transaction_id", evidenceTxnId);

      const res = await axios.post("/api/evidence-chain/evidence/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      setStatusMessage(`Evidence stored! SHA-256: ${res.data.evidence_sha256.substring(0, 16)}...`);
      setEvidenceFile(null);
      await fetchEvents();
      await handleVerifyChain();
    } catch (err) {
      const msg = err.response?.data?.detail || err.message;
      alert("Evidence upload failed: " + msg);
      setStatusMessage("Evidence upload failed: " + msg);
    } finally {
      setLoading(false);
    }
  };

  const handleLogEvent = async (e) => {
    e.preventDefault();
    setLoading(true);
    setStatusMessage("Appending cryptographic audit event block...");

    try {
      const formData = new URLSearchParams();
      formData.append("actor", logActor);
      formData.append("event_type", logEventType);
      formData.append("transaction_id", logTxnId);
      formData.append("details", logDetails);

      await axios.post("/api/evidence-chain/events", formData, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });

      setStatusMessage("Audit event block appended to chain successfully!");
      await fetchEvents();
      await handleVerifyChain();
    } catch (err) {
      const msg = err.response?.data?.detail || err.message;
      alert("Event logging failed: " + msg);
      setStatusMessage("Event logging failed: " + msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="evidence-container">
      <div className="section-header">
        <div>
          <h2>🔗 Evidence Chain & Cryptographic Trust</h2>
          <p className="subtitle">
            Tamper-evident audit trail backed by SHA-256 hash-chaining and immutable SQLite ledger verification.
          </p>
        </div>
        <button onClick={handleVerifyChain} disabled={loading} className="btn btn-primary">
          🛡️ Verify Chain Integrity
        </button>
      </div>

      {verification && (
        <div
          className={`status-pill ${verification.valid ? "status-info" : "status-error"}`}
          style={{
            marginBottom: "20px",
            padding: "16px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div>
            <div style={{ fontWeight: 700, fontSize: "15px" }}>
              {verification.valid ? "✅ Cryptographic Ledger Valid & Verified" : "❌ Cryptographic Chain Compromised"}
            </div>
            <div style={{ fontSize: "12px", marginTop: "4px" }}>
              Blocks verified: <strong>{verification.events_checked}</strong> | Latest Block Hash:{" "}
              <code style={{ fontSize: "11px" }}>{verification.last_verified_hash.substring(0, 24)}...</code>
            </div>
          </div>
          <span className={`badge badge-${verification.valid ? "low" : "critical"}`}>
            {verification.valid ? "UNCOMPROMISED" : "TAMPERED"}
          </span>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "20px", marginBottom: "24px" }}>
        {/* Upload Supporting Evidence Form */}
        <div className="upload-container">
          <h3 style={{ fontSize: "16px", marginBottom: "8px" }}>📁 Anchor Evidence Document</h3>
          <p style={{ fontSize: "12px", color: "#64748b", marginBottom: "16px" }}>
            Upload invoice PDFs, PO contracts, or approval emails. The file is hashed and chained into the audit log.
          </p>
          <form onSubmit={handleUploadEvidence}>
            <div style={{ marginBottom: "10px" }}>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "4px" }}>
                Supporting File:
              </label>
              <input
                type="file"
                onChange={(e) => setEvidenceFile(e.target.files[0] || null)}
                disabled={loading}
                style={{ fontSize: "13px" }}
              />
            </div>
            <div style={{ marginBottom: "10px" }}>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "4px" }}>
                Auditor / Actor:
              </label>
              <input
                type="text"
                value={evidenceActor}
                onChange={(e) => setEvidenceActor(e.target.value)}
                style={{ width: "100%", padding: "7px 10px", border: "1px solid #cbd5e1", borderRadius: "6px" }}
              />
            </div>
            <div style={{ marginBottom: "14px" }}>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "4px" }}>
                Transaction ID:
              </label>
              <input
                type="text"
                value={evidenceTxnId}
                onChange={(e) => setEvidenceTxnId(e.target.value)}
                style={{ width: "100%", padding: "7px 10px", border: "1px solid #cbd5e1", borderRadius: "6px" }}
              />
            </div>
            <button type="submit" disabled={loading || !evidenceFile} className="btn btn-primary" style={{ width: "100%" }}>
              🔒 Seal & Store Evidence Block
            </button>
          </form>
        </div>

        {/* Record Audit Event Form */}
        <div className="upload-container">
          <h3 style={{ fontSize: "16px", marginBottom: "8px" }}>✍️ Record Immutable Audit Event</h3>
          <p style={{ fontSize: "12px", color: "#64748b", marginBottom: "16px" }}>
            Append a formal audit procedure, finding review, or test record with forward-linked cryptographic block hashes.
          </p>
          <form onSubmit={handleLogEvent}>
            <div style={{ marginBottom: "10px" }}>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "4px" }}>
                Event Type:
              </label>
              <select
                value={logEventType}
                onChange={(e) => setLogEventType(e.target.value)}
                style={{ width: "100%", padding: "7px 10px", border: "1px solid #cbd5e1", borderRadius: "6px" }}
              >
                <option value="AUDIT_TEST_RUN">AUDIT_TEST_RUN (Test Procedure)</option>
                <option value="FINDING_CREATED">FINDING_CREATED (New Exception)</option>
                <option value="FINDING_REVIEWED">FINDING_REVIEWED (Auditor Review)</option>
                <option value="EVIDENCE_REVIEWED">EVIDENCE_REVIEWED (Evidence Inspection)</option>
              </select>
            </div>
            <div style={{ marginBottom: "10px" }}>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "4px" }}>
                Actor:
              </label>
              <input
                type="text"
                value={logActor}
                onChange={(e) => setLogActor(e.target.value)}
                style={{ width: "100%", padding: "7px 10px", border: "1px solid #cbd5e1", borderRadius: "6px" }}
              />
            </div>
            <div style={{ marginBottom: "10px" }}>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "4px" }}>
                Transaction ID:
              </label>
              <input
                type="text"
                value={logTxnId}
                onChange={(e) => setLogTxnId(e.target.value)}
                style={{ width: "100%", padding: "7px 10px", border: "1px solid #cbd5e1", borderRadius: "6px" }}
              />
            </div>
            <div style={{ marginBottom: "14px" }}>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "4px" }}>
                Investigation Notes:
              </label>
              <input
                type="text"
                value={logDetails}
                onChange={(e) => setLogDetails(e.target.value)}
                style={{ width: "100%", padding: "7px 10px", border: "1px solid #cbd5e1", borderRadius: "6px" }}
              />
            </div>
            <button type="submit" disabled={loading} className="btn btn-secondary" style={{ width: "100%" }}>
              ⛓️ Append Event Block
            </button>
          </form>
        </div>
      </div>

      {/* Blockchain Ledger Table */}
      <div className="audit-table-container">
        <h3>Immutable Audit Event Ledger ({events.length} Blocks)</h3>
        {events.length === 0 ? (
          <p style={{ color: "#64748b", padding: "16px 0" }}>
            No audit events recorded yet. Upload an evidence file or log an audit event above.
          </p>
        ) : (
          <div className="table-responsive">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>Seq</th>
                  <th>Event Type</th>
                  <th>Actor</th>
                  <th>Txn ID</th>
                  <th>Evidence File / Hash</th>
                  <th>Previous Block Hash</th>
                  <th>Block Hash</th>
                  <th>Timestamp (UTC)</th>
                </tr>
              </thead>
              <tbody>
                {events.map((ev) => (
                  <tr key={ev.event_id}>
                    <td>
                      <span className="score-pill">#{ev.sequence}</span>
                    </td>
                    <td>
                      <span className="badge badge-high">{ev.event_type}</span>
                    </td>
                    <td>{ev.actor}</td>
                    <td className="font-mono">{ev.transaction_id || "N/A"}</td>
                    <td>
                      {ev.filename ? (
                        <div>
                          <div>📄 {ev.filename}</div>
                          <code style={{ fontSize: "10px", color: "#64748b" }}>
                            {ev.evidence_sha256?.substring(0, 16)}...
                          </code>
                        </div>
                      ) : (
                        <span style={{ color: "#94a3b8" }}>No file</span>
                      )}
                    </td>
                    <td>
                      <code style={{ fontSize: "11px", color: "#64748b" }}>
                        {ev.previous_hash === "GENESIS" ? "GENESIS" : `${ev.previous_hash?.substring(0, 12)}...`}
                      </code>
                    </td>
                    <td>
                      <code style={{ fontSize: "11px", color: "#2563eb", fontWeight: 600 }}>
                        {ev.event_hash?.substring(0, 12)}...
                      </code>
                    </td>
                    <td style={{ fontSize: "11px", whiteSpace: "nowrap" }}>
                      {ev.timestamp ? new Date(ev.timestamp).toLocaleString() : "N/A"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default EvidenceChain;

