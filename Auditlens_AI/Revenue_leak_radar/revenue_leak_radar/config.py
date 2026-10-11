import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "revenue_leak_radar.sqlite3"
UPLOAD_DIR = BASE_DIR / "uploaded_files"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = int(os.getenv("REVENUE_LEAK_MAX_FILE_SIZE", str(10 * 1024 * 1024)))
MAX_ROWS = int(os.getenv("REVENUE_LEAK_MAX_ROWS", "50000"))
REPORTING_PERIOD_END = os.getenv("REVENUE_LEAK_REPORTING_END", "2024-12-31")

REQUIRED_COLUMNS = [
    "transaction_id",
    "invoice_number",
    "invoice_date",
    "customer_id",
    "gross_amount",
    "transaction_type",
]

COLUMN_ALIASES = {
    "transaction_id": ["transaction_id", "txn_id", "id"],
    "invoice_number": ["invoice_number", "invoice", "invoice_no", "invoiceid"],
    "invoice_date": ["invoice_date", "invoice_dt", "invoice_date_value"],
    "posting_date": ["posting_date", "posted_date", "post_date"],
    "customer_id": ["customer_id", "customer", "customer_code", "cust_id"],
    "customer_name": ["customer_name", "customer_name_value", "customer_desc"],
    "product_id": ["product_id", "sku", "product", "item_id"],
    "product_name": ["product_name", "item_name", "product_desc"],
    "quantity": ["quantity", "qty"],
    "unit_price": ["unit_price", "unit_price_value"],
    "gross_amount": ["gross_amount", "amount", "gross", "invoice_amount"],
    "discount_amount": ["discount_amount", "discount", "discount_value"],
    "tax_amount": ["tax_amount", "tax", "vat_amount"],
    "net_amount": ["net_amount", "net_value", "total_amount"],
    "credit_note_number": ["credit_note_number", "credit_note", "cn_number"],
    "transaction_type": ["transaction_type", "entry_type", "txn_type"],
    "gl_account": ["gl_account", "account", "general_ledger_account"],
    "currency": ["currency", "currency_code"],
    "contract_price": ["contract_price", "expected_price", "contract_value"],
    "expected_quantity": ["expected_quantity", "expected_qty"],
    "related_party_indicator": ["related_party_indicator", "related_party", "related_party_flag"],
}

DEFAULT_RULE_WEIGHTS = {
    "duplicate_revenue_entries": 30,
    "underbilling": 35,
    "unusual_discounts": 20,
    "credit_note_anomalies": 25,
    "revenue_cutoff_risks": 15,
    "missing_or_inconsistent_transactions": 18,
    "price_and_quantity_mismatches": 16,
    "statistical_anomalies": 18,
}

RISK_THRESHOLDS = {
    "LOW": 24,
    "MEDIUM": 49,
    "HIGH": 74,
    "CRITICAL": 100,
}
