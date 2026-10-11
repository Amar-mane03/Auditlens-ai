# AuditLens

Starter structure for an audit workflow with a Python backend and a React frontend.

## Project layout

- `backend/audit_engine/` contains the audit workflow and its supporting folders.
- `backend/tests/` contains backend unit tests.
- `frontend/` contains the React application.
- `docs/audit_guidelines.md` is the place to maintain statutory audit rules and references.
- `sample_transactions.csv` sample dataset for testing anomalies and statutory rules.

## Setup & Running

### Backend

Use Python 3.10 or newer, activate the virtual environment, then install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt flask-cors
```

Run backend unit tests:

```powershell
python -m unittest backend.tests.unit_tests
```

Start the backend API from the project root:

```powershell
python -m backend.audit_engine.audit_analysis
```

The API listens on `http://127.0.0.1:5000`; use `GET /health` to confirm it is running.

### Frontend

Install dependencies and start the Vite development server:

```powershell
cd frontend
npm install
npm run dev
```

The frontend listens on `http://localhost:5173`.
