"""Data validation rules for Elexon BMRS datasets (FUELHH and WINDFOR)."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def parse_iso_timestamp(ts: Any) -> datetime:
    """Parse an ISO 8601 timestamp string into a timezone-aware UTC datetime."""
    if not isinstance(ts, str) or not ts.strip():
        raise ValueError(f"Invalid timestamp format: expected non-empty string, got {ts!r}")
    cleaned = ts.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception as exc:
        raise ValueError(f"Failed to parse ISO timestamp {ts!r}: {exc}") from exc


def format_utc_timestamp(dt: datetime) -> str:
    """Format a datetime object into a standardized ISO 8601 UTC string ending in 'Z'."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_actual_record(record: Dict[str, Any], enforce_wind_fuel: bool = True) -> Dict[str, Any]:
    """Validate a single generation actual record from FUELHH.
    
    Guarantees generation is numeric, startTime is parseable, and prevents silent zero-coercion.
    """
    if not isinstance(record, dict):
        raise ValueError(f"Record must be a dict, got {type(record).__name__}")

    if "startTime" not in record or record["startTime"] is None:
        raise ValueError("Actual record missing required field: 'startTime'")

    if "generation" not in record or record["generation"] is None:
        raise ValueError("Actual record missing required field: 'generation'")

    start_dt = parse_iso_timestamp(record["startTime"])

    gen = record["generation"]
    if isinstance(gen, bool) or not isinstance(gen, (int, float)):
        raise ValueError(f"Actual generation must be numeric, got {type(gen).__name__}: {gen!r}")

    fuel_type = record.get("fuelType")
    if fuel_type is not None and enforce_wind_fuel and str(fuel_type).strip().upper() != "WIND":
        raise ValueError(f"Expected fuelType 'WIND', got '{fuel_type}'")

    publish_time_str = record.get("publishTime")
    pub_dt = parse_iso_timestamp(publish_time_str) if publish_time_str else None

    return {
        "dataset": record.get("dataset", "FUELHH"),
        "startTime": format_utc_timestamp(start_dt),
        "startDateTime": start_dt,
        "fuelType": str(fuel_type).strip().upper() if fuel_type is not None else "WIND",
        "generation": float(gen),
        "settlementDate": record.get("settlementDate"),
        "settlementPeriod": record.get("settlementPeriod"),
        "publishTime": format_utc_timestamp(pub_dt) if pub_dt else None,
        "publishDateTime": pub_dt,
    }


def validate_forecast_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a single forecast record from WINDFOR.
    
    Guarantees retention of both delivery interval (startTime) and model publication time (publishTime).
    """
    if not isinstance(record, dict):
        raise ValueError(f"Record must be a dict, got {type(record).__name__}")

    if "startTime" not in record or record["startTime"] is None:
        raise ValueError("Forecast record missing required field: 'startTime'")

    if "publishTime" not in record or record["publishTime"] is None:
        raise ValueError("Forecast record missing required field: 'publishTime'")

    if "generation" not in record or record["generation"] is None:
        raise ValueError("Forecast record missing required field: 'generation'")

    start_dt = parse_iso_timestamp(record["startTime"])
    pub_dt = parse_iso_timestamp(record["publishTime"])

    gen = record["generation"]
    if isinstance(gen, bool) or not isinstance(gen, (int, float)):
        raise ValueError(f"Forecast generation must be numeric, got {type(gen).__name__}: {gen!r}")

    return {
        "dataset": record.get("dataset", "WINDFOR"),
        "startTime": format_utc_timestamp(start_dt),
        "publishTime": format_utc_timestamp(pub_dt),
        "startDateTime": start_dt,
        "publishDateTime": pub_dt,
        "settlementDate": record.get("settlementDate"),
        "settlementPeriod": record.get("settlementPeriod"),
        "generation": float(gen),
    }


def select_forecast_at_cutoff(
    records: List[Dict[str, Any]],
    cutoff_time: str,
    target_start_time: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Select the latest forecast vintage published at or prior to the decision cutoff.
    
    Prevents lookahead bias by excluding forecasts with publishTime > decision_cutoff.
    """
    cutoff_dt = parse_iso_timestamp(cutoff_time)
    target_dt = parse_iso_timestamp(target_start_time) if target_start_time else None

    eligible_records = []
    for r in records:
        valid_r = validate_forecast_record(r)
        if target_dt is not None and valid_r["startDateTime"] != target_dt:
            continue
        if valid_r["publishDateTime"] <= cutoff_dt:
            eligible_records.append(valid_r)

    if not eligible_records:
        return None

    eligible_records.sort(key=lambda x: x["publishDateTime"])
    return eligible_records[-1]
