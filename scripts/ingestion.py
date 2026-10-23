"""Elexon BMRS API ingestion client for FUELHH actuals and WINDFOR forecasts."""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from scripts.validation import (
    format_utc_timestamp,
    parse_iso_timestamp,
    validate_actual_record,
    validate_forecast_record,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"
DEFAULT_TIMEOUT = 20


class ElexonAPIError(Exception):
    """Exception raised when an Elexon API request fails."""
    pass


def execute_request(
    endpoint: str,
    params: Optional[Dict[str, str]] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> Tuple[int, Any]:
    """Execute an HTTP GET request against the Elexon Insights Solution REST API."""
    url = f"{BASE_URL}{endpoint}"
    if params:
        url += f"?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "WindLens/1.0",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status_code = response.getcode()
            raw_bytes = response.read()
            try:
                data = json.loads(raw_bytes.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as err:
                raise ElexonAPIError(f"Failed to decode JSON response from {url}: {err}") from err
            return status_code, data

    except urllib.error.HTTPError as http_err:
        err_body = ""
        try:
            err_body = http_err.read().decode("utf-8")[:200]
        except Exception:
            pass
        raise ElexonAPIError(f"HTTP {http_err.code} from {url}: {http_err.reason} ({err_body})") from http_err
    except urllib.error.URLError as url_err:
        raise ElexonAPIError(f"Network error querying {url}: {url_err.reason}") from url_err
    except Exception as exc:
        raise ElexonAPIError(f"Unexpected error querying {url}: {exc}") from exc


def fetch_actual_wind(
    from_time: str,
    to_time: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> List[Dict[str, Any]]:
    """Retrieve half-hourly generation records from the FUELHH stream endpoint."""
    dt_from = parse_iso_timestamp(from_time)
    dt_to = parse_iso_timestamp(to_time)

    params = {
        "publishDateTimeFrom": format_utc_timestamp(dt_from),
        "publishDateTimeTo": format_utc_timestamp(dt_to),
    }

    _, payload = execute_request("/datasets/FUELHH/stream", params=params, timeout=timeout)

    if not isinstance(payload, list):
        raise ElexonAPIError(f"Expected list response for FUELHH, got {type(payload).__name__}")

    return payload


def normalize_actual_records(raw_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter raw FUELHH records for fuelType == 'WIND' and validate structure."""
    wind_records = []
    for r in raw_records:
        if r.get("fuelType") == "WIND":
            validated = validate_actual_record(r, enforce_wind_fuel=True)
            validated.pop("startDateTime", None)
            validated.pop("publishDateTime", None)
            wind_records.append(validated)

    wind_records.sort(key=lambda x: x["startTime"])
    return wind_records


def fetch_wind_forecasts_latest(
    from_time: str,
    to_time: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> List[Dict[str, Any]]:
    """Retrieve the latest wind generation forecast values for target delivery intervals."""
    dt_from = parse_iso_timestamp(from_time)
    dt_to = parse_iso_timestamp(to_time)

    params = {
        "from": format_utc_timestamp(dt_from),
        "to": format_utc_timestamp(dt_to),
    }

    _, payload = execute_request("/forecast/generation/wind/latest", params=params, timeout=timeout)

    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    elif isinstance(payload, list):
        return payload
    else:
        raise ElexonAPIError(f"Unexpected response structure for forecast latest: {type(payload).__name__}")


def fetch_wind_forecast_history(
    publish_time: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> List[Dict[str, Any]]:
    """Retrieve forecast records published during a specific historical model publication run."""
    pub_dt = parse_iso_timestamp(publish_time)

    params = {
        "publishTime": format_utc_timestamp(pub_dt),
        "format": "json",
    }

    _, payload = execute_request("/forecast/generation/wind/history", params=params, timeout=timeout)

    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    elif isinstance(payload, list):
        return payload
    else:
        raise ElexonAPIError(f"Unexpected response structure for forecast history: {type(payload).__name__}")


def normalize_forecast_records(raw_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate and sort forecast records, retaining distinct publication vintages."""
    normalized = []
    for r in raw_records:
        validated = validate_forecast_record(r)
        validated.pop("startDateTime", None)
        validated.pop("publishDateTime", None)
        normalized.append(validated)

    normalized.sort(key=lambda x: (x["startTime"], x["publishTime"]))
    return normalized
