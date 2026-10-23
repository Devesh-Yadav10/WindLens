"""
Pydantic schemas for the WindLens FastAPI backend.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., description="Service health status, e.g. 'ok'")
    version: str = Field("1.0.0", description="API version")
    timestamp_utc: str = Field(..., description="Current server UTC timestamp")
    dataset_period: str = Field("2026-01", description="Target historical dataset period")
    total_observations_available: int = Field(..., description="Total verified hourly matched intervals")


class AccuracyMetrics(BaseModel):
    observation_count: int
    mae_mw: Optional[float] = Field(None, description="Mean Absolute Error in MW")
    nmae_percent: Optional[float] = Field(None, description="Normalized MAE as % of mean generation")
    rmse_mw: Optional[float] = Field(None, description="Root Mean Squared Error in MW")
    mbe_mw: Optional[float] = Field(None, description="Mean Bias Error in MW (positive = over-forecast)")
    mape_percent: Optional[float] = Field(None, description="Mean Absolute Percentage Error (actuals >= 100 MW)")
    mean_actual_mw: Optional[float] = Field(None, description="Mean actual wind generation in MW")
    mean_forecast_mw: Optional[float] = Field(None, description="Mean day-ahead wind forecast in MW")
    valid: bool


class OverviewResponse(BaseModel):
    period: str
    cutoff_policy: str
    expected_intervals: int
    matched_intervals: int
    coverage_percentage: float
    metrics: AccuracyMetrics
    key_findings: List[str]


class ForecastDeliveryInterval(BaseModel):
    startTime: str
    settlementDate: str
    publishTime: Optional[str]
    cutoffTime: Optional[str]
    lead_time_hours: Optional[float]
    forecast_mw: float
    actual_mw: float
    actual_hh1_mw: Optional[float]
    actual_hh2_mw: Optional[float]
    error_mw: float
    abs_error_mw: float


class ForecastsQueryResponse(BaseModel):
    date: str
    observation_count: int
    expected_count: int = 24
    coverage_percent: float
    data: List[ForecastDeliveryInterval]


class DailyMetric(BaseModel):
    date: str
    observation_count: int
    expected_count: int = 24
    coverage_percent: float
    mae_mw: Optional[float]
    rmse_mw: Optional[float]
    mbe_mw: Optional[float]
    mape_percent: Optional[float]
    mean_actual_mw: Optional[float]
    mean_forecast_mw: Optional[float]


class AccuracyQueryResponse(BaseModel):
    from_date: str
    to_date: str
    observation_count: int
    metrics: AccuracyMetrics


class DailyAccuracyResponse(BaseModel):
    from_date: str
    to_date: str
    total_days: int
    daily_breakdown: List[DailyMetric]


class ErrorRecord(BaseModel):
    startTime: str
    publishTime: Optional[str]
    lead_time_hours: Optional[float]
    forecast_mw: float
    actual_mw: float
    error_mw: float
    abs_error_mw: float
    direction: str


class TopErrorsResponse(BaseModel):
    limit: int
    count: int
    largest_errors: List[ErrorRecord]

