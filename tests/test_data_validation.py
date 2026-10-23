"""
Unit tests for WindLens Phase 2 data ingestion, validation, and caching.

Covers:
- Actual record filtering (fuelType == 'WIND')
- Forecast publication timestamp and vintage preservation
- Duplicate delivery periods across distinct publication vintages
- Invalid timestamps and non-numeric generation values
- Simulated API failures and malformed JSON responses
- Distinguishing empty successful responses from network/HTTP failures
- Cache reading, writing, and provenance metadata validation
- Decision cutoff forecast selection logic

All external HTTP requests are mocked with synthetic fixtures to ensure
tests run deterministically without internet dependency.
"""

import json
import os
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import urllib.error

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.cache import (
    build_cache_payload,
    load_json_cache,
    save_json_cache,
)
from scripts.ingestion import (
    ElexonAPIError,
    execute_request,
    fetch_actual_wind,
    fetch_wind_forecast_history,
    fetch_wind_forecasts_latest,
    normalize_actual_records,
    normalize_forecast_records,
)
from scripts.validation import (
    format_utc_timestamp,
    parse_iso_timestamp,
    select_forecast_at_cutoff,
    validate_actual_record,
    validate_forecast_record,
)


class TestValidationAndSelection(unittest.TestCase):
    """Test validation and cutoff logic with synthetic fixtures."""

    def setUp(self):
        self.SYNTHETIC_WIND_ACTUAL = {
            "dataset": "FUELHH",
            "publishTime": "2026-01-01T01:00:00Z",
            "startTime": "2026-01-01T00:30:00Z",
            "settlementDate": "2026-01-01",
            "settlementPeriod": 2,
            "fuelType": "WIND",
            "generation": 1850.5,
        }

        self.SYNTHETIC_SOLAR_ACTUAL = {
            "dataset": "FUELHH",
            "publishTime": "2026-01-01T01:00:00Z",
            "startTime": "2026-01-01T00:30:00Z",
            "settlementDate": "2026-01-01",
            "settlementPeriod": 2,
            "fuelType": "SOLAR",
            "generation": 0.0,
        }

        self.SYNTHETIC_FORECAST_V1 = {
            "dataset": "WINDFOR",
            "publishTime": "2025-12-31T09:30:00Z",
            "startTime": "2026-01-01T12:00:00Z",
            "settlementDate": "2026-01-01",
            "settlementPeriod": 25,
            "generation": 12500,
        }

        self.SYNTHETIC_FORECAST_V2 = {
            "dataset": "WINDFOR",
            "publishTime": "2025-12-31T16:30:00Z",
            "startTime": "2026-01-01T12:00:00Z",
            "settlementDate": "2026-01-01",
            "settlementPeriod": 25,
            "generation": 14200,
        }

        self.SYNTHETIC_FORECAST_V3_LATE = {
            "dataset": "WINDFOR",
            "publishTime": "2026-01-01T10:30:00Z",
            "startTime": "2026-01-01T12:00:00Z",
            "settlementDate": "2026-01-01",
            "settlementPeriod": 25,
            "generation": 15100,
        }

    def test_timezone_aware_utc_parsing(self):
        dt = parse_iso_timestamp("2026-01-01T00:30:00Z")
        self.assertIsNotNone(dt.tzinfo)
        self.assertEqual(dt.tzinfo, timezone.utc)
        self.assertEqual(format_utc_timestamp(dt), "2026-01-01T00:30:00Z")

    def test_invalid_timestamp_raises_value_error(self):
        with self.assertRaises(ValueError):
            parse_iso_timestamp("invalid-date")
        with self.assertRaises(ValueError):
            parse_iso_timestamp("")

    def test_actual_fuel_type_filtering(self):
        raw_batch = [self.SYNTHETIC_WIND_ACTUAL, self.SYNTHETIC_SOLAR_ACTUAL]
        filtered = normalize_actual_records(raw_batch)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["fuelType"], "WIND")
        self.assertEqual(filtered[0]["generation"], 1850.5)

    def test_missing_generation_not_coerced_to_zero(self):
        record_no_gen = {"startTime": "2026-01-01T00:30:00Z", "fuelType": "WIND"}
        with self.assertRaises(ValueError) as ctx:
            validate_actual_record(record_no_gen)
        self.assertIn("missing required field: 'generation'", str(ctx.exception))

    def test_non_numeric_generation_fails(self):
        bad_record = {
            "startTime": "2026-01-01T00:30:00Z",
            "fuelType": "WIND",
            "generation": "NaN",
        }
        with self.assertRaises(ValueError):
            validate_actual_record(bad_record)

    def test_forecast_publication_timestamp_preserved(self):
        norm = normalize_forecast_records([self.SYNTHETIC_FORECAST_V1])
        self.assertEqual(len(norm), 1)
        self.assertEqual(norm[0]["publishTime"], "2025-12-31T09:30:00Z")
        self.assertEqual(norm[0]["startTime"], "2026-01-01T12:00:00Z")

    def test_duplicate_delivery_periods_across_vintages_preserved(self):
        # Two vintages for the same delivery interval (2026-01-01T12:00:00Z)
        norm = normalize_forecast_records([self.SYNTHETIC_FORECAST_V2, self.SYNTHETIC_FORECAST_V1])
        self.assertEqual(len(norm), 2)
        # Should be sorted deterministically
        self.assertEqual(norm[0]["publishTime"], "2025-12-31T09:30:00Z")
        self.assertEqual(norm[1]["publishTime"], "2025-12-31T16:30:00Z")
        self.assertEqual(norm[0]["generation"], 12500.0)
        self.assertEqual(norm[1]["generation"], 14200.0)

    def test_cutoff_forecast_selection(self):
        vintages = [self.SYNTHETIC_FORECAST_V1, self.SYNTHETIC_FORECAST_V2, self.SYNTHETIC_FORECAST_V3_LATE]

        # Day-ahead cutoff: 2025-12-31 11:00 UTC (EPEX auction)
        selected_da = select_forecast_at_cutoff(
            vintages,
            cutoff_time="2025-12-31T11:00:00Z",
            target_start_time="2026-01-01T12:00:00Z",
        )
        self.assertIsNotNone(selected_da)
        self.assertEqual(selected_da["publishTime"], "2025-12-31T09:30:00Z")
        self.assertEqual(selected_da["generation"], 12500.0)

        # Later evening cutoff: 2025-12-31 18:00 UTC
        selected_eve = select_forecast_at_cutoff(
            vintages,
            cutoff_time="2025-12-31T18:00:00Z",
            target_start_time="2026-01-01T12:00:00Z",
        )
        self.assertIsNotNone(selected_eve)
        self.assertEqual(selected_eve["publishTime"], "2025-12-31T16:30:00Z")
        self.assertEqual(selected_eve["generation"], 14200.0)


class TestIngestionClientMocked(unittest.TestCase):
    """Test ingestion HTTP calls, error handling, and payload shapes with mocks."""

    @patch("urllib.request.urlopen")
    def test_fetch_actual_wind_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_payload = [
            {"dataset": "FUELHH", "startTime": "2026-01-01T00:00:00Z", "fuelType": "WIND", "generation": 1000},
            {"dataset": "FUELHH", "startTime": "2026-01-01T00:00:00Z", "fuelType": "CCGT", "generation": 3000},
        ]
        mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        records = fetch_actual_wind("2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z")
        self.assertEqual(len(records), 2)

        norm = normalize_actual_records(records)
        self.assertEqual(len(norm), 1)
        self.assertEqual(norm[0]["fuelType"], "WIND")

    @patch("urllib.request.urlopen")
    def test_fetch_forecast_latest_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_payload = {
            "metadata": {"datasets": ["WINDFOR"]},
            "data": [
                {
                    "publishTime": "2026-01-01T22:30:00Z",
                    "startTime": "2026-01-01T00:00:00Z",
                    "generation": 19960,
                }
            ],
        }
        mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        records = fetch_wind_forecasts_latest("2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z")
        self.assertEqual(len(records), 1)
        norm = normalize_forecast_records(records)
        self.assertEqual(norm[0]["generation"], 19960.0)

    @patch("urllib.request.urlopen")
    def test_fetch_forecast_history_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_payload = {
            "data": [
                {
                    "publishTime": "2025-12-31T09:30:00Z",
                    "startTime": "2026-01-01T00:00:00Z",
                    "generation": 12000,
                }
            ]
        }
        mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        records = fetch_wind_forecast_history("2025-12-31T11:00:00Z")
        self.assertEqual(len(records), 1)
        norm = normalize_forecast_records(records)
        self.assertEqual(norm[0]["publishTime"], "2025-12-31T09:30:00Z")

    @patch("urllib.request.urlopen")
    def test_empty_results_distinguished(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.read.return_value = json.dumps([]).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        records = fetch_actual_wind("2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z")
        self.assertEqual(records, [])
        cache = build_cache_payload("FUELHH", "/datasets/FUELHH/stream", {}, records)
        self.assertTrue(cache["metadata"]["is_empty"])
        self.assertEqual(cache["metadata"]["status"], "SUCCESS")

    @patch("urllib.request.urlopen")
    def test_http_error_handling(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://data.elexon.co.uk",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=MagicMock(read=lambda: b"Not found"),
        )
        with self.assertRaises(ElexonAPIError) as ctx:
            fetch_actual_wind("2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z")
        self.assertIn("HTTP 404", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_malformed_json_handling(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.read.return_value = b"{not-valid-json"
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        with self.assertRaises(ElexonAPIError) as ctx:
            fetch_actual_wind("2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z")
        self.assertIn("Failed to decode JSON", str(ctx.exception))


class TestCacheOperations(unittest.TestCase):
    """Test reading and writing cached data with metadata."""

    def test_save_and_load_cache(self):
        sample_records = [
            {"startTime": "2026-01-01T00:00:00Z", "fuelType": "WIND", "generation": 1500.0}
        ]
        cache_data = build_cache_payload(
            dataset_name="FUELHH_WIND",
            source_endpoint="/datasets/FUELHH/stream",
            parameters={"test": "param"},
            records=sample_records,
            date_range={"from": "2026-01-01T00:00:00Z", "to": "2026-01-01T01:00:00Z"},
        )

        test_file = os.path.join(os.path.dirname(__file__), "test_temp_cache.json")
        try:
            saved_path = save_json_cache(test_file, cache_data)
            self.assertTrue(os.path.exists(saved_path))

            loaded = load_json_cache(test_file)
            self.assertEqual(loaded["metadata"]["record_count"], 1)
            self.assertFalse(loaded["metadata"]["is_empty"])
            self.assertEqual(loaded["metadata"]["status"], "SUCCESS")
            self.assertEqual(loaded["data"][0]["generation"], 1500.0)
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

    def test_load_cache_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_json_cache("non_existent_cache_file.json")


if __name__ == "__main__":
    unittest.main()
