from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from revenue_leak_radar.schemas import AnalysisRequest, HealthResponse, ResolveInput, ReviewInput
from revenue_leak_radar.services.analysis_service import RevenueLeakAnalysisService
from revenue_leak_radar.services.evidence_chain_service import evidence_chain_available
from revenue_leak_radar.services.finding_service import FindingService
from revenue_leak_radar.services.report_service import ReportService

router = APIRouter()
analysis_service = RevenueLeakAnalysisService()
finding_service = FindingService()


@router.get("/health", response_model=HealthResponse)
def health() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "service": "Revenue Leak Radar",
        "evidence_chain_available": evidence_chain_available(),
    }


@router.get("/rules")
def list_rules():
    return {
        "rules": [
            {"rule_id": "duplicate_revenue_entries", "title": "Duplicate Revenue Entries", "description": "Identifies repeated invoice/customer/date/amount combinations."},
            {"rule_id": "underbilling", "title": "Underbilling", "description": "Measures the gap between the benchmark and the actual invoiced amount."},
            {"rule_id": "unusual_discounts", "title": "Unusual Discounts", "description": "Flags discount ratios above configured policy thresholds."},
            {"rule_id": "credit_note_anomalies", "title": "Credit Notes", "description": "Flags duplicate or unmatched credit notes and out-of-period adjustments."},
            {"rule_id": "revenue_cutoff_risks", "title": "Revenue Cut-off", "description": "Flags postings outside the reporting-period boundary."},
            {"rule_id": "missing_or_inconsistent_transactions", "title": "Missing or Inconsistent Transactions", "description": "Highlights gaps and invalid values that require review."},
            {"rule_id": "price_and_quantity_mismatches", "title": "Price & Quantity Mismatch", "description": "Compares quantity x price against reported amounts with tolerance."},
            {"rule_id": "statistical_anomalies", "title": "Statistical Anomalies", "description": "Uses an isolation-forest indicator, not proof of financial misconduct."},
        ]
    }


@router.post("/upload")
async def upload_ledger(file: UploadFile = File(...)):
    try:
        response = analysis_service.upload_ledger(file)
        return response
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = finding_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/analyze")
def analyze(request: AnalysisRequest):
    try:
        result = analysis_service.analyze_job(request.job_id)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/summary")
def get_summary():
    return analysis_service.get_summary()


@router.get("/findings")
def list_findings(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
    status: Optional[str] = None,
    customer: Optional[str] = None,
    risk: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
):
    return finding_service.list_findings(page=page, limit=limit, status=status, customer=customer, risk_level=risk, from_date=from_date, to_date=to_date)


@router.get("/findings/{finding_id}")
def get_finding(finding_id: str):
    finding = finding_service.get_finding(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    return finding


@router.get("/transactions/{transaction_id}")
def get_transaction(transaction_id: str):
    items = finding_service.get_transactions(transaction_id)
    return {"transaction_id": transaction_id, "items": items}


@router.patch("/findings/{finding_id}/review")
def review_finding(finding_id: str, payload: ReviewInput):
    finding = finding_service.get_finding(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    updated = finding_service.patch_review(finding_id, payload.status, payload.reviewer, payload.comments)
    return updated


@router.post("/findings/{finding_id}/resolve")
def resolve_finding(finding_id: str, payload: ResolveInput):
    finding = finding_service.get_finding(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    updated = finding_service.resolve_finding(finding_id, payload.status, payload.reviewer, payload.resolution_notes)
    return updated


@router.get("/export/csv")
def export_csv():
    findings = finding_service.list_findings(page=1, limit=500)["items"]
    path = ReportService.export_csv(findings, filename="revenue_leak_findings.csv")
    return FileResponse(path, media_type="text/csv", filename="revenue_leak_findings.csv")


@router.get("/export/excel")
def export_excel():
    findings = finding_service.list_findings(page=1, limit=500)["items"]
    path = ReportService.export_excel(findings, filename="revenue_leak_findings.xlsx")
    return FileResponse(path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename="revenue_leak_findings.xlsx")


@router.get("/export/pdf")
def export_pdf():
    findings = finding_service.list_findings(page=1, limit=500)["items"]
    path = ReportService.export_pdf(findings, filename="revenue_leak_findings.pdf")
    return FileResponse(path, media_type="application/pdf", filename="revenue_leak_findings.pdf")
