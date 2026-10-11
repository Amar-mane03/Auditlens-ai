from importlib import import_module


def test_rule_modules_import():
    import_module("revenue_leak_radar.services.detection_rules")
    import_module("revenue_leak_radar.services.risk_scoring")


def test_duplicate_and_underbilling_detection():
    detection = import_module("revenue_leak_radar.services.detection_rules")

    rows = [
        {
            "transaction_id": "T-1",
            "invoice_number": "INV-100",
            "customer_id": "C-1",
            "invoice_date": "2024-01-05",
            "gross_amount": 1000,
            "discount_amount": 0,
            "net_amount": 1000,
            "quantity": 10,
            "unit_price": 100,
            "contract_price": 120,
            "transaction_type": "INVOICE",
        },
        {
            "transaction_id": "T-2",
            "invoice_number": "INV-100",
            "customer_id": "C-1",
            "invoice_date": "2024-01-05",
            "gross_amount": 1000,
            "discount_amount": 0,
            "net_amount": 1000,
            "quantity": 10,
            "unit_price": 100,
            "contract_price": 120,
            "transaction_type": "INVOICE",
        },
    ]

    duplicates = detection.detect_duplicate_revenue_entries(rows)
    underbill = detection.detect_underbilling(rows)

    assert duplicates
    assert underbill[0]["potential_shortfall"] == 200
