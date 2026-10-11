from __future__ import annotations

import io
import json
import math
from collections import Counter
from typing import Any, Dict, List, Tuple

import pandas as pd
from fastapi import UploadFile

from revenue_leak_radar.config import COLUMN_ALIASES, MAX_FILE_SIZE, MAX_ROWS, REQUIRED_COLUMNS


def _normalize_column_name(name: str) -> str:
    cleaned = str(name or "").strip().lower().replace("-", "_").replace(" ", "_")
    return cleaned


def _find_alias(column_name: str, canonical: str) -> str:
    normalized = _normalize_column_name(column_name)
    alias_values = {alias.lower().replace("-", "_").replace(" ", "_"): alias for alias in COLUMN_ALIASES.get(canonical, [canonical])}
    if normalized in alias_values:
        return alias_values[normalized]
    return column_name


def normalize_columns(columns: List[str]) -> Tuple[Dict[str, str], List[str]]:
    mapping: Dict[str, str] = {}
    seen: set[str] = set()
    missing: List[str] = []

    for column in columns:
        raw_name = str(column or "").strip()
        if not raw_name:
            continue
        normalized = _normalize_column_name(raw_name)
        matched = None
        for canonical in REQUIRED_COLUMNS + [value for values in COLUMN_ALIASES.values() for value in values]:
            aliases = {alias.lower().replace("-", "_").replace(" ", "_"): alias for alias in COLUMN_ALIASES.get(canonical, [canonical])}
            if normalized in aliases:
                matched = canonical
                break
        if matched is None:
            match_name = normalized
            if match_name not in seen:
                mapping[raw_name] = normalized
                seen.add(normalized)
            continue

        target_name = matched
        if target_name not in seen:
            mapping[raw_name] = target_name
            seen.add(target_name)
        else:
            mapping[raw_name] = f"{target_name}_{len(seen)}"

    for required in REQUIRED_COLUMNS:
        if required not in {value for value in mapping.values()}:
            missing.append(required)

    return mapping, missing


def parse_numeric(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        result = float(value)
        if math.isnan(result) or math.isinf(result):
            return None
        return result
    text = str(value).strip().replace(",", "")
    if text.lower() in {"", "na", "n/a", "null", "none", "nan", "inf", "-inf", "+inf"}:
        return None
    try:
        result = float(text)
    except ValueError:
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def parse_date(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    if text in {"", "NA", "N/A", "null", "None"}:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return pd.to_datetime(text, format=fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    try:
        return pd.to_datetime(text).strftime("%Y-%m-%d")
    except Exception:
        return None


def normalize_row(raw_row: Dict[str, Any]) -> Dict[str, Any]:
    normalized = {}
    for key, value in raw_row.items():
        if key is None:
            continue
        normalized_key = _normalize_column_name(str(key))
        normalized[normalized_key] = value

    for canonical in REQUIRED_COLUMNS:
        if canonical not in normalized:
            normalized[canonical] = None

    numeric_fields = [
        "quantity",
        "unit_price",
        "gross_amount",
        "discount_amount",
        "tax_amount",
        "net_amount",
        "contract_price",
        "expected_quantity",
    ]
    for field in numeric_fields:
        if field in normalized:
            normalized[field] = parse_numeric(normalized[field])

    for field in ["invoice_date", "posting_date"]:
        if field in normalized:
            normalized[field] = parse_date(normalized[field])

    return normalized


def prepare_ledger_rows(file: UploadFile) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    file_bytes = file.file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise ValueError(f"File exceeds the {MAX_FILE_SIZE} byte limit.")

    file_name = (file.filename or "upload").lower()
    buffer = io.BytesIO(file_bytes)

    if file_name.endswith(".csv"):
        df = pd.read_csv(buffer, dtype=str, keep_default_na=True)
    elif file_name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(buffer, dtype=str)
    else:
        raise ValueError("Unsupported file type. Use CSV or Excel (.xlsx/.xls).")

    if df.empty:
        raise ValueError("Uploaded ledger is empty.")
    if len(df) > MAX_ROWS:
        raise ValueError(f"Uploaded ledger exceeds the {MAX_ROWS} row limit.")

    mapping, missing = normalize_columns(list(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    renamed = df.rename(columns=mapping)
    rows: List[Dict[str, Any]] = []
    missing_values: Dict[str, int] = {key: 0 for key in REQUIRED_COLUMNS}
    duplicate_invoice_numbers: Dict[str, int] = {}

    for row_index, raw_row in renamed.iterrows():
        row = normalize_row(raw_row.to_dict())
        row["source_row"] = int(row_index + 2)
        row["source_file"] = file.filename or "upload"
        rows.append(row)

        for column in REQUIRED_COLUMNS:
            if row.get(column) in (None, "", pd.NaT):
                missing_values[column] = missing_values.get(column, 0) + 1

        invoice_number = row.get("invoice_number")
        if invoice_number:
            duplicate_invoice_numbers[invoice_number] = duplicate_invoice_numbers.get(invoice_number, 0) + 1

    duplicate_invoice_list = [key for key, count in duplicate_invoice_numbers.items() if count > 1]

    quality_summary = {
        "total_rows": len(rows),
        "missing_columns": missing,
        "missing_values": missing_values,
        "duplicate_invoice_numbers": duplicate_invoice_list,
        "duplicate_rows": sum(1 for item in rows if item.get("invoice_number") and list(row["invoice_number"] for row in rows).count(item["invoice_number"]) > 1),
        "required_columns_present": True,
        "detection_notes": [
            "Rows are kept for review when invalid values are present; they are not silently dropped.",
            "Duplicate invoice numbers are reported separately from confirmed fraud.",
        ],
    }

    return rows, quality_summary


def summarize_ledger(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = {
        "transactions_analyzed": len(rows),
        "missing_values": {},
        "duplicate_invoice_numbers": [],
        "invalid_dates": 0,
        "negative_amounts": 0,
        "negative_quantities": 0,
    }
    for key in ["invoice_number", "customer_id", "gross_amount", "transaction_type"]:
        summary["missing_values"][key] = sum(1 for row in rows if row.get(key) in (None, ""))
    invoice_counts = Counter(row.get("invoice_number") for row in rows if row.get("invoice_number"))
    summary["duplicate_invoice_numbers"] = sorted([value for value, count in invoice_counts.items() if count > 1])
    summary["invalid_dates"] = sum(1 for row in rows if row.get("invoice_date") is None)
    summary["negative_amounts"] = sum(1 for row in rows if (row.get("gross_amount") or 0) < 0)
    summary["negative_quantities"] = sum(1 for row in rows if (row.get("quantity") or 0) < 0)
    return summary
