from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/revenue-leak-radar/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_upload_missing_columns():
    csv_payload = "invoice_number,amount\nINV-1,100\n"
    response = client.post(
        "/api/revenue-leak-radar/upload",
        files={"file": ("bad.csv", csv_payload, "text/csv")},
    )
    assert response.status_code == 400
    body = response.json()
    assert "missing_columns" in body or "detail" in body


def test_analyze_with_csv():
    csv_payload = """transaction_id,invoice_number,invoice_date,posting_date,customer_id,customer_name,product_id,product_name,quantity,unit_price,gross_amount,discount_amount,tax_amount,net_amount,credit_note_number,transaction_type,gl_account,currency,contract_price,expected_quantity,related_party_indicator\nT-1,INV-100,2024-01-05,2024-01-07,CUST-1,Acme,SKU-1,Widget,10,100,1000,0,0,1000,,INVOICE,4100,USD,120,10,N\nT-2,INV-101,2024-02-20,2024-02-21,CUST-1,Acme,SKU-1,Widget,8,100,800,0,0,800,,INVOICE,4100,USD,120,10,N\n"""
    response = client.post(
        "/api/revenue-leak-radar/upload",
        files={"file": ("ledger.csv", csv_payload, "text/csv")},
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    analysis = client.post(
        "/api/revenue-leak-radar/analyze",
        json={"job_id": job_id, "analysis_name": "demo"},
    )
    assert analysis.status_code == 200
    payload = analysis.json()
    assert payload["summary"]["transactions_analyzed"] >= 2


def test_review_resolution_cycle():
    response = client.get("/api/revenue-leak-radar/findings")
    assert response.status_code == 200
    findings = response.json().get("items", [])
    if not findings:
        return
    finding_id = findings[0]["finding_id"]
    patched = client.patch(
        f"/api/revenue-leak-radar/findings/{finding_id}/review",
        json={"status": "UNDER_REVIEW", "reviewer": "analyst@example.com", "comments": "Needs validation."},
    )
    assert patched.status_code == 200

    resolved = client.post(
        f"/api/revenue-leak-radar/findings/{finding_id}/resolve",
        json={"status": "RESOLVED", "reviewer": "analyst@example.com", "resolution_notes": "Reviewed and accepted."},
    )
    assert resolved.status_code == 200
