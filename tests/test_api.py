"""
API integration and unit tests for FastAPI endpoints.
"""

import unittest
from fastapi.testclient import TestClient

from backend.main import app


class TestFastAPIEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_endpoint(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["dataset_period"], "2026-01")
        self.assertGreater(data["total_observations_available"], 700)

    def test_overview_endpoint(self):
        resp = self.client.get("/api/overview")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("metrics", data)
        self.assertEqual(data["metrics"]["observation_count"], 743)
        self.assertEqual(data["metrics"]["mae_mw"], 2124.56)
        self.assertGreater(data["coverage_percentage"], 99.0)

    def test_forecasts_valid_date(self):
        resp = self.client.get("/api/forecasts?date=2026-01-15")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["date"], "2026-01-15")
        self.assertEqual(data["observation_count"], 24)
        self.assertEqual(len(data["data"]), 24)
        # Check first delivery interval structure
        first_item = data["data"][0]
        self.assertIn("forecast_mw", first_item)
        self.assertIn("actual_mw", first_item)
        self.assertIn("error_mw", first_item)

    def test_forecasts_invalid_date_format(self):
        resp = self.client.get("/api/forecasts?date=invalid-date")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Invalid format", resp.json()["detail"])

    def test_forecasts_out_of_range_date(self):
        resp = self.client.get("/api/forecasts?date=2025-05-01")
        self.assertEqual(resp.status_code, 404)

    def test_accuracy_range_endpoint(self):
        resp = self.client.get("/api/accuracy?from=2026-01-01&to=2026-01-10")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["from_date"], "2026-01-01")
        self.assertEqual(data["to_date"], "2026-01-10")
        self.assertEqual(data["observation_count"], 240)
        self.assertIn("mae_mw", data["metrics"])

    def test_accuracy_invalid_range_ordering(self):
        resp = self.client.get("/api/accuracy?from=2026-01-20&to=2026-01-10")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("cannot be after", resp.json()["detail"])

    def test_accuracy_daily_endpoint(self):
        resp = self.client.get("/api/accuracy/daily?from=2026-01-01&to=2026-01-05")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_days"], 5)
        self.assertEqual(len(data["daily_breakdown"]), 5)

    def test_top_errors_endpoint(self):
        resp = self.client.get("/api/errors?limit=5")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 5)
        self.assertEqual(len(data["largest_errors"]), 5)
        # Check that peak error is on 2026-01-12
        peak = data["largest_errors"][0]
        self.assertTrue(peak["startTime"].startswith("2026-01-12"))
        self.assertGreater(peak["abs_error_mw"], 6000)

    def test_csv_export_endpoint(self):
        resp = self.client.get("/api/export.csv?from=2026-01-01&to=2026-01-02")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["content-type"], "text/csv; charset=utf-8")
        lines = resp.text.strip().split("\r\n") if "\r\n" in resp.text else resp.text.strip().split("\n")
        self.assertGreater(len(lines), 40)
        header = lines[0]
        self.assertIn("startTime", header)
        self.assertIn("forecast_mw", header)
        self.assertIn("actual_mw", header)


if __name__ == "__main__":
    unittest.main()

