# Revenue Leak Radar

This MVP backend module is designed for RevAI and integrates with the local evidence-chain service running on port 8001.

## Prerequisites

- Python 3.11+
- FastAPI, pandas, numpy, openpyxl, scikit-learn, reportlab, pytest

## Install

```powershell
cd D:\Projects\RevAI\Revenue_leak_radar
python -m pip install -r requirements.txt
```

## Run locally

```powershell
cd D:\Projects\RevAI\Revenue_leak_radar
python -m uvicorn main:app --reload --port 8002
```

Then open:
- Swagger UI: http://localhost:8002/docs
- Evidence Chain service: http://localhost:8001/docs

## Endpoints

- GET /api/revenue-leak-radar/health
- GET /api/revenue-leak-radar/rules
- POST /api/revenue-leak-radar/upload
- POST /api/revenue-leak-radar/analyze
- GET /api/revenue-leak-radar/findings
- PATCH /api/revenue-leak-radar/findings/{finding_id}/review
- POST /api/revenue-leak-radar/findings/{finding_id}/resolve
- GET /api/revenue-leak-radar/export/csv
- GET /api/revenue-leak-radar/export/excel
- GET /api/revenue-leak-radar/export/pdf

## Example request body

```json
{
  "job_id": "abc123",
  "analysis_name": "demo-analysis"
}
```

## Sample CSV

See `demo/sample_revenue_ledger.csv` for a synthetic ledger including normal, duplicate, underbilling, and credit-note anomaly examples.

## Notes

- The rule logic is deterministic and transparent.
- Audit events are recorded through the local evidence-chain endpoint when available.
- If the evidence-chain service is unavailable, the detection engine still works and surfaces a clear warning in the health response.
