"""Unit and integration tests for auditlens_backend."""

import json
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

import auditlens_backend as alb


class AuditLensBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        alb.settings.api_tokens_json = json.dumps({
            "test-token": {"identity": "test@auditlens.ai", "role": "admin"}
        })
        alb.Base.metadata.create_all(alb.engine)
        cls.client = TestClient(alb.app)
        cls.headers = {"Authorization": "Bearer test-token"}

    def test_01_health_check(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["database"], "connected")

    def test_02_prediction_endpoint(self):
        payload = {
            "amount": 2200.50,
            "currency": "USD",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "sender_account_id": "ACC-TEST-001",
            "receiver_account_id": "ACC-TEST-002",
            "device_id": "DEV-TEST-001",
            "status": "pending",
        }
        response = self.client.post("/api/predictions", json=payload, headers=self.headers)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("fraud_score", data)
        self.assertIn("prediction_label", data)
        self.assertIn("risk_level", data)
        self.assertIn("transaction_id", data)

    def test_03_ml_metrics(self):
        response = self.client.get("/api/ml/metrics", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("eligible_feedback_count", data)
        self.assertIn("models", data)
        self.assertIn("training_jobs", data)

    def test_04_fraud_case_workflow(self):
        # 1. Create a transaction
        tx_payload = {
            "amount": 5000.00,
            "currency": "USD",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "sender_account_id": "ACC-SUSPECT-10",
            "receiver_account_id": "ACC-OFFSHORE-99",
            "device_id": "DEV-UNTRUSTED",
            "status": "pending",
        }
        tx_res = self.client.post("/api/predictions", json=tx_payload, headers=self.headers)
        self.assertEqual(tx_res.status_code, 201)
        tx_id = tx_res.json()["transaction_id"]

        # Check if high-risk auto-created a case, or create manually
        with alb.SessionLocal() as db:
            case_link = db.scalars(
                alb.select(alb.CaseTransaction).where(alb.CaseTransaction.transaction_id == tx_id)
            ).first()

            if case_link:
                case_id = case_link.case_id
            else:
                create_res = self.client.post("/api/fraud-cases", json=[tx_id], headers=self.headers)
                self.assertEqual(create_res.status_code, 201)
                case_id = create_res.json()["case_id"]

        # 2. Start review
        review_res = self.client.post(f"/api/fraud-cases/{case_id}/start-review", headers=self.headers)
        self.assertIn(review_res.status_code, [200, 409])  # 200 or already under review

        # 3. Resolve case
        resolve_payload = {
            "status": "confirmed_fraud",
            "confirmed_amount": 5000.00,
            "recovered_amount": 4000.00,
            "reason_code": "VERIFIED_FRAUD_SYNDICATE",
        }
        resolve_res = self.client.post(
            f"/api/fraud-cases/{case_id}/resolve",
            json=resolve_payload,
            headers=self.headers,
        )
        self.assertIn(resolve_res.status_code, [200, 409])


if __name__ == "__main__":
    unittest.main()
