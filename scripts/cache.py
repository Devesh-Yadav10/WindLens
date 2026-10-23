"""
Data caching module for WindLens (Phase 2).

Provides utilities to read and write cached JSON datasets with structured metadata.
Stored datasets:
- data/actuals_2026_01.json
- data/forecasts_2026_01.json

Features:
- Structured provenance and retrieval metadata
- Distinguishes empty successful responses from failed requests
- Reproducible cache writing and validation
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def build_cache_payload(
    dataset_name: str,
    source_endpoint: str,
    parameters: Dict[str, Any],
    records: List[Dict[str, Any]],
    date_range: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Construct a cache envelope containing retrieval metadata and payload records."""
    return {
        "metadata": {
            "dataset": dataset_name,
            "source_endpoint": source_endpoint,
            "retrieved_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "query_parameters": parameters,
            "date_range": date_range or {},
            "record_count": len(records),
            "status": "SUCCESS",
            "is_empty": len(records) == 0,
        },
        "data": records,
    }


def save_json_cache(filepath: str, payload: Dict[str, Any]) -> str:
    """Save payload dict to a JSON file, creating parent directories if needed."""
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return filepath


def load_json_cache(filepath: str) -> Dict[str, Any]:
    """Load cached dataset from a JSON file.

    Raises FileNotFoundError if file does not exist,
    or ValueError if file content is malformed or invalid JSON.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Cache file not found at {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        try:
            payload = json.load(f)
        except Exception as exc:
            raise ValueError(f"Malformed JSON in cache file {filepath}: {exc}") from exc

    if not isinstance(payload, dict) or "metadata" not in payload or "data" not in payload:
        raise ValueError(f"Cache envelope invalid in {filepath}: missing 'metadata' or 'data'")

    return payload

