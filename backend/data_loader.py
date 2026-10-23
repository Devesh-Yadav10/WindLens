"""
Data access layer for the FastAPI backend.

Loads and caches the verified January 2026 actuals, day-ahead forecasts,
and precomputed analytics outputs. Reuses scripts/analytics.py for on-the-fly
filtered calculations.
"""

import csv
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from scripts.analytics import (
    calculate_accuracy_metrics,
    calculate_daily_breakdown,
    identify_largest_errors,
    match_forecast_and_actuals,
    select_forecasts_for_delivery_periods,
)
from scripts.cache import load_json_cache

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")

# In-memory cached structures
_CACHE: Dict[str, Any] = {}


def get_data_loader():
    """Singleton-style cache loader to serve API queries efficiently without disk thrashing."""
    if "matched_observations" not in _CACHE:
        summary_path = os.path.join(PROCESSED_DIR, "january_2026_accuracy_summary.json")
        csv_path = os.path.join(PROCESSED_DIR, "january_2026_forecast_vs_actual.csv")

        # Fallback or direct load
        if os.path.exists(summary_path) and os.path.exists(csv_path):
            with open(summary_path, "r", encoding="utf-8") as f:
                _CACHE["summary"] = json.load(f)

            observations = []
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    observations.append({
                        "startTime": r["startTime"],
                        "settlementDate": r["settlementDate"],
                        "publishTime": r["publishTime"],
                        "cutoffTime": r["cutoffTime"],
                        "lead_time_hours": float(r["lead_time_hours"]) if r.get("lead_time_hours") else None,
                        "forecast_mw": float(r["forecast_mw"]),
                        "actual_mw": float(r["actual_mw"]),
                        "actual_hh1_mw": float(r["actual_hh1_mw"]) if r.get("actual_hh1_mw") else None,
                        "actual_hh2_mw": float(r["actual_hh2_mw"]) if r.get("actual_hh2_mw") else None,
                        "error_mw": float(r["error_mw"]),
                        "abs_error_mw": float(r["abs_error_mw"]),
                        "sq_error_mw": float(r["error_mw"]) ** 2,
                    })
            _CACHE["matched_observations"] = observations
        else:
            # Recompute from raw caches if processed folder is absent
            act_path = os.path.join(DATA_DIR, "actuals_2026_01.json")
            fc_path = os.path.join(DATA_DIR, "forecasts_day_ahead_cutoff_2026_01.json")
            act_cache = load_json_cache(act_path)
            fc_cache = load_json_cache(fc_path)
            selected_fc, _ = select_forecasts_for_delivery_periods(
                fc_cache.get("data", []),
                cutoff_policy="day_ahead_1100"
            )
            matched, _, _ = match_forecast_and_actuals(selected_fc, act_cache.get("data", []))
            _CACHE["matched_observations"] = matched
            _CACHE["summary"] = {
                "monthly_metrics": calculate_accuracy_metrics(matched),
                "daily_breakdown": calculate_daily_breakdown(matched),
                "top_10_largest_errors": identify_largest_errors(matched, top_n=10)
            }

    return _CACHE


def filter_observations(from_date: Optional[str] = None, to_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """Filter observations by settlementDate range (inclusive)."""
    cache = get_data_loader()
    obs = cache["matched_observations"]
    filtered = []
    for r in obs:
        d = r["settlementDate"]
        if from_date and d < from_date:
            continue
        if to_date and d > to_date:
            continue
        filtered.append(r)
    return filtered

