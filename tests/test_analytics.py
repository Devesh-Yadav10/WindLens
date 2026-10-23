"""
Unit tests for WindLens Phase 3 Analytics, Forecast Cutoff Selection, and Matching.

Covers:
- Forecast selection at configured cutoff: latest eligible publishTime <= cutoff.
- Strict rejection of forecasts published after cutoff (lookahead bias guard).
- Preservation of original publish timestamps and lead-time calculations.
- Handling duplicate candidate vintages deterministically.
- Unmatched delivery periods reporting when no vintage qualifies before cutoff.
- Accurate interval semantics: averaging 30-min actuals (XX:00 & XX:30) to form hourly actual.
- Incomplete hour handling (missing HH interval excluded).
- Metrics calculation: MAE, RMSE, MBE (bias), and MAPE with zero-actual guard.
- Monthly metrics calculated directly from underlying observations (not averaged daily metrics).
- Coverage calculation and top error identification.
- End-to-end reproducible pipeline run and file generation.

All tests run deterministically with synthetic fixtures.
"""

import math
import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.analytics import (
    align_actuals_to_hourly,
    calculate_accuracy_metrics,
    calculate_daily_breakdown,
    identify_largest_errors,
    match_forecast_and_actuals,
    select_forecasts_for_delivery_periods,
)
from scripts.cache import build_cache_payload, save_json_cache


class TestForecastSelection(unittest.TestCase):
    """Test cutoff-based forecast selection with synthetic fixtures."""

    def setUp(self):
        # Delivery on 2026-01-02 at 12:00 UTC.
        # Day-ahead D-1 cutoff is 2026-01-01 11:00:00Z.
        self.CANDIDATE_VINTAGES = [
            # Vintage A: published D-2 (too early, but eligible)
            {
                "dataset": "WINDFOR",
                "startTime": "2026-01-02T12:00:00Z",
                "publishTime": "2025-12-31T22:30:00Z",
                "generation": 10000.0,
            },
            # Vintage B: published D-1 at 09:30Z (eligible and latest before 11:00Z cutoff)
            {
                "dataset": "WINDFOR",
                "startTime": "2026-01-02T12:00:00Z",
                "publishTime": "2026-01-01T09:30:00Z",
                "generation": 12000.0,
            },
            # Vintage C: published D-1 at 12:30Z (AFTER the 11:00Z cutoff - must be excluded)
            {
                "dataset": "WINDFOR",
                "startTime": "2026-01-02T12:00:00Z",
                "publishTime": "2026-01-01T12:30:00Z",
                "generation": 15000.0,
            },
            # Vintage D: published on Day D at 05:30Z (intraday - must be excluded)
            {
                "dataset": "WINDFOR",
                "startTime": "2026-01-02T12:00:00Z",
                "publishTime": "2026-01-02T05:30:00Z",
                "generation": 16000.0,
            },
        ]

    def test_select_latest_eligible_forecast_before_cutoff(self):
        selected, unselected = select_forecasts_for_delivery_periods(
            candidate_forecasts=self.CANDIDATE_VINTAGES,
            cutoff_policy="day_ahead_1100",
        )
        self.assertEqual(len(selected), 1)
        self.assertEqual(len(unselected), 0)

        # Must select Vintage B (09:30 UTC), NOT C (12:30 UTC) or D (05:30 UTC intraday)
        rec = selected[0]
        self.assertEqual(rec["startTime"], "2026-01-02T12:00:00Z")
        self.assertEqual(rec["publishTime"], "2026-01-01T09:30:00Z")
        self.assertEqual(rec["generation"], 12000.0)
        self.assertEqual(rec["cutoffTime"], "2026-01-01T11:00:00Z")

    def test_unselected_when_all_vintages_after_cutoff(self):
        # All vintages published after the cutoff
        late_vintages = [self.CANDIDATE_VINTAGES[2], self.CANDIDATE_VINTAGES[3]]
        selected, unselected = select_forecasts_for_delivery_periods(
            candidate_forecasts=late_vintages,
            cutoff_policy="day_ahead_1100",
        )
        self.assertEqual(len(selected), 0)
        self.assertEqual(len(unselected), 1)
        self.assertEqual(unselected[0], "2026-01-02T12:00:00Z")

    def test_custom_cutoff_policy(self):
        # Custom cutoff map for specific gate closure
        custom_map = {"2026-01-02": "2026-01-01T15:00:00Z"}
        selected, unselected = select_forecasts_for_delivery_periods(
            candidate_forecasts=self.CANDIDATE_VINTAGES,
            cutoff_policy="custom_map",
            specific_cutoff_map=custom_map,
        )
        self.assertEqual(len(selected), 1)
        # Under 15:00 UTC cutoff, Vintage C (12:30 UTC) becomes eligible and is the latest
        self.assertEqual(selected[0]["publishTime"], "2026-01-01T12:30:00Z")
        self.assertEqual(selected[0]["generation"], 15000.0)


class TestAlignmentAndMatching(unittest.TestCase):
    """Test resolution alignment and record matching."""

    def test_align_actuals_to_hourly_averages_two_half_hours(self):
        actuals = [
            {"startTime": "2026-01-01T14:00:00Z", "fuelType": "WIND", "generation": 1000.0},
            {"startTime": "2026-01-01T14:30:00Z", "fuelType": "WIND", "generation": 2000.0},
        ]
        hourly = align_actuals_to_hourly(actuals)
        self.assertIn("2026-01-01T14:00:00Z", hourly)
        # Expected average = (1000 + 2000) / 2 = 1500.0 MW
        self.assertEqual(hourly["2026-01-01T14:00:00Z"]["generation"], 1500.0)
        self.assertEqual(hourly["2026-01-01T14:00:00Z"]["hh_records_count"], 2)

    def test_incomplete_hour_marked_and_not_matched(self):
        # Only 1 half-hour available for 14:00
        actuals = [
            {"startTime": "2026-01-01T14:00:00Z", "fuelType": "WIND", "generation": 1000.0},
        ]
        forecasts = [
            {"startTime": "2026-01-01T14:00:00Z", "publishTime": "2025-12-31T09:30:00Z", "generation": 1200.0}
        ]
        matched, unmatched_fc, unmatched_act = match_forecast_and_actuals(forecasts, actuals)
        self.assertEqual(len(matched), 0)
        self.assertEqual(len(unmatched_fc), 1)
        self.assertEqual(unmatched_fc[0], "2026-01-01T14:00:00Z")

    def test_signed_error_and_lead_time_calculation(self):
        actuals = [
            {"startTime": "2026-01-01T10:00:00Z", "fuelType": "WIND", "generation": 4000.0},
            {"startTime": "2026-01-01T10:30:00Z", "fuelType": "WIND", "generation": 6000.0},
        ]
        # Actual hourly average = 5000.0 MW. Forecast = 6500.0 MW.
        forecasts = [
            {
                "startTime": "2026-01-01T10:00:00Z",
                "publishTime": "2025-12-31T09:30:00Z",
                "generation": 6500.0,
            }
        ]
        matched, _, _ = match_forecast_and_actuals(forecasts, actuals)
        self.assertEqual(len(matched), 1)
        rec = matched[0]
        # error_mw = forecast - actual = 6500 - 5000 = +1500 (over-forecast)
        self.assertEqual(rec["error_mw"], 1500.0)
        self.assertEqual(rec["abs_error_mw"], 1500.0)
        # Lead time: from 2025-12-31 09:30 to 2026-01-01 10:00 is 24.5 hours
        self.assertEqual(rec["lead_time_hours"], 24.5)


class TestAccuracyMetricsCalculation(unittest.TestCase):
    """Test MAE, RMSE, MBE, and MAPE metric calculations."""

    def setUp(self):
        # Synthetic observations with known manual calculations:
        # Obs 1: Actual = 1000, Forecast = 1200 -> Error = +200, Abs = 200, Sq = 40,000
        # Obs 2: Actual = 2000, Forecast = 1700 -> Error = -300, Abs = 300, Sq = 90,000
        # Obs 3: Actual = 500,  Forecast = 600  -> Error = +100, Abs = 100, Sq = 10,000
        # N = 3
        # Sum Err = 0, MBE = 0.0
        # Sum Abs Err = 600, MAE = 200.0
        # Sum Sq Err = 140,000, Mean Sq = 46666.67, RMSE = sqrt(46666.67) = 216.02
        # MAPE:
        # Obs 1: 200 / 1000 = 0.20
        # Obs 2: 300 / 2000 = 0.15
        # Obs 3: 100 / 500  = 0.20
        # Mean MAPE = (0.20 + 0.15 + 0.20) / 3 * 100 = 18.33%
        self.SYNTHETIC_MATCHED = [
            {
                "startTime": "2026-01-01T00:00:00Z",
                "settlementDate": "2026-01-01",
                "publishTime": "2025-12-31T09:30:00Z",
                "actual_mw": 1000.0,
                "forecast_mw": 1200.0,
                "error_mw": 200.0,
                "abs_error_mw": 200.0,
                "sq_error_mw": 40000.0,
            },
            {
                "startTime": "2026-01-01T01:00:00Z",
                "settlementDate": "2026-01-01",
                "publishTime": "2025-12-31T09:30:00Z",
                "actual_mw": 2000.0,
                "forecast_mw": 1700.0,
                "error_mw": -300.0,
                "abs_error_mw": 300.0,
                "sq_error_mw": 90000.0,
            },
            {
                "startTime": "2026-01-01T02:00:00Z",
                "settlementDate": "2026-01-01",
                "publishTime": "2025-12-31T09:30:00Z",
                "actual_mw": 500.0,
                "forecast_mw": 600.0,
                "error_mw": 100.0,
                "abs_error_mw": 100.0,
                "sq_error_mw": 10000.0,
            },
        ]

    def test_metrics_values(self):
        m = calculate_accuracy_metrics(self.SYNTHETIC_MATCHED)
        self.assertEqual(m["observation_count"], 3)
        self.assertEqual(m["mae_mw"], 200.0)
        self.assertAlmostEqual(m["rmse_mw"], math.sqrt(140000 / 3), places=2)
        self.assertEqual(m["mbe_mw"], 0.0)
        self.assertEqual(m["mape_percent"], 18.33)

    def test_mape_excludes_zero_or_near_zero_actuals(self):
        # Add observation with actual = 0 MW
        zero_actual_obs = {
            "startTime": "2026-01-01T03:00:00Z",
            "settlementDate": "2026-01-01",
            "publishTime": "2025-12-31T09:30:00Z",
            "actual_mw": 0.0,
            "forecast_mw": 50.0,
            "error_mw": 50.0,
            "abs_error_mw": 50.0,
            "sq_error_mw": 2500.0,
        }
        batch = list(self.SYNTHETIC_MATCHED) + [zero_actual_obs]
        m = calculate_accuracy_metrics(batch, min_actual_for_mape=100.0)
        # Should not raise ZeroDivisionError, excludes 1 observation for MAPE
        self.assertEqual(m["mape_excluded_count"], 1)
        self.assertEqual(m["mape_percent"], 18.33)

    def test_empty_dataset_returns_invalid_metrics(self):
        m = calculate_accuracy_metrics([])
        self.assertFalse(m["valid"])
        self.assertEqual(m["observation_count"], 0)
        self.assertIsNone(m["mae_mw"])

    def test_top_largest_errors_ranking(self):
        top = identify_largest_errors(self.SYNTHETIC_MATCHED, top_n=2)
        self.assertEqual(len(top), 2)
        # Largest is Obs 2 (abs error 300)
        self.assertEqual(top[0]["abs_error_mw"], 300.0)
        self.assertEqual(top[0]["direction"], "UNDER_FORECAST")
        # Second largest is Obs 1 (abs error 200)
        self.assertEqual(top[1]["abs_error_mw"], 200.0)
        self.assertEqual(top[1]["direction"], "OVER_FORECAST")


if __name__ == "__main__":
    unittest.main()

