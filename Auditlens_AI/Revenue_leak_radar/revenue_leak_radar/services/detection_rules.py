from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any, Dict, List

from sklearn.ensemble import IsolationForest


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def detect_duplicate_revenue_entries(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            row.get("invoice_number"),
            row.get("customer_id"),
            row.get("invoice_date"),
            row.get("gross_amount"),
            row.get("product_id") or row.get("product_name"),
        )
        groups[key].append(row)

    findings: List[Dict[str, Any]] = []
    for group_rows in groups.values():
        if len(group_rows) > 1:
            for row in group_rows:
                findings.append(
                    {
                        "transaction_id": row.get("transaction_id"),
                        "rule_id": "duplicate_revenue_entries",
                        "reason": "Duplicate invoice/customer/date/amount pattern detected.",
                        "supporting_values": {
                            "invoice_number": row.get("invoice_number"),
                            "customer_id": row.get("customer_id"),
                            "invoice_date": row.get("invoice_date"),
                            "gross_amount": row.get("gross_amount"),
                        },
                        "potential_shortfall": 0.0,
                    }
                )
    return findings


def detect_underbilling(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for row in rows:
        expected_amount = None
        if row.get("contract_price") is not None:
            qty = _safe_float(row.get("quantity")) or 1.0
            expected_amount = _safe_float(row.get("contract_price")) * qty
        elif row.get("expected_quantity") is not None and row.get("unit_price") is not None:
            expected_amount = _safe_float(row.get("expected_quantity")) * _safe_float(row.get("unit_price"))
        if expected_amount is None:
            continue
        actual_amount = _safe_float(row.get("gross_amount")) or _safe_float(row.get("net_amount")) or 0.0
        shortfall = max(0.0, expected_amount - actual_amount)
        if shortfall > 0:
            findings.append(
                {
                    "transaction_id": row.get("transaction_id"),
                    "rule_id": "underbilling",
                    "reason": "Actual invoice amount is below the supplied contract benchmark.",
                    "supporting_values": {
                        "contract_price": row.get("contract_price"),
                        "expected_amount": expected_amount,
                        "gross_amount": row.get("gross_amount"),
                    },
                    "potential_shortfall": shortfall,
                }
            )
    return findings


def detect_unusual_discounts(rows: List[Dict[str, Any]], threshold: float = 0.30) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for row in rows:
        gross = _safe_float(row.get("gross_amount"))
        discount = _safe_float(row.get("discount_amount"))
        if gross <= 0:
            continue
        ratio = discount / gross if gross else 0.0
        if ratio >= threshold:
            findings.append(
                {
                    "transaction_id": row.get("transaction_id"),
                    "rule_id": "unusual_discounts",
                    "reason": "Discount ratio exceeds configured threshold or policy benchmark.",
                    "supporting_values": {"discount_amount": discount, "gross_amount": gross, "discount_ratio": ratio},
                    "potential_shortfall": 0.0,
                }
            )
    return findings


def detect_credit_note_anomalies(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    seen_credit_notes: Dict[str, int] = {}
    for row in rows:
        credit_note = row.get("credit_note_number")
        if credit_note:
            seen_credit_notes[credit_note] = seen_credit_notes.get(credit_note, 0) + 1

    for row in rows:
        credit_note = row.get("credit_note_number")
        if not credit_note:
            continue
        invoice_number = row.get("invoice_number")
        if seen_credit_notes.get(credit_note, 0) > 1:
            findings.append(
                {
                    "transaction_id": row.get("transaction_id"),
                    "rule_id": "credit_note_anomalies",
                    "reason": "Duplicate credit-note reference detected.",
                    "supporting_values": {"credit_note_number": credit_note, "invoice_number": invoice_number},
                    "potential_shortfall": 0.0,
                }
            )
        elif not invoice_number:
            findings.append(
                {
                    "transaction_id": row.get("transaction_id"),
                    "rule_id": "credit_note_anomalies",
                    "reason": "Credit note without an associated invoice reference.",
                    "supporting_values": {"credit_note_number": credit_note},
                    "potential_shortfall": 0.0,
                }
            )
    return findings


def detect_revenue_cutoff_risks(rows: List[Dict[str, Any]], reporting_end: str = "2024-12-31") -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for row in rows:
        invoice_date = row.get("invoice_date")
        posting_date = row.get("posting_date")
        if not invoice_date or not posting_date:
            continue
        if posting_date > reporting_end:
            findings.append(
                {
                    "transaction_id": row.get("transaction_id"),
                    "rule_id": "revenue_cutoff_risks",
                    "reason": "Posting date falls outside the configured reporting period boundary.",
                    "supporting_values": {"invoice_date": invoice_date, "posting_date": posting_date, "reporting_end": reporting_end},
                    "potential_shortfall": 0.0,
                }
            )
    return findings


def detect_missing_or_inconsistent_transactions(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    invoice_numbers = [str(row.get("invoice_number")) for row in rows if row.get("invoice_number")]
    numeric_invoices = []
    for value in invoice_numbers:
        try:
            numeric_invoices.append(int(value.replace("INV-", "")))
        except ValueError:
            continue
    if numeric_invoices:
        min_invoice = min(numeric_invoices)
        max_invoice = max(numeric_invoices)
        expected_range = set(range(min_invoice, max_invoice + 1))
        observed = set(numeric_invoices)
        gaps = sorted(expected_range - observed)
        if gaps:
            for row in rows:
                if row.get("invoice_number") and str(row.get("invoice_number")).startswith("INV-"):
                    findings.append(
                        {
                            "transaction_id": row.get("transaction_id"),
                            "rule_id": "missing_or_inconsistent_transactions",
                            "reason": "Invoice number gap detected; requires review to distinguish legitimate breaks from missing transactions.",
                            "supporting_values": {"gaps": gaps[:10]},
                            "potential_shortfall": 0.0,
                        }
                    )
                    break

    for row in rows:
        qty = _safe_float(row.get("quantity"))
        gross = _safe_float(row.get("gross_amount"))
        if qty is not None and qty < 0:
            findings.append({
                "transaction_id": row.get("transaction_id"),
                "rule_id": "missing_or_inconsistent_transactions",
                "reason": "Negative quantity found.",
                "supporting_values": {"quantity": qty},
                "potential_shortfall": 0.0,
            })
        if gross is not None and gross < 0:
            findings.append({
                "transaction_id": row.get("transaction_id"),
                "rule_id": "missing_or_inconsistent_transactions",
                "reason": "Unexpected negative gross amount.",
                "supporting_values": {"gross_amount": gross},
                "potential_shortfall": 0.0,
            })
    return findings


def detect_price_quantity_mismatches(rows: List[Dict[str, Any]], tolerance: float = 0.02) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for row in rows:
        qty = _safe_float(row.get("quantity"))
        unit_price = _safe_float(row.get("unit_price"))
        gross = _safe_float(row.get("gross_amount"))
        discount = _safe_float(row.get("discount_amount"))
        if qty is None or unit_price is None or gross is None:
            continue
        expected_base = qty * unit_price
        expected_net = max(0.0, expected_base - discount)
        if abs(expected_net - gross) > tolerance * max(1.0, abs(gross)):
            findings.append(
                {
                    "transaction_id": row.get("transaction_id"),
                    "rule_id": "price_and_quantity_mismatches",
                    "reason": "Price and quantity mismatch exceeds configured tolerance.",
                    "supporting_values": {
                        "quantity": qty,
                        "unit_price": unit_price,
                        "gross_amount": gross,
                        "discount_amount": discount,
                        "expected_net": expected_net,
                    },
                    "potential_shortfall": 0.0,
                }
            )
    return findings


def detect_statistical_anomalies(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if len(rows) < 5:
        return []
    values = []
    for row in rows:
        amount = _safe_float(row.get("net_amount")) or _safe_float(row.get("gross_amount"))
        if amount is not None:
            values.append(amount)
    if len(values) < 5:
        return []
    median_value = median(values)
    feature_matrix = [[amount, abs(amount - median_value)] for amount in values]
    model = IsolationForest(random_state=42, contamination=0.1)
    model.fit(feature_matrix)
    labels = model.predict(feature_matrix)
    anomalies = []
    for row, label in zip(rows, labels):
        if label == -1:
            anomalies.append(
                {
                    "transaction_id": row.get("transaction_id"),
                    "rule_id": "statistical_anomalies",
                    "reason": "Statistical anomaly detected by an isolation forest; not proof of fraud.",
                    "supporting_values": {"net_amount": row.get("net_amount"), "gross_amount": row.get("gross_amount")},
                    "potential_shortfall": 0.0,
                }
            )
    return anomalies
