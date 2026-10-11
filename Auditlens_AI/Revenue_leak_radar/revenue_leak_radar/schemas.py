from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    job_id: str
    analysis_name: Optional[str] = "default-analysis"


class HealthResponse(BaseModel):
    status: str
    service: str
    evidence_chain_available: bool = False


class ReviewInput(BaseModel):
    status: str = Field(..., example="UNDER_REVIEW")
    reviewer: str = Field(..., example="analyst@company.com")
    comments: Optional[str] = None


class ResolveInput(BaseModel):
    status: str = Field(..., example="RESOLVED")
    reviewer: str = Field(..., example="analyst@company.com")
    resolution_notes: Optional[str] = None


class UploadJob(BaseModel):
    job_id: str
    filename: str
    rows_loaded: int
    summary: Dict[str, Any]
    status: str = "uploaded"


class FindingRecord(BaseModel):
    finding_id: str
    transaction_id: Optional[str]
    rule_ids: List[str]
    risk_score: int
    risk_level: str
    reasons: List[str]
    supporting_values: Dict[str, Any]
    potential_shortfall: Optional[float] = None
    source_file: Optional[str] = None
    source_row: Optional[int] = None
    requires_manual_review: bool = True
    status: str = "OPEN"
    created_at: datetime


class SummaryResponse(BaseModel):
    total_eligible_revenue: float
    transactions_analyzed: int
    flagged_transactions: int
    unique_affected_invoices: int
    total_potential_shortfall: float
    flagged_gross_transaction_value: float
    flagged_credit_note_value: float
    high_critical_count: int
    leakage_indicators: Dict[str, Any]
    data_quality_exceptions: Dict[str, Any]


class ExportLink(BaseModel):
    download_url: str
    format: str
    rows: int


class RulesResponse(BaseModel):
    rules: List[Dict[str, Any]]
