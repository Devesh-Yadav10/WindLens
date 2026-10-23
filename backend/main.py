"""
FastAPI application entry point for WindLens.

Serves verified January 2026 Elexon data and analytics:
- GET /api/health
- GET /api/overview
- GET /api/forecasts?date=YYYY-MM-DD
- GET /api/accuracy?from=YYYY-MM-DD&to=YYYY-MM-DD
- GET /api/accuracy/daily?from=YYYY-MM-DD&to=YYYY-MM-DD
- GET /api/errors?limit=N
- GET /api/export.csv
"""

import csv
import io
import os
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from backend.data_loader import filter_observations, get_data_loader
from backend.schemas import (
    AccuracyMetrics,
    AccuracyQueryResponse,
    DailyAccuracyResponse,
    ForecastDeliveryInterval,
    ForecastsQueryResponse,
    HealthResponse,
    OverviewResponse,
    TopErrorsResponse,
)
from scripts.analytics import calculate_accuracy_metrics, calculate_daily_breakdown, identify_largest_errors

app = FastAPI(
    title="WindLens Energy Analytics API",
    description="High-integrity historical wind generation forecast vs. actual analytics for GB electricity utility.",
    version="1.0.0",
)

# CORS Configuration
allowed_origins_env = os.getenv("WINDLENS_CORS_ORIGINS", "*")
allowed_origins = [o.strip() for o in allowed_origins_env.split(",")] if allowed_origins_env else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_date_format(d_str: Optional[str], param_name: str) -> None:
    if d_str and not DATE_REGEX.match(d_str):
        raise HTTPException(status_code=400, detail=f"Invalid format for '{param_name}'. Expected YYYY-MM-DD.")


@app.get("/api/health", response_model=HealthResponse)
def health_check():
    """Service health and dataset status."""
    loader = get_data_loader()
    return HealthResponse(
        status="ok",
        version="1.0.0",
        timestamp_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        dataset_period="2026-01",
        total_observations_available=len(loader["matched_observations"]),
    )


@app.get("/api/overview", response_model=OverviewResponse)
def get_overview():
    """January 2026 monthly overview KPIs, coverage, and executive findings."""
    loader = get_data_loader()
    obs = loader["matched_observations"]
    summary = loader["summary"]
    metrics_dict = summary["monthly_metrics"]

    key_findings = [
        "Analyzed 743 out of 744 hourly delivery intervals across January 2026 (99.87% data completeness).",
        f"Mean Absolute Error (MAE) was {metrics_dict['mae_mw']} MW (18.34% of average generation).",
        f"Persistent positive bias (+{metrics_dict['mbe_mw']} MW MBE) indicates consistent over-forecasting of GB wind power at Day-Ahead gate closure.",
        "Peak over-forecast error reached +6,833 MW on January 12, 2026 (15.5h lead time)."
    ]

    return OverviewResponse(
        period="2026-01-01 to 2026-01-31",
        cutoff_policy="Day-Ahead D-1 11:00:00Z (UK EPEX SPOT / Nord Pool Auction Gate Closure)",
        expected_intervals=744,
        matched_intervals=len(obs),
        coverage_percentage=round(len(obs) / 744.0 * 100.0, 2),
        metrics=AccuracyMetrics(**metrics_dict),
        key_findings=key_findings,
    )


@app.get("/api/forecasts", response_model=ForecastsQueryResponse)
def get_forecasts(date: str = Query("2026-01-15", description="Target delivery date in format YYYY-MM-DD")):
    """Hourly delivery interval time-series comparing forecast vs. actual for a specific date."""
    validate_date_format(date, "date")
    filtered = filter_observations(from_date=date, to_date=date)

    if not filtered:
        raise HTTPException(
            status_code=404,
            detail=f"No observations found for date '{date}'. Available period is 2026-01-01 to 2026-01-31."
        )

    coverage = round(len(filtered) / 24.0 * 100.0, 1)
    return ForecastsQueryResponse(
        date=date,
        observation_count=len(filtered),
        expected_count=24,
        coverage_percent=coverage,
        data=[ForecastDeliveryInterval(**r) for r in filtered],
    )


@app.get("/api/accuracy", response_model=AccuracyQueryResponse)
def get_accuracy_metrics(
    from_date: str = Query("2026-01-01", alias="from", description="Start date YYYY-MM-DD"),
    to_date: str = Query("2026-01-31", alias="to", description="End date YYYY-MM-DD"),
):
    """Calculate aggregated forecast accuracy metrics over a flexible date range."""
    validate_date_format(from_date, "from")
    validate_date_format(to_date, "to")

    if from_date > to_date:
        raise HTTPException(status_code=400, detail="'from' date cannot be after 'to' date.")

    filtered = filter_observations(from_date=from_date, to_date=to_date)
    if not filtered:
        raise HTTPException(status_code=404, detail=f"No data available in range {from_date} to {to_date}.")

    metrics = calculate_accuracy_metrics(filtered, min_actual_for_mape=100.0)
    return AccuracyQueryResponse(
        from_date=from_date,
        to_date=to_date,
        observation_count=len(filtered),
        metrics=AccuracyMetrics(**metrics),
    )


@app.get("/api/accuracy/daily", response_model=DailyAccuracyResponse)
def get_daily_accuracy(
    from_date: str = Query("2026-01-01", alias="from", description="Start date YYYY-MM-DD"),
    to_date: str = Query("2026-01-31", alias="to", description="End date YYYY-MM-DD"),
):
    """Daily breakdown of MAE, RMSE, MBE, and generation outturns."""
    validate_date_format(from_date, "from")
    validate_date_format(to_date, "to")

    if from_date > to_date:
        raise HTTPException(status_code=400, detail="'from' date cannot be after 'to' date.")

    filtered = filter_observations(from_date=from_date, to_date=to_date)
    daily = calculate_daily_breakdown(filtered)

    return DailyAccuracyResponse(
        from_date=from_date,
        to_date=to_date,
        total_days=len(daily),
        daily_breakdown=daily,
    )


@app.get("/api/errors", response_model=TopErrorsResponse)
def get_top_errors(limit: int = Query(10, ge=1, le=100, description="Number of peak errors to return")):
    """Identify the largest absolute forecast error intervals."""
    loader = get_data_loader()
    obs = loader["matched_observations"]
    top_records = identify_largest_errors(obs, top_n=limit)
    return TopErrorsResponse(
        limit=limit,
        count=len(top_records),
        largest_errors=top_records,
    )


@app.get("/api/export.csv")
def export_csv(
    from_date: Optional[str] = Query(None, alias="from", description="Filter start date"),
    to_date: Optional[str] = Query(None, alias="to", description="Filter end date"),
):
    """Download verified hourly observations as CSV."""
    validate_date_format(from_date, "from")
    validate_date_format(to_date, "to")

    filtered = filter_observations(from_date=from_date, to_date=to_date)

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "startTime",
            "settlementDate",
            "publishTime",
            "cutoffTime",
            "lead_time_hours",
            "forecast_mw",
            "actual_mw",
            "actual_hh1_mw",
            "actual_hh2_mw",
            "error_mw",
            "abs_error_mw",
        ],
        extrasaction="ignore",
    )
    writer.writeheader()
    writer.writerows(filtered)
    output.seek(0)

    filename = f"windlens_january_2026_{from_date or 'all'}_to_{to_date or 'all'}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

