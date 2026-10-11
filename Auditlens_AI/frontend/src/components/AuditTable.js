import React, { useState } from "react";

function AuditTable({ details, transactions, onLoadSample }) {
  const list = details || transactions || [];
  const [filterRisk, setFilterRisk] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");

  if (!list || list.length === 0) {
    return (
      <div className="empty-state-card">
        <div className="empty-state-icon">📋</div>
        <h3>No Transaction Records Loaded</h3>
        <p>
          The transaction registry displays complete multi-currency ledgers with statutory risk scoring. Ingest a ledger or load sample data to explore records.
        </p>
        {onLoadSample && (
          <div style={{ marginTop: "16px" }}>
            <button onClick={onLoadSample} className="btn btn-primary">
              ✨ Load Built-In Sample Dataset
            </button>
          </div>
        )}
      </div>
    );
  }

  const filtered = list.filter((item) => {
    if (filterRisk !== "ALL" && item.classification !== filterRisk) {
      return false;
    }
    if (searchQuery.trim() !== "") {
      const q = searchQuery.toLowerCase();
      const idMatch = String(item.transaction_id || "").toLowerCase().includes(q);
      const custMatch = String(item.customer_id || "").toLowerCase().includes(q);
      const vendMatch = String(item.vendor_id || "").toLowerCase().includes(q);
      return idMatch || custMatch || vendMatch;
    }
    return true;
  });

  return (
    <div className="audit-table-container">
      <div className="table-header-controls">
        <div>
          <h3>Transaction Registry & Journal Ledger</h3>
          <p className="subtitle" style={{ marginBottom: 0 }}>
            Displaying {filtered.length} of {list.length} ledger journal entries
          </p>
        </div>
        <div className="filters">
          <input
            type="text"
            placeholder="Search by ID, Customer, Vendor..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="search-input"
            style={{ width: "240px" }}
          />
          <select
            value={filterRisk}
            onChange={(e) => setFilterRisk(e.target.value)}
            className="filter-select"
          >
            <option value="ALL">All Risk Levels</option>
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
              <th>Customer</th>
              <th>Vendor</th>
              <th>Amount</th>
              <th>Risk Score</th>
              <th>Classification</th>
              <th>Flags</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((txn, idx) => {
              const flagsText = Array.isArray(txn.flags)
                ? (txn.flags.length > 0 ? txn.flags.join(", ") : "None")
                : String(txn.flags || "None");
              const classificationClass = `badge badge-${(txn.classification || "low").toLowerCase()}`;

              return (
                <tr key={txn.transaction_id || idx}>
                  <td className="font-mono">{txn.transaction_id ?? "N/A"}</td>
                  <td>{txn.customer_id ?? "N/A"}</td>
                  <td>{txn.vendor_id ?? "N/A"}</td>
                  <td style={{ fontWeight: 600 }}>₹{Number(txn.amount || 0).toLocaleString()}</td>
                  <td>
                    <span className="score-pill">{txn.risk_score ?? 0}</span>
                  </td>
                  <td>
                    <span className={classificationClass}>{txn.classification}</span>
                  </td>
                  <td className="flags-cell">{flagsText}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default AuditTable;
