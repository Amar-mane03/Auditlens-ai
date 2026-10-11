from __future__ import annotations

from typing import Any, Dict, Iterable, List

from revenue_leak_radar.config import DEFAULT_RULE_WEIGHTS, RISK_THRESHOLDS


def _risk_level(score: int) -> str:
    if score <= RISK_THRESHOLDS["LOW"]:
        return "LOW"
    if score <= RISK_THRESHOLDS["MEDIUM"]:
        return "MEDIUM"
    if score <= RISK_THRESHOLDS["HIGH"]:
        return "HIGH"
    return "CRITICAL"


def score_transaction(flag_rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    unique_rules: set[str] = set()
    reasons: List[str] = []
    supporting_values: Dict[str, Any] = {}
    potential_shortfall = 0.0

    for flag in flag_rows:
        rule_id = str(flag.get("rule_id") or "general")
        if rule_id not in unique_rules:
            unique_rules.add(rule_id)
        reasons.append(flag.get("reason", "Review required."))
        supporting_values.setdefault(rule_id, flag.get("supporting_values", {}))
        shortfall = float(flag.get("potential_shortfall") or 0.0)
        if shortfall > potential_shortfall:
            potential_shortfall = shortfall

    total_score = sum(DEFAULT_RULE_WEIGHTS.get(rule_id, 10) for rule_id in unique_rules)
    if potential_shortfall > 0:
        total_score = min(100, total_score + min(15, int(potential_shortfall / 100)))

    score = max(0, min(100, int(total_score)))
    level = _risk_level(score)

    return {
        "risk_score": score,
        "risk_level": level,
        "detected_rules": sorted(unique_rules),
        "reasons": reasons,
        "supporting_values": supporting_values,
        "potential_shortfall": potential_shortfall,
        "requires_manual_review": score >= 25 or potential_shortfall > 0,
    }
