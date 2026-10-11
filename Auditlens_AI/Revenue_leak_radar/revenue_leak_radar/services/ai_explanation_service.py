from __future__ import annotations

import os
from typing import Any, Dict


def build_deterministic_explanation(finding: Dict[str, Any]) -> Dict[str, Any]:
    rule_id = finding.get("rule_id", "unknown_rule")
    reason = finding.get("reason", "No reason supplied.")
    support = finding.get("supporting_values", {})
    explanation = (
        "This finding is based on deterministic audit logic and the supplied ledger values. "
        f"The rule {rule_id} triggered because {reason}. "
        "An auditor should verify the original invoice, contract benchmark, and supporting documents before treating the issue as a confirmed loss."
    )
    return {
        "provider": "deterministic-fallback",
        "status": "ok" if not os.getenv("GROQ_API_KEY") else "provider-configured",
        "explanation": explanation,
        "source_values": support,
    }
