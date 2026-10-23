"""
Elexon Data Inspection Script for WindLens (Phase 1).

Retrieves and validates bounded samples from official Elexon Insights Solution APIs:
- FUELHH actual wind generation (/datasets/FUELHH/stream)
- WINDFOR forecast wind generation (/datasets/WINDFOR/stream)

Distinguishes:
- Successful request
- Successful request with no matching records
- Failed request (HTTP error, timeout, network error)
- Inconclusive historical-data feasibility result
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# Import data validation functions
try:
    from validation import (
        parse_iso_timestamp,
        validate_actual_record,
        validate_forecast_record,
        select_forecast_at_cutoff,
    )
except ImportError:
    # Allow running when scripts/ is not current directory
    sys.path.insert(0, os.path.dirname(__file__))
    from validation import (
        parse_iso_timestamp,
        validate_actual_record,
        validate_forecast_record,
        select_forecast_at_cutoff,
    )

BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"
DEFAULT_TIMEOUT = 10  # seconds


def fetch_elexon_stream(
    dataset: str,
    params: Optional[Dict[str, str]] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> Tuple[str, Optional[List[Dict[str, Any]]], str]:
    """Fetch data from an Elexon stream endpoint.

    Returns:
      (status, data_list, message)
      where status is one of: 'SUCCESS', 'EMPTY', 'FAILED', 'INCONCLUSIVE'
    """
    url = f"{BASE_URL}/datasets/{dataset}/stream"
    if params:
        url += f"?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "WindLens-Feasibility-Inspector/1.0", "Accept": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status_code = response.getcode()
            if status_code != 200:
                return "FAILED", None, f"HTTP status {status_code}"

            raw_bytes = response.read()
            try:
                data = json.loads(raw_bytes.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as err:
                return "FAILED", None, f"JSON decode error: {err}"

            if not isinstance(data, list):
                return "FAILED", None, f"Unexpected response shape: expected list, got {type(data).__name__}"

            if len(data) == 0:
                return "EMPTY", data, f"Request succeeded (HTTP {status_code}) but returned 0 records."

            return "SUCCESS", data, f"Request succeeded (HTTP {status_code}) returning {len(data)} records."

    except urllib.error.HTTPError as http_err:
        return "FAILED", None, f"HTTP Error {http_err.code}: {http_err.reason}"
    except urllib.error.URLError as url_err:
        # Check for network / DNS / sandbox restrictions
        return "INCONCLUSIVE", None, f"Network / URLError (sandbox restriction or connection issue): {url_err.reason}"
    except Exception as exc:
        return "FAILED", None, f"Unexpected error: {exc}"


def inspect_actuals_sample(publish_from: str, publish_to: str) -> None:
    """Inspect sample actual wind generation records (FUELHH)."""
    print("=" * 70)
    print("1. INSPECTING ACTUAL GENERATION DATA (FUELHH)")
    print(f"Target Publish Window: {publish_from} to {publish_to}")
    print("=" * 70)

    params = {
        "publishDateTimeFrom": publish_from,
        "publishDateTimeTo": publish_to,
    }
    status, records, msg = fetch_elexon_stream("FUELHH", params=params)
    print(f"Status: {status}")
    print(f"Details: {msg}")

    if status == "SUCCESS" and records:
        print(f"\nTotal records retrieved: {len(records)}")

        # Filter for WIND fuel type
        wind_records = [r for r in records if r.get("fuelType") == "WIND"]
        fuel_types = sorted(list({r.get("fuelType") for r in records if r.get("fuelType")}))
        print(f"Fuel types present in response: {', '.join(fuel_types)}")
        print(f"Wind records matching 'WIND': {len(wind_records)}")

        if wind_records:
            sample = wind_records[0]
            print("\nVerified FUELHH Schema Fields (Sample Record):")
            for k, v in sample.items():
                print(f"  - {k} ({type(v).__name__}): {v}")

            # Validation check
            try:
                val = validate_actual_record(sample, enforce_wind_fuel=True)
                print(f"\n[Validation PASS] Validated record: startTime={val['startTime']}, gen={val['generation']} MW")
            except Exception as e:
                print(f"\n[Validation FAIL] {e}")
        else:
            print("Note: No records with fuelType == 'WIND' in this specific window sample.")
    elif status == "EMPTY":
        print("Verification outcome: No records returned for this window.")
    else:
        print(f"Verification outcome: Could not retrieve live data ({msg}).")


def inspect_forecast_sample(publish_from: Optional[str] = None, publish_to: Optional[str] = None) -> None:
    """Inspect sample forecast wind generation records (WINDFOR)."""
    print("\n" + "=" * 70)
    print("2. INSPECTING FORECAST GENERATION DATA (WINDFOR)")
    if publish_from and publish_to:
        print(f"Target Publish Window: {publish_from} to {publish_to}")
        params = {"publishDateTimeFrom": publish_from, "publishDateTimeTo": publish_to}
    else:
        print("Target: Latest published stream (no publish date filter)")
        params = None
    print("=" * 70)

    status, records, msg = fetch_elexon_stream("WINDFOR", params=params)
    print(f"Status: {status}")
    print(f"Details: {msg}")

    if status == "SUCCESS" and records:
        print(f"\nTotal records retrieved: {len(records)}")
        sample = records[0]
        print("\nVerified WINDFOR Schema Fields (Sample Record):")
        for k, v in sample.items():
            print(f"  - {k} ({type(v).__name__}): {v}")

        # Check for multiple vintages or delivery horizon
        start_times = [r.get("startTime") for r in records if r.get("startTime")]
        publish_times = [r.get("publishTime") for r in records if r.get("publishTime")]
        unique_starts = set(start_times)
        unique_publishes = set(publish_times)

        print(f"Unique startTimes (delivery periods): {len(unique_starts)}")
        print(f"Unique publishTimes (forecast vintages): {len(unique_publishes)}")
        if start_times:
            print(f"Delivery horizon: {min(start_times)} to {max(start_times)}")
        if publish_times:
            print(f"Publication horizon: {min(publish_times)} to {max(publish_times)}")

        # Check vintage multiplicity: multiple publications for same startTime
        delivery_counts: Dict[str, int] = {}
        for r in records:
            st = r.get("startTime")
            if st:
                delivery_counts[st] = delivery_counts.get(st, 0) + 1

        mult_vintages = {k: v for k, v in delivery_counts.items() if v > 1}
        if mult_vintages:
            print(f"Sample contains multiple forecast vintages for same delivery period: Yes ({len(mult_vintages)} periods)")
        else:
            print("Sample contains single forecast publication per delivery period (e.g. single publication snapshot).")

        # Validate first record
        try:
            val = validate_forecast_record(sample)
            print(f"\n[Validation PASS] Validated record: startTime={val['startTime']}, pubTime={val['publishTime']}, gen={val['generation']} MW")
        except Exception as e:
            print(f"\n[Validation FAIL] {e}")

    elif status == "EMPTY":
        print("Verification outcome: No records returned for this window.")
    else:
        print(f"Verification outcome: Could not retrieve live data ({msg}).")


def test_january_2026_feasibility() -> None:
    """Explicit bounded feasibility check for January 2026 data."""
    print("\n" + "=" * 70)
    print("3. EXPLICIT HISTORICAL DATA FEASIBILITY CHECK: JANUARY 2026")
    print("=" * 70)

    # Test FUELHH for Jan 1, 2026
    print("\n[A] Testing FUELHH (Actuals) for 2026-01-01:")
    f_status, f_records, f_msg = fetch_elexon_stream(
        "FUELHH",
        params={
            "publishDateTimeFrom": "2026-01-01T00:00:00Z",
            "publishDateTimeTo": "2026-01-01T01:00:00Z",
        },
    )
    print(f"  Status: {f_status}")
    print(f"  Details: {f_msg}")
    if f_status == "SUCCESS" and f_records:
        wind = [r for r in f_records if r.get("fuelType") == "WIND"]
        print(f"  Total records: {len(f_records)}, Wind records: {len(wind)}")
        if wind:
            print(f"  Sample Wind Actual: startTime={wind[0].get('startTime')}, gen={wind[0].get('generation')} MW")
            print("  -> RESULT: January 2026 actuals (FUELHH) ARE AVAILABLE and verified.")

    # Test WINDFOR for Jan 1, 2026
    print("\n[B] Testing WINDFOR (Forecasts) for 2026-01-01 (publishDateTime window):")
    w_status, w_records, w_msg = fetch_elexon_stream(
        "WINDFOR",
        params={
            "publishDateTimeFrom": "2026-01-01T00:00:00Z",
            "publishDateTimeTo": "2026-01-01T06:00:00Z",
        },
    )
    print(f"  Status: {w_status}")
    print(f"  Details: {w_msg}")
    if w_status == "EMPTY":
        print("  -> RESULT: WINDFOR stream returns 0 records when queried with historical publishDateTime.")
        print("     Explanation: The /datasets/WINDFOR/stream endpoint serves real-time rolling streams.")
        print("     Documented alternative for historical forecast vintages: /forecast/generation/wind/latest or /history.")
    elif w_status == "SUCCESS" and w_records:
        print(f"  Total forecast records: {len(w_records)}")
    else:
        print(f"  Status: {w_status} ({w_msg})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect Elexon BMRS API for WindLens")
    parser.add_argument("--test-jan-2026", action="store_true", help="Run explicit January 2026 feasibility check")
    args = parser.parse_args()

    print("WindLens Elexon Data Inspection Tool (Phase 1)")
    print("Testing live API endpoints at https://data.elexon.co.uk/bmrs/api/v1\n")

    # 1. Bounded actuals inspection
    inspect_actuals_sample("2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z")

    # 2. Latest forecast stream inspection
    inspect_forecast_sample()

    # 3. January 2026 explicit test
    test_january_2026_feasibility()


if __name__ == "__main__":
    main()

