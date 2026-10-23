"""
WindLens Analytics Engine (Phase 3).

Core modules for:
1. Cutoff forecast selection:
   Filters candidate forecasts where publishTime <= cutoff and selects latest vintage.
2. Temporal & resolution alignment:
   Matches half-hourly FUELHH actuals to hourly WINDFOR forecasts using documented
   interval-start semantics.
   Averages the two half-hourly actuals (HH1: XX:00 and HH2: XX:30) to form the
   defensible hourly actual generation for each hour XX:00.
3. Forecast error metrics calculation:
   error_mw = forecast_generation - actual_generation
   MAE = mean(abs(error_mw))
   RMSE = sqrt(mean(error_mw ** 2))
   MBE = mean(error_mw)
   MAPE = mean(abs(error_mw) / actual_generation) * 100 (safely excluding near-zero/zero actuals)
4. Daily summaries, peak errors, lead-time tracking, and data quality summaries.
"""

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from scripts.validation import (
    format_utc_timestamp,
    parse_iso_timestamp,
    validate_actual_record,
    validate_forecast_record,
)


def select_forecasts_for_delivery_periods(
    candidate_forecasts: List[Dict[str, Any]],
    cutoff_policy: str = "day_ahead_1100",
    specific_cutoff_map: Optional[Dict[str, str]] = None,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Select the eligible forecast for each delivery interval based on a cutoff policy.

    Rule:
      For each delivery interval target startTime, select the record with the latest
      publishTime such that publishTime <= cutoff_time.

    Cutoff Policies:
      - 'day_ahead_1100': Cutoff is 11:00:00 UTC on day D-1 (UK Day-Ahead auction gate closure).
      - 'custom_map': Uses explicit delivery_date -> cutoff_iso mapping from specific_cutoff_map.

    Returns:
      (selected_records, unselected_start_times)
    """
    # Group candidates by target delivery interval startTime
    grouped_by_start: Dict[str, List[Dict[str, Any]]] = {}
    for r in candidate_forecasts:
        st = r.get("startTime")
        if st:
            grouped_by_start.setdefault(st, []).append(r)

    selected_records: List[Dict[str, Any]] = []
    unselected_starts: List[str] = []

    for start_time_str in sorted(grouped_by_start.keys()):
        start_dt = parse_iso_timestamp(start_time_str)
        delivery_date_str = start_dt.strftime("%Y-%m-%d")

        # Determine cutoff timestamp
        if cutoff_policy == "day_ahead_1100":
            cutoff_dt = datetime(start_dt.year, start_dt.month, start_dt.day, 11, 0, 0, tzinfo=timezone.utc) - timedelta(days=1)
        elif cutoff_policy == "custom_map" and specific_cutoff_map and delivery_date_str in specific_cutoff_map:
            cutoff_dt = parse_iso_timestamp(specific_cutoff_map[delivery_date_str])
        else:
            raise ValueError(f"Unsupported cutoff policy or missing mapping for date {delivery_date_str}")

        # Find all candidate vintages with publishTime <= cutoff_dt
        eligible = []
        for cand in grouped_by_start[start_time_str]:
            pub_dt = parse_iso_timestamp(cand["publishTime"])
            if pub_dt <= cutoff_dt:
                eligible.append((pub_dt, cand))

        if eligible:
            # Deterministic selection: highest publishTime
            eligible.sort(key=lambda item: item[0])
            best_vintage = eligible[-1][1]
            selected_records.append({
                "dataset": best_vintage.get("dataset", "WINDFOR"),
                "startTime": start_time_str,
                "publishTime": best_vintage["publishTime"],
                "cutoffTime": format_utc_timestamp(cutoff_dt),
                "settlementDate": best_vintage.get("settlementDate", delivery_date_str),
                "settlementPeriod": best_vintage.get("settlementPeriod"),
                "generation": float(best_vintage["generation"]),
            })
        else:
            unselected_starts.append(start_time_str)

    return selected_records, unselected_starts


def align_actuals_to_hourly(actual_records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Aggregate 30-minute FUELHH actual wind generation records to 60-minute intervals.

    Documented Interval Semantics:
      Hour XX:00 delivery interval consists of:
        - Settlement Period A: XX:00:00Z to XX:30:00Z
        - Settlement Period B: XX:30:00Z to (XX+1):00:00Z
      The defensible average hourly power in MW is:
        Actual_hourly = (Actual_HH_A + Actual_HH_B) / 2.0

    Returns:
      dict mapping hour_start_timestamp -> {
          'startTime': 'YYYY-MM-DDTHH:00:00Z',
          'generation': hourly_average_mw,
          'hh_records_count': 2,
          'hh1_mw': ...,
          'hh2_mw': ...
      }
    """
    # Group actual records by hour start timestamp
    hours: Dict[str, List[Dict[str, Any]]] = {}
    for r in actual_records:
        if r.get("fuelType") and str(r["fuelType"]).upper() != "WIND":
            continue
        dt = parse_iso_timestamp(r["startTime"])
        hour_key = dt.strftime("%Y-%m-%dT%H:00:00Z")
        hours.setdefault(hour_key, []).append(r)

    aligned_hourly: Dict[str, Dict[str, Any]] = {}
    for hour_key, recs in hours.items():
        if len(recs) == 2:
            # Sort by startTime so HH1 is :00 and HH2 is :30
            recs_sorted = sorted(recs, key=lambda x: x["startTime"])
            g1 = float(recs_sorted[0]["generation"])
            g2 = float(recs_sorted[1]["generation"])
            avg_mw = (g1 + g2) / 2.0
            aligned_hourly[hour_key] = {
                "startTime": hour_key,
                "generation": avg_mw,
                "hh_records_count": 2,
                "hh1_mw": g1,
                "hh2_mw": g2,
                "settlementDate": recs_sorted[0].get("settlementDate"),
                "settlementPeriodStart": recs_sorted[0].get("settlementPeriod"),
            }
        else:
            # Incomplete hour (e.g. only 1 HH period available)
            aligned_hourly[hour_key] = {
                "startTime": hour_key,
                "generation": float(recs[0]["generation"]),
                "hh_records_count": len(recs),
                "incomplete": True,
            }

    return aligned_hourly


def match_forecast_and_actuals(
    forecast_records: List[Dict[str, Any]],
    actual_records: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
    """Match hourly forecast records to aligned hourly actual generation records.

    Returns:
      (matched_pairs, unmatched_forecast_starts, unmatched_actual_starts)
    """
    hourly_actuals = align_actuals_to_hourly(actual_records)
    matched_pairs: List[Dict[str, Any]] = []
    unmatched_forecasts: List[str] = []

    actuals_matched_keys = set()

    for fc in forecast_records:
        st = fc["startTime"]
        if st in hourly_actuals and hourly_actuals[st].get("hh_records_count") == 2:
            act = hourly_actuals[st]
            fc_mw = float(fc["generation"])
            act_mw = float(act["generation"])
            err_mw = fc_mw - act_mw  # Signed error: positive = over-forecast, negative = under-forecast

            start_dt = parse_iso_timestamp(st)
            pub_dt = parse_iso_timestamp(fc["publishTime"])
            lead_time_hours = (start_dt - pub_dt).total_seconds() / 3600.0

            matched_pairs.append({
                "startTime": st,
                "publishTime": fc["publishTime"],
                "cutoffTime": fc.get("cutoffTime"),
                "lead_time_hours": round(lead_time_hours, 2),
                "settlementDate": act.get("settlementDate", st[:10]),
                "forecast_mw": fc_mw,
                "actual_mw": act_mw,
                "actual_hh1_mw": act.get("hh1_mw"),
                "actual_hh2_mw": act.get("hh2_mw"),
                "error_mw": err_mw,
                "abs_error_mw": abs(err_mw),
                "sq_error_mw": err_mw ** 2,
            })
            actuals_matched_keys.add(st)
        else:
            unmatched_forecasts.append(st)

    unmatched_actuals = [k for k in sorted(hourly_actuals.keys()) if k not in actuals_matched_keys]
    matched_pairs.sort(key=lambda x: x["startTime"])

    return matched_pairs, unmatched_forecasts, unmatched_actuals


def calculate_accuracy_metrics(
    matched_pairs: List[Dict[str, Any]],
    min_actual_for_mape: float = 100.0,
) -> Dict[str, Any]:
    """Calculate standard forecast accuracy metrics across a collection of matched observations.

    Definitions:
      error_mw = forecast_mw - actual_mw
      MAE = mean(abs(error_mw))
      RMSE = sqrt(mean(error_mw ** 2))
      MBE = mean(error_mw) (Bias)
      MAPE = mean(abs(error_mw) / actual_mw) * 100 (excludes actual_mw < min_actual_for_mape)

    Rules:
      - Monthly metrics must be computed from raw underlying observations, not daily averages.
      - Never coerce missing values to zero.
    """
    n = len(matched_pairs)
    if n == 0:
        return {
            "observation_count": 0,
            "mae_mw": None,
            "rmse_mw": None,
            "mbe_mw": None,
            "mape_percent": None,
            "valid": False,
        }

    sum_abs_err = sum(p["abs_error_mw"] for p in matched_pairs)
    sum_sq_err = sum(p["sq_error_mw"] for p in matched_pairs)
    sum_err = sum(p["error_mw"] for p in matched_pairs)

    mae = sum_abs_err / n
    rmse = math.sqrt(sum_sq_err / n)
    mbe = sum_err / n

    # MAPE calculation with safe threshold for zero / near-zero generation
    mape_eligible = [p for p in matched_pairs if p["actual_mw"] >= min_actual_for_mape]
    if mape_eligible:
        mape_val = (sum(p["abs_error_mw"] / p["actual_mw"] for p in mape_eligible) / len(mape_eligible)) * 100.0
    else:
        mape_val = None

    mean_actual = sum(p["actual_mw"] for p in matched_pairs) / n
    mean_forecast = sum(p["forecast_mw"] for p in matched_pairs) / n
    nmae_percent = (mae / mean_actual * 100.0) if mean_actual > 0 else None

    return {
        "observation_count": n,
        "mae_mw": round(mae, 2),
        "rmse_mw": round(rmse, 2),
        "mbe_mw": round(mbe, 2),
        "mape_percent": round(mape_val, 2) if mape_val is not None else None,
        "nmae_percent": round(nmae_percent, 2) if nmae_percent is not None else None,
        "mean_actual_mw": round(mean_actual, 2),
        "mean_forecast_mw": round(mean_forecast, 2),
        "mape_excluded_count": n - len(mape_eligible),
        "valid": True,
    }


def calculate_daily_breakdown(matched_pairs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Calculate daily accuracy metrics and observation counts for each calendar day."""
    days: Dict[str, List[Dict[str, Any]]] = {}
    for p in matched_pairs:
        d_str = p["settlementDate"]
        days.setdefault(d_str, []).append(p)

    daily_metrics = []
    for d_str in sorted(days.keys()):
        pairs = days[d_str]
        m = calculate_accuracy_metrics(pairs)
        daily_metrics.append({
            "date": d_str,
            "observation_count": len(pairs),
            "expected_count": 24,
            "coverage_percent": round(len(pairs) / 24.0 * 100.0, 1),
            "mae_mw": m["mae_mw"],
            "rmse_mw": m["rmse_mw"],
            "mbe_mw": m["mbe_mw"],
            "mape_percent": m["mape_percent"],
            "mean_actual_mw": m["mean_actual_mw"],
            "mean_forecast_mw": m["mean_forecast_mw"],
        })

    return daily_metrics


def identify_largest_errors(matched_pairs: List[Dict[str, Any]], top_n: int = 10) -> List[Dict[str, Any]]:
    """Identify the top N largest absolute forecast errors."""
    sorted_pairs = sorted(matched_pairs, key=lambda x: x["abs_error_mw"], reverse=True)
    top_records = []
    for p in sorted_pairs[:top_n]:
        top_records.append({
            "startTime": p["startTime"],
            "publishTime": p["publishTime"],
            "lead_time_hours": p.get("lead_time_hours"),
            "forecast_mw": p["forecast_mw"],
            "actual_mw": p["actual_mw"],
            "error_mw": p["error_mw"],
            "abs_error_mw": p["abs_error_mw"],
            "direction": "OVER_FORECAST" if p["error_mw"] > 0 else "UNDER_FORECAST",
        })
    return top_records

