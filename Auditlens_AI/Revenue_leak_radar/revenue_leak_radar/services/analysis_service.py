from __future__ import annotations

import json
import math
import uuid
from collections import Counter, defaultdict
from typing import Any, Dict, List

from revenue_leak_radar.config import DEFAULT_RULE_WEIGHTS, REPORTING_PERIOD_END
from revenue_leak_radar.services.data_quality import prepare_ledger_rows, summarize_ledger
from revenue_leak_radar.services.detection_rules import (
    detect_credit_note_anomalies,
    detect_duplicate_revenue_entries,
    detect_missing_or_inconsistent_transactions,
    detect_price_quantity_mismatches,
    detect_revenue_cutoff_risks,
    detect_statistical_anomalies,
    detect_underbilling,
    detect_unusual_discounts,
)
from revenue_leak_radar.services.evidence_chain_service import evidence_chain_available, record_audit_event
from revenue_leak_radar.services.finding_service import FindingService
from revenue_leak_radar.services.risk_scoring import score_transaction


def _sanitize_jsonable(value):
    if isinstance(value, dict):
        return {str(key): _sanitize_jsonable(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_sanitize_jsonable(val) for val in value]
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    return value


class RevenueLeakAnalysisService:
    def __init__(self):
        self.finding_service = FindingService()

    def upload_ledger(self, file) -> Dict[str, Any]:
        rows, quality_summary = prepare_ledger_rows(file)
        job_id = self.finding_service.create_job(file.filename or "upload", rows, quality_summary)
        return {
            "job_id": job_id,
            "filename": file.filename,
            "rows_loaded": len(rows),
            "summary": quality_summary,
        }

    def analyze_job(self, job_id: str) -> Dict[str, Any]:
        job = self.finding_service.get_job(job_id)
        if not job:
            raise ValueError("Job not found")
        rows = job["rows"]
        all_flags = []
        by_transaction: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        detections = [
            detect_duplicate_revenue_entries(rows),
            detect_underbilling(rows),
            detect_unusual_discounts(rows),
            detect_credit_note_anomalies(rows),
            detect_revenue_cutoff_risks(rows, REPORTING_PERIOD_END),
            detect_missing_or_inconsistent_transactions(rows),
            detect_price_quantity_mismatches(rows),
            detect_statistical_anomalies(rows),
        ]

        for bucket in detections:
            for flag in bucket:
                all_flags.append(flag)
                tid = flag.get("transaction_id")
                if tid:
                    by_transaction[tid].append(flag)

        findings: List[Dict[str, Any]] = []
        for row in rows:
            tid = row.get("transaction_id")
            flags = by_transaction.get(tid, [])
            if not flags:
                continue
            score = score_transaction(flags)
            created = {
                "finding_id": uuid.uuid4().hex,
                "transaction_id": tid,
                "invoice_number": row.get("invoice_number"),
                "customer_id": row.get("customer_id"),
                "source_file": row.get("source_file"),
                "source_row": row.get("source_row"),
                "status": "OPEN",
                "risk_score": score["risk_score"],
                "risk_level": score["risk_level"],
                "detected_rules": score["detected_rules"],
                "reasons": score["reasons"],
                "supporting_values": score["supporting_values"],
                "potential_shortfall": score["potential_shortfall"],
                "requires_manual_review": score["requires_manual_review"],
                "created_at": row.get("source_row") and row.get("invoice_date") or "2024-01-01T00:00:00+00:00",
            }
            created["created_at"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
            persisted = self.finding_service.create_finding(created)
            findings.append(persisted)

            if evidence_chain_available():
                record_audit_event(
                    actor="system",
                    event_type="FINDING_CREATED",
                    transaction_id=tid,
                    details={
                        "finding_id": persisted["finding_id"],
                        "rule_ids": score["detected_rules"],
                        "risk_score": score["risk_score"],
                        "source_file": row.get("source_file"),
                        "source_row": row.get("source_row"),
                    },
                )

        summary = self.build_summary(rows, findings)
        self.finding_service.update_job_analysis(job_id, uuid.uuid4().hex)
        return {
            "job_id": job_id,
            "summary": _sanitize_jsonable(summary),
            "findings": _sanitize_jsonable(findings),
            "count": len(findings),
        }

    def build_summary(self, rows: List[Dict[str, Any]], findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        total_eligible_revenue = sum(float(row.get("gross_amount") or 0) for row in rows)
        flagged_rows = [row for row in rows if row.get("transaction_id") in {f.get("transaction_id") for f in findings}]
        unique_invoices = {row.get("invoice_number") for row in flagged_rows if row.get("invoice_number")}
        total_shortfall = sum(float(f.get("potential_shortfall") or 0) for f in findings)
        flagged_gross = sum(float(row.get("gross_amount") or 0) for row in flagged_rows)
        flagged_credit_note = sum(float(row.get("gross_amount") or 0) for row in flagged_rows if row.get("credit_note_number"))
        high_critical = sum(1 for f in findings if f.get("risk_level") in {"HIGH", "CRITICAL"})

        customer_counts = Counter(row.get("customer_id") for row in flagged_rows if row.get("customer_id"))
        product_counts = Counter(row.get("product_id") or row.get("product_name") for row in flagged_rows if row.get("product_id") or row.get("product_name"))
        gl_counts = Counter(row.get("gl_account") for row in flagged_rows if row.get("gl_account"))

        return {
            "total_eligible_revenue": round(total_eligible_revenue, 2),
            "transactions_analyzed": len(rows),
            "flagged_transactions": len(findings),
            "unique_affected_invoices": len(unique_invoices),
            "potential_shortfall": round(total_shortfall, 2),
            "flagged_gross_transaction_value": round(flagged_gross, 2),
            "flagged_credit_note_value": round(flagged_credit_note, 2),
            "high_and_critical_risk_count": high_critical,
            "leakage_indicators": {
                "customer": dict(customer_counts),
                "product": dict(product_counts),
                "gl_account": dict(gl_counts),
            },
            "data_quality_exceptions": summarize_ledger(rows),
        }

    def get_summary(self) -> Dict[str, Any]:
        all_findings = self.finding_service.list_findings(page=1, limit=1000)
        rows = []
        for item in all_findings["items"]:
            rows.append({
                "transaction_id": item.get("transaction_id"),
                "gross_amount": item.get("supporting_values", {}).get("gross_amount"),
                "credit_note_number": item.get("supporting_values", {}).get("credit_note_number"),
                "customer_id": item.get("supporting_values", {}).get("customer_id"),
                "product_id": item.get("supporting_values", {}).get("product_id"),
                "gl_account": item.get("supporting_values", {}).get("gl_account"),
            })
        return _sanitize_jsonable(self.build_summary(rows, all_findings["items"]))

    def explain_finding(self, finding_id: str):
        from revenue_leak_radar.services.ai_explanation_service import build_deterministic_explanation
        finding = self.finding_service.get_finding(finding_id)
        if not finding:
            raise ValueError("Finding not found")
        explanation = build_deterministic_explanation(finding)
        return {"finding_id": finding_id, **explanation}


def create_service() -> RevenueLeakAnalysisService:
    return RevenueLeakAnalysisService()
