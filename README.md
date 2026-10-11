# AuditLens - AI Financial Anomaly & Statutory Audit Engine

AuditLens is a financial audit platform with a Python Flask analytics backend and a React + Vite frontend for detecting transaction anomalies, duplicate invoices, suspicious refunds, period-end manipulations, and tax mismatches.

---

## Quick Start

You can run both backend and frontend from the root using the batch scripts or manually:

### 1. Run Backend API
Double click `run_backend.bat` or run in PowerShell:
```powershell
.\run_backend.bat
```
Alternatively:
```powershell
cd Auditlens_AI
.\.venv\Scripts\python.exe -m backend.audit_engine.audit_analysis
```
- API will start at `http://127.0.0.1:5000`
- Confirm by visiting `http://127.0.0.1:5000/health` (returns `{"status":"ok"}`)

### 2. Run Frontend Dev Server
Double click `run_frontend.bat` or run in PowerShell:
```powershell
.\run_frontend.bat
```
Alternatively:
```powershell
cd Auditlens_AI\frontend
npm run dev
```
- Frontend will start at `http://localhost:5173`

### 3. Run Backend Tests
Double click `test_backend.bat` or run:
```powershell
cd Auditlens_AI
.\.venv\Scripts\python.exe -m unittest backend.tests.unit_tests
```

---

## Testing with Sample Data

A pre-configured sample dataset is provided at:
- `sample_transactions.csv` (at project root and inside `Auditlens_AI/`)

In the UI:
1. Click **"✨ Load Sample Data"** to immediately analyze built-in test records.
2. Or click **"📁 Choose Files"**, select `sample_transactions.csv`, and click **"🚀 Upload & Analyze"**.
3. View the **Executive Summary**, **Risk Distribution**, and **Auditor Investigation Workbench**.
4. Click **"📥 Download Audit Report (.xlsx)"** to export the verified findings to Excel.

---

## Key Fixes & Enhancements Made

1. **Virtual Environment Reconfiguration**:
   - Fixed broken virtual environment configured for non-existent Python 3.14 by creating a valid environment with system Python 3.13 and installing all required packages (`pandas`, `numpy`, `openpyxl`, `flask`, `flask-cors`, etc.).

2. **Backend Logic & Type Safety**:
   - Fixed `TypeError` in arithmetic operations when string numbers or currencies (e.g., `"$1,000"`, `"180.0"`) appear in `invoice_amount`, `tax_amount`, `discount`, or `frequency`.
   - Fixed impossible 24-hr condition `ts.hour > 23` to `ts.hour < 6 or ts.hour >= 23`.
   - Fixed `amount % 100_000 == 0` flagging `$0` as a round-number anomaly (`amount > 0 and amount % 100_000 == 0`).
   - Added column name normalization (trim and lowercase) to support capitalized CSV headers like `Amount`, `Transaction_ID`.
   - Added `/reports/<filename>` endpoint for downloading generated Excel audit reports.
   - Added `/sample-data` endpoint for instant 1-click test runs.
   - Fixed Excel export formatting so list flags are cleanly serialized as comma-separated text.

3. **Frontend Fixes & Enhancements**:
   - Fixed inverted component exports between `AuditSummary.js` and `AuditTable.js`.
   - Fixed unhandled Axios errors in `fileUpload.js` to surface backend error descriptions.
   - Added multi-file selection support, loading indicators, and a sample data loader.
   - Added interactive decision toggling (Pending -> Reviewed -> Escalated) in the Investigation Workbench.
   - Added real-time search and classification filtering (Critical, High, Medium, Low).
   - Added full Vite proxy configuration to route API requests to port 5000.
   - Added a modern responsive CSS interface (`App.css`).

