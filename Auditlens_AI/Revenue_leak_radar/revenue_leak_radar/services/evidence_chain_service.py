from __future__ import annotations

import json
import os
from urllib import parse, request


def evidence_chain_available() -> bool:
    base_url = os.getenv("REVAI_EVIDENCE_CHAIN_URL", "http://localhost:8001")
    try:
        with request.urlopen(f"{base_url}/health", timeout=3) as response:
            return response.status == 200
    except Exception:
        return False


def record_audit_event(actor: str, event_type: str, transaction_id: str | None = None, details: dict | None = None):
    base_url = os.getenv("REVAI_EVIDENCE_CHAIN_URL", "http://localhost:8001")
    payload = {
        "actor": actor,
        "event_type": event_type,
        "transaction_id": transaction_id or "",
        "details": json.dumps(details or {}, sort_keys=True),
    }
    data = parse.urlencode(payload).encode("utf-8")
    req = request.Request(f"{base_url}/events", data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with request.urlopen(req, timeout=5) as response:
            body = response.read().decode("utf-8")
            return {"recorded": True, "status": response.status, "body": body}
    except Exception as exc:
        return {"recorded": False, "error": str(exc)}
