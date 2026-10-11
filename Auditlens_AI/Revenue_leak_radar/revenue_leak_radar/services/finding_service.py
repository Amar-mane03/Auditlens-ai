from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from revenue_leak_radar.config import DB_PATH


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FindingService:
    def __init__(self, db_path: str = str(DB_PATH)):
        self.db_path = db_path
        self.initialize_database()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize_database(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS findings (
                    finding_id TEXT PRIMARY KEY,
                    transaction_id TEXT,
                    invoice_number TEXT,
                    customer_id TEXT,
                    source_file TEXT,
                    source_row INTEGER,
                    status TEXT DEFAULT 'OPEN',
                    risk_score INTEGER,
                    risk_level TEXT,
                    detected_rules TEXT,
                    reasons TEXT,
                    supporting_values TEXT,
                    potential_shortfall REAL DEFAULT 0,
                    requires_manual_review INTEGER DEFAULT 1,
                    created_at TEXT,
                    reviewed_by TEXT,
                    reviewed_at TEXT,
                    review_comments TEXT,
                    resolution_notes TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    filename TEXT,
                    rows_json TEXT,
                    summary_json TEXT,
                    status TEXT,
                    created_at TEXT,
                    analysis_id TEXT
                )
                """
            )
            conn.commit()

    def create_finding(self, record: Dict[str, Any]) -> Dict[str, Any]:
        finding_id = record.get("finding_id") or uuid.uuid4().hex
        safe_support = self._sanitize_jsonable(record.get("supporting_values", {}))
        safe_reasons = self._sanitize_jsonable(record.get("reasons", []))
        safe_rules = self._sanitize_jsonable(record.get("detected_rules", []))
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO findings (
                    finding_id, transaction_id, invoice_number, customer_id,
                    source_file, source_row, status, risk_score, risk_level,
                    detected_rules, reasons, supporting_values, potential_shortfall,
                    requires_manual_review, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    finding_id,
                    record.get("transaction_id"),
                    record.get("invoice_number"),
                    record.get("customer_id"),
                    record.get("source_file"),
                    record.get("source_row"),
                    record.get("status", "OPEN"),
                    record.get("risk_score"),
                    record.get("risk_level"),
                    json.dumps(safe_rules, ensure_ascii=False, allow_nan=False),
                    json.dumps(safe_reasons, ensure_ascii=False, allow_nan=False),
                    json.dumps(safe_support, ensure_ascii=False, allow_nan=False),
                    record.get("potential_shortfall", 0.0),
                    int(bool(record.get("requires_manual_review", True))),
                    record.get("created_at", utc_now()),
                ),
            )
            conn.commit()
        record["finding_id"] = finding_id
        return record

    def create_job(self, filename: str, rows: List[Dict[str, Any]], summary: Dict[str, Any]) -> str:
        job_id = uuid.uuid4().hex
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO jobs (job_id, filename, rows_json, summary_json, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (job_id, filename, json.dumps(rows, ensure_ascii=False), json.dumps(summary, ensure_ascii=False), "uploaded", utc_now()),
            )
            conn.commit()
        return job_id

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return {
            "job_id": row["job_id"],
            "filename": row["filename"],
            "rows": json.loads(row["rows_json"]),
            "summary": json.loads(row["summary_json"]),
            "status": row["status"],
            "created_at": row["created_at"],
            "analysis_id": row["analysis_id"],
        }

    def update_job_analysis(self, job_id: str, analysis_id: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE jobs SET status = 'analyzed', analysis_id = ? WHERE job_id = ?", (analysis_id, job_id))
            conn.commit()

    def list_findings(self, page: int = 1, limit: int = 20, status: Optional[str] = None, customer: Optional[str] = None, risk_level: Optional[str] = None, from_date: Optional[str] = None, to_date: Optional[str] = None) -> Dict[str, Any]:
        offset = (page - 1) * limit
        query = "SELECT * FROM findings WHERE 1=1"
        params: List[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if customer:
            query += " AND customer_id = ?"
            params.append(customer)
        if risk_level:
            query += " AND risk_level = ?"
            params.append(risk_level)
        if from_date:
            query += " AND created_at >= ?"
            params.append(from_date)
        if to_date:
            query += " AND created_at <= ?"
            params.append(to_date)
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) as total FROM findings WHERE 1=1" + (" AND status = ?" if status else "") + (" AND customer_id = ?" if customer else "") + (" AND risk_level = ?" if risk_level else "") + (" AND created_at >= ?" if from_date else "") + (" AND created_at <= ?" if to_date else ""),
                tuple(params[:-2]) if params else tuple(),
            ).fetchone()

        items = [self._to_dict(row) for row in rows]
        return {"items": items, "page": page, "limit": limit, "total": total["total"] if total else 0}

    def get_finding(self, finding_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM findings WHERE finding_id = ?", (finding_id,)).fetchone()
        if row is None:
            return None
        return self._to_dict(row)

    def get_transactions(self, transaction_id: str) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM findings WHERE transaction_id = ? ORDER BY created_at DESC", (transaction_id,)).fetchall()
        return [self._to_dict(row) for row in rows]

    def patch_review(self, finding_id: str, status: str, reviewer: str, comments: Optional[str]) -> Dict[str, Any]:
        with self._connect() as conn:
            conn.execute(
                "UPDATE findings SET status = ?, reviewed_by = ?, reviewed_at = ?, review_comments = ? WHERE finding_id = ?",
                (status, reviewer, utc_now(), comments or "", finding_id),
            )
            conn.commit()
        return self.get_finding(finding_id)

    def resolve_finding(self, finding_id: str, status: str, reviewer: str, resolution_notes: Optional[str]) -> Dict[str, Any]:
        with self._connect() as conn:
            conn.execute(
                "UPDATE findings SET status = ?, reviewed_by = ?, reviewed_at = ?, resolution_notes = ? WHERE finding_id = ?",
                (status, reviewer, utc_now(), resolution_notes or "", finding_id),
            )
            conn.commit()
        return self.get_finding(finding_id)

    def _sanitize_jsonable(self, value):
        if isinstance(value, dict):
            return {str(k): self._sanitize_jsonable(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._sanitize_jsonable(v) for v in value]
        if isinstance(value, float):
            if value != value or value in (float("inf"), float("-inf")):
                return None
            return value
        return value

    def _to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "finding_id": row["finding_id"],
            "transaction_id": row["transaction_id"],
            "invoice_number": row["invoice_number"],
            "customer_id": row["customer_id"],
            "source_file": row["source_file"],
            "source_row": row["source_row"],
            "status": row["status"],
            "risk_score": row["risk_score"],
            "risk_level": row["risk_level"],
            "detected_rules": self._sanitize_jsonable(json.loads(row["detected_rules"] or "[]")),
            "reasons": self._sanitize_jsonable(json.loads(row["reasons"] or "[]")),
            "supporting_values": self._sanitize_jsonable(json.loads(row["supporting_values"] or "{}")),
            "potential_shortfall": row["potential_shortfall"],
            "requires_manual_review": bool(row["requires_manual_review"]),
            "created_at": row["created_at"],
            "reviewed_by": row["reviewed_by"],
            "reviewed_at": row["reviewed_at"],
            "review_comments": row["review_comments"],
            "resolution_notes": row["resolution_notes"],
        }
