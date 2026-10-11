"""Flask API for transaction audit analysis."""

import base64
import io
import logging
from pathlib import Path
from uuid import uuid4

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

logger = logging.getLogger("audit_engine")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

ENGINE_FOLDER = Path(__file__).resolve().parent
UPLOAD_FOLDER = ENGINE_FOLDER / "uploads"
REPORT_FOLDER = ENGINE_FOLDER / "reports"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
REPORT_FOLDER.mkdir(parents=True, exist_ok=True)

LATEST_GRAPHS = None

try:
    from flask_cors import CORS  # type: ignore
except ImportError:  # pragma: no cover - fallback for environments without flask-cors
    class CORS:
        def __init__(self, *args, **kwargs):
            pass

        def init_app(self, *args, **kwargs):
            pass


CORS(app, origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"])

ALLOWED_EXTENSIONS = {".csv", ".xlsx"}
FRONTEND_ORIGINS = {"http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"}


@app.after_request
def add_development_cors_headers(response):
    origin = request.headers.get("Origin")
    if origin in FRONTEND_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def _json_value(value):
    """Convert pandas and NumPy scalar values to JSON-safe values."""
    if pd.isna(value):
        return None
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    return value


def _safe_float(value):
    """Safely parse numeric floats, handling strings, currencies, and commas."""
    if pd.isna(value):
        return None
    try:
        val_str = str(value).replace("$", "").replace("₹", "").replace(",", "").strip()
        return float(val_str)
    except (ValueError, TypeError):
        return None


def detect_fraud_rules(row, history_stats=None):
    flags = []
    risk_score = 0
    raw_amount = row.get("amount")
    amount = _safe_float(raw_amount)
    if amount is None or pd.isna(raw_amount):
        flags.append("Missing or invalid transaction amount")
        risk_score += 25
        amount = 0.0
    elif amount <= 0 or amount > 1_000_000:
        flags.append("Unusual transaction amount")
        risk_score += 15

    frequency = _safe_float(row.get("frequency"))
    if frequency is not None and frequency > 50:
        flags.append("Too many transactions in short period")
        risk_score += 10

    timestamp = row.get("timestamp")
    if pd.notna(timestamp) and str(timestamp).strip() not in {"", "nan"}:
        try:
            ts = pd.to_datetime(timestamp, errors="raise")
            if (ts.hour < 6 or ts.hour >= 23) and (":" in str(timestamp) or ts.hour != 0):
                flags.append("Transaction at unusual time")
                risk_score += 10
            if ts.month == 3 and ts.day >= 30:
                flags.append("Potential period-end revenue manipulation")
                risk_score += 15
            if ts.dayofweek >= 5 and "Weekend transaction" not in flags:
                flags.append("Weekend transaction")
                risk_score += 10
        except (TypeError, ValueError):
            flags.append("Invalid timestamp")
            risk_score += 5
    elif "timestamp" in row or "transaction_date" in row:
        flags.append("Missing transaction date")
        risk_score += 10

    # Dataset explicit weekend transaction check
    weekend_tx = str(row.get("weekend_transaction", "")).strip().lower()
    if weekend_tx in {"yes", "true", "1"} and "Weekend transaction" not in flags:
        flags.append("Weekend transaction")
        risk_score += 10

    transaction_type = str(row.get("type", "")).strip().lower()
    if transaction_type in {"refund", "reversal", "adjustment"}:
        flags.append(f"Suspicious transaction type: {row.get('type')}")
        risk_score += 10

    invoice_amount = _safe_float(row.get("invoice_amount"))
    if (
        "invoice_amount" in row
        and "amount" in row
        and invoice_amount is not None
        and amount is not None
        and round(invoice_amount, 2) != round(amount, 2)
    ):
        flags.append("Invoice amount mismatch")
        risk_score += 10

    tax_amount = _safe_float(row.get("tax_amount"))
    if invoice_amount is not None and tax_amount is not None:
        expected_tax = round(invoice_amount * 0.18, 2)
        if abs(tax_amount - expected_tax) > 5:
            flags.append("Tax calculation anomaly")
            risk_score += 10

    discount = _safe_float(row.get("discount"))
    if discount is not None and invoice_amount is not None:
        if discount > 0.5 * invoice_amount:
            flags.append("Excessive discount")
            risk_score += 10

    if (
        transaction_type == "refund"
        and str(row.get("status", "")).strip().lower() == "completed"
    ):
        flags.append("Abnormal refund pattern")
        risk_score += 10

    # Duplicate invoice check from column or history
    dup_flagged = False
    dup_col = str(row.get("duplicate_invoice", "")).strip().lower()
    if dup_col in {"yes", "true", "1"}:
        flags.append("Duplicate invoice")
        risk_score += 15
        dup_flagged = True

    invoice_number = row.get("invoice_number")
    if history_stats is not None and pd.notna(invoice_number) and str(invoice_number).strip() not in {"", "nan"}:
        seen_invoices = history_stats.setdefault("seen_invoices", set())
        if invoice_number in seen_invoices and not dup_flagged:
            flags.append("Duplicate invoice")
            risk_score += 15
        seen_invoices.add(invoice_number)
    elif ("invoice_number" in row or "invoice_no" in row) and (pd.isna(invoice_number) or str(invoice_number).strip() in {"", "nan"}):
        flags.append("Missing invoice number")
        risk_score += 10

    # Workflow approval anomalies
    appr_status = str(row.get("approval_status", "")).strip().lower()
    if appr_status in {"rejected", "declined"}:
        flags.append("Transaction rejected by approval workflow")
        risk_score += 20
    elif "approval_status" in row and (pd.isna(row.get("approval_status")) or appr_status == ""):
        flags.append("Missing approval status")
        risk_score += 10

    # Historical prior flags
    prior_flags = _safe_float(row.get("prior_flagged_transactions"))
    if prior_flags is not None and prior_flags > 0:
        flags.append(f"Prior flagged history ({int(prior_flags)} previous flags)")
        risk_score += 15

    # New vendor scrutiny (< 90 days)
    vendor_age = _safe_float(row.get("vendor_age_days"))
    if vendor_age is not None and vendor_age < 90:
        flags.append(f"New vendor ({int(vendor_age)} days active)")
        risk_score += 10

    # Missing Vendor ID
    if "vendor_id" in row:
        vend_val = row.get("vendor_id")
        if pd.isna(vend_val) or str(vend_val).strip() in {"", "nan"}:
            flags.append("Missing Vendor ID")
            risk_score += 10

    # Round number anomaly
    if amount > 0 and (amount % 100_000 == 0):
        flags.append("Round-number anomaly")
        risk_score += 5

    # Fraud label anomaly
    fraud_label = _safe_float(row.get("fraud_label"))
    if fraud_label == 1.0:
        flags.append("High-confidence fraud signal")
        risk_score += 20

    if risk_score >= 80:
        classification = "Critical"
    elif risk_score >= 60:
        classification = "High"
    elif risk_score >= 30:
        classification = "Medium"
    else:
        classification = "Low"

    return flags, risk_score, classification


def analyze_transactions(file_path):
    file_path = Path(file_path)
    extension = file_path.suffix.lower()
    if extension == ".csv":
        df = pd.read_csv(file_path)
    elif extension == ".xlsx":
        df = pd.read_excel(file_path)
    else:
        raise ValueError("Unsupported file format. Use CSV or XLSX.")

    # Normalize column names: strip whitespace and lowercase for reliable lookup
    col_map = {c: str(c).strip().lower() for c in df.columns}
    df.rename(columns=col_map, inplace=True)

    # Intelligent alias mapping for diverse and real-world datasets
    column_aliases = {
        "amount": [
            "invoice_amount", "invoice_amt", "txn_amount", "transaction_amount",
            "amt", "total_amount", "total", "value", "price", "payment_amount", "net_amount"
        ],
        "transaction_id": ["txn_id", "tx_id", "id", "trans_id", "transaction_no"],
        "invoice_number": ["invoice_no", "inv_no", "inv_num", "invoice_num", "invoice_id"],
        "timestamp": ["transaction_date", "date", "txn_date", "datetime", "trans_date"],
        "vendor_id": ["vendor", "vend_id", "supplier_id", "vendor_code"],
        "customer_id": ["customer", "cust_id", "client_id"],
        "status": ["approval_status", "state"],
        "type": ["transaction_type", "txn_type", "payment_method"],
    }

    for canonical, aliases in column_aliases.items():
        if canonical not in df.columns:
            for alias in aliases:
                if alias in df.columns:
                    df[canonical] = df[alias]
                    break

    if "amount" not in df.columns:
        raise ValueError("Uploaded file must include an 'amount' column.")

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    if df["amount"].isna().all():
        raise ValueError("The 'amount' column must contain valid numeric values.")

    history_stats = {"seen_invoices": set()}
    results = []
    for _, row in df.iterrows():
        flags, score, classification = detect_fraud_rules(row, history_stats)
        results.append(
            {
                "transaction_id": _json_value(row.get("transaction_id", "N/A")),
                "amount": _json_value(row["amount"]) if pd.notna(row.get("amount")) else 0.0,
                "customer_id": _json_value(row.get("customer_id", "N/A")),
                "vendor_id": _json_value(row.get("vendor_id", "N/A")),
                "risk_score": score,
                "classification": classification,
                "flags": flags,
                "supporting_evidence": f"Row data: {row.to_dict()}",
                "related_transactions": "Check duplicates / vendor history",
                "ai_explanation": "Flagged based on rule-based anomaly checks",
                "auditor_decision": "Pending",
            }
        )

    report_path = REPORT_FOLDER / f"audit_report_{uuid4().hex}.xlsx"
    export_rows = []
    for r in results:
        row_copy = dict(r)
        if isinstance(row_copy.get("flags"), list):
            row_copy["flags"] = ", ".join(row_copy["flags"])
        export_rows.append(row_copy)
    pd.DataFrame(export_rows).to_excel(report_path, index=False)

    risk_distribution = {
        level: sum(result["classification"] == level for result in results)
        for level in ("Low", "Medium", "High", "Critical")
    }
    dashboard = {
        "total_transactions": len(df),
        "total_revenue": float(df["amount"].fillna(0.0).sum()),
        "transactions_analyzed": len(results),
        "high_risk": risk_distribution["High"] + risk_distribution["Critical"],
        "potential_leakage": sum(
            "Unusual transaction amount" in result["flags"] or "Missing or invalid transaction amount" in result["flags"]
            for result in results
        ),
        "duplicates": sum(
            "Duplicate invoice" in result["flags"] for result in results
        ),
        "revenue_recognition_issues": sum(
            "Round-number anomaly" in result["flags"] or "Potential period-end revenue manipulation" in result["flags"]
            for result in results
        ),
        "open_findings": sum(
            result["classification"] != "Low" for result in results
        ),
        "risk_distribution": risk_distribution,
    }

    report_filename = report_path.name
    return {
        "dashboard": dashboard,
        "investigation": results,
        "report_path": str(report_path),
        "report_filename": report_filename,
        "report_url": f"/reports/{report_filename}",
    }


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/reports/<path:filename>", methods=["GET"])
def download_report(filename):
    safe_filename = secure_filename(filename)
    file_to_send = REPORT_FOLDER / safe_filename
    if not file_to_send.is_file():
        return jsonify({"error": "Report file not found"}), 404
    return send_from_directory(REPORT_FOLDER, safe_filename, as_attachment=True)


@app.route("/sample-data", methods=["GET"])
def sample_data():
    sample_csv_path = ENGINE_FOLDER / "sample_transactions.csv"
    if not sample_csv_path.is_file():
        sample_csv_path.write_text(
            "transaction_id,amount,customer_id,vendor_id,type,status,invoice_amount,tax_amount,discount,invoice_number,timestamp\n"
            "TXN-1001,12000.00,CUST-01,VEND-01,sale,completed,12000.00,2160.00,500.00,INV-1001,2026-03-15 11:20:00\n"
            "TXN-1002,100000.00,CUST-02,VEND-02,sale,completed,100000.00,18000.00,0.00,INV-1002,2026-03-31 23:45:00\n"
            "TXN-1003,5000.00,CUST-03,VEND-03,refund,completed,5000.00,900.00,0.00,INV-1003,2026-03-18 14:10:00\n"
            "TXN-1004,25000.00,CUST-01,VEND-01,sale,completed,30000.00,4500.00,16000.00,INV-1001,2026-03-20 03:30:00\n"
            "TXN-1005,-500.00,CUST-04,VEND-04,adjustment,completed,-500.00,0.00,0.00,INV-1005,2026-03-22 09:15:00\n",
            encoding="utf-8",
        )
    result = analyze_transactions(sample_csv_path)
    return jsonify(
        {
            "message": "Sample audit loaded successfully",
            **result,
        }
    )


@app.route("/upload", methods=["POST"])
def upload_file():
    uploaded_files = request.files.getlist("files")
    if not uploaded_files:
        uploaded_files = request.files.getlist("file")
    if not uploaded_files:
        return jsonify({"error": "No file uploaded"}), 400

    if any(not uploaded_file.filename for uploaded_file in uploaded_files):
        return jsonify({"error": "Empty filename"}), 400

    invalid_names = [
        uploaded_file.filename
        for uploaded_file in uploaded_files
        if not allowed_file(uploaded_file.filename)
    ]
    if invalid_names:
        return jsonify(
            {"error": f"Invalid file type: {', '.join(invalid_names)}"}
        ), 400

    results = []
    for uploaded_file in uploaded_files:
        filename = secure_filename(uploaded_file.filename)
        if not filename:
            return jsonify({"error": "Invalid filename"}), 400

        saved_path = UPLOAD_FOLDER / f"{uuid4().hex}_{filename}"
        uploaded_file.save(saved_path)
        try:
            results.append(
                {
                    "filename": filename,
                    **analyze_transactions(saved_path),
                }
            )
        except (ValueError, TypeError, pd.errors.ParserError, UnicodeDecodeError) as error:
            saved_path.unlink(missing_ok=True)
            return jsonify({"error": f"Error analyzing {filename}: {error}"}), 400

    if len(results) == 1:
        return jsonify(
            {
                "message": "Audit completed successfully",
                **{
                    key: value
                    for key, value in results[0].items()
                    if key != "filename"
                },
            }
        )

    combined_dashboard = {
        "total_transactions": sum(
            result["dashboard"]["total_transactions"] for result in results
        ),
        "total_revenue": sum(
            result["dashboard"]["total_revenue"] for result in results
        ),
        "transactions_analyzed": sum(
            result["dashboard"]["transactions_analyzed"] for result in results
        ),
        "high_risk": sum(
            result["dashboard"]["high_risk"] for result in results
        ),
        "potential_leakage": sum(
            result["dashboard"]["potential_leakage"] for result in results
        ),
        "duplicates": sum(result["dashboard"]["duplicates"] for result in results),
        "revenue_recognition_issues": sum(
            result["dashboard"]["revenue_recognition_issues"] for result in results
        ),
        "open_findings": sum(
            result["dashboard"]["open_findings"] for result in results
        ),
        "risk_distribution": {
            level: sum(
                result["dashboard"]["risk_distribution"][level]
                for result in results
            )
            for level in ("Low", "Medium", "High", "Critical")
        },
    }
    return jsonify(
        {
            "message": "Audit completed successfully",
            "dashboard": combined_dashboard,
            "investigation": [
                item for result in results for item in result["investigation"]
            ],
            "file_results": results,
        }
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
