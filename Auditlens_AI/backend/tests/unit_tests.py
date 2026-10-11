"""Unit tests for the audit workflow and upload endpoint."""

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.audit_engine import audit_analysis


class AnalyzeTransactionsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.reports_dir = Path(self.temp_dir.name) / "reports"
        self.reports_dir.mkdir()
        self.report_folder_patcher = patch.object(
            audit_analysis, "REPORT_FOLDER", self.reports_dir
        )
        self.report_folder_patcher.start()

    def tearDown(self):
        self.report_folder_patcher.stop()
        self.temp_dir.cleanup()

    def test_analyze_csv_creates_report_and_summary(self):
        csv_path = Path(self.temp_dir.name) / "transactions.csv"
        csv_path.write_text(
            "transaction_id,amount,invoice_number\n1,250,INV-1\n2,100000,INV-1\n",
            encoding="utf-8",
        )

        result = audit_analysis.analyze_transactions(csv_path)

        self.assertEqual(result["dashboard"]["total_transactions"], 2)
        self.assertEqual(result["dashboard"]["total_revenue"], 100250.0)
        self.assertTrue(Path(result["report_path"]).is_file())
        self.assertIn("Duplicate invoice", result["investigation"][1]["flags"])

    def test_analyze_rejects_missing_amount_column(self):
        csv_path = Path(self.temp_dir.name) / "transactions.csv"
        csv_path.write_text("transaction_id\n1\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "'amount' column"):
            audit_analysis.analyze_transactions(csv_path)


class UploadRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.uploads_dir = Path(self.temp_dir.name) / "uploads"
        self.reports_dir = Path(self.temp_dir.name) / "reports"
        self.uploads_dir.mkdir()
        self.reports_dir.mkdir()
        self.upload_folder_patcher = patch.object(
            audit_analysis, "UPLOAD_FOLDER", self.uploads_dir
        )
        self.report_folder_patcher = patch.object(
            audit_analysis, "REPORT_FOLDER", self.reports_dir
        )
        self.upload_folder_patcher.start()
        self.report_folder_patcher.start()
        audit_analysis.app.config["TESTING"] = True
        self.client = audit_analysis.app.test_client()

    def tearDown(self):
        self.upload_folder_patcher.stop()
        self.report_folder_patcher.stop()
        audit_analysis.app.config["TESTING"] = False
        self.temp_dir.cleanup()

    def test_single_file_upload_returns_dashboard_and_investigation(self):
        response = self.client.post(
            "/upload",
            data={
                "file": (
                    io.BytesIO(b"transaction_id,amount\n1,125\n"),
                    "transactions.csv",
                )
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["dashboard"]["total_transactions"], 1
        )
        self.assertEqual(len(response.get_json()["investigation"]), 1)

    def test_multiple_file_upload_returns_combined_summary(self):
        response = self.client.post(
            "/upload",
            data={
                "files": [
                    (io.BytesIO(b"amount\n125\n"), "first.csv"),
                    (io.BytesIO(b"amount\n275\n"), "second.csv"),
                ]
            },
            content_type="multipart/form-data",
        )

        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["dashboard"]["total_transactions"], 2)
        self.assertEqual(body["dashboard"]["total_revenue"], 400.0)
        self.assertEqual(len(body["file_results"]), 2)

    def test_upload_rejects_unsupported_file_extension(self):
        response = self.client.post(
            "/upload",
            data={"file": (io.BytesIO(b"not a csv"), "transactions.txt")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid file type", response.get_json()["error"])

    def test_upload_rejects_csv_without_amount_column(self):
        response = self.client.post(
            "/upload",
            data={
                "file": (
                    io.BytesIO(b"transaction_id\n1\n"),
                    "transactions.csv",
                )
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("'amount' column", response.get_json()["error"])
        self.assertEqual(list(self.uploads_dir.iterdir()), [])

    def test_health_endpoint_and_vite_cors_headers(self):
        response = self.client.get(
            "/health", headers={"Origin": "http://localhost:5173"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})
        self.assertEqual(
            response.headers["Access-Control-Allow-Origin"],
            "http://localhost:5173",
        )

    def test_upload_handles_case_insensitive_columns_and_string_values(self):
        csv_data = b"Transaction_ID,Amount,Invoice_Amount,Tax_Amount,Discount\nTXN-1,1000.0,1000,180.0,50\n"
        response = self.client.post(
            "/upload",
            data={"file": (io.BytesIO(csv_data), "transactions.csv")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["dashboard"]["total_transactions"], 1)
        self.assertIn("report_url", data)

    def test_download_report_endpoint(self):
        # Create a report file in reports_dir
        report_file = self.reports_dir / "test_report.xlsx"
        report_file.write_bytes(b"mock excel content")

        response = self.client.get("/reports/test_report.xlsx")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"mock excel content")

    def test_sample_data_endpoint(self):
        response = self.client.get("/sample-data")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("dashboard", data)
        self.assertIn("investigation", data)
        self.assertGreater(data["dashboard"]["total_transactions"], 0)

    def test_upload_dirty_dataset_with_missing_amounts_and_aliases(self):
        dirty_csv = (
            b"Transaction_ID,Invoice_No,Transaction_Date,Vendor_ID,Invoice_Amount,Weekend_Transaction,Approval_Status\n"
            b"TX01,INV-101,2026-09-13,V01,86510.39,Yes,Approved\n"
            b"TX02,INV-102,2026-01-29,V02,,No,Approved\n"
            b"TX03,INV-103,2026-07-01,V03,12142.44,No,Rejected\n"
        )
        response = self.client.post(
            "/upload",
            data={"file": (io.BytesIO(dirty_csv), "financial_fraud_dirty_dataset.csv")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["dashboard"]["total_transactions"], 3)
        # Check that TX02 got flagged for missing amount without crashing
        tx02 = [item for item in data["investigation"] if item["transaction_id"] == "TX02"][0]
        self.assertIn("Missing or invalid transaction amount", tx02["flags"])


if __name__ == "__main__":
    unittest.main()
