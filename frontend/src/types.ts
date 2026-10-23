export interface AccuracyMetrics {
  observation_count: number;
  mae_mw: number | null;
  nmae_percent: number | null;
  rmse_mw: number | null;
  mbe_mw: number | null;
  mape_percent: number | null;
  mean_actual_mw: number | null;
  mean_forecast_mw: number | null;
  valid: boolean;
}

export interface OverviewData {
  period: string;
  cutoff_policy: string;
  expected_intervals: number;
  matched_intervals: number;
  coverage_percentage: number;
  metrics: AccuracyMetrics;
  key_findings: string[];
}

export interface DeliveryInterval {
  startTime: string;
  settlementDate: string;
  publishTime: string | null;
  cutoffTime: string | null;
  lead_time_hours: number | null;
  forecast_mw: number;
  actual_mw: number;
  actual_hh1_mw: number | null;
  actual_hh2_mw: number | null;
  error_mw: number;
  abs_error_mw: number;
}

export interface ForecastsResponse {
  date: string;
  observation_count: number;
  expected_count: number;
  coverage_percent: number;
  data: DeliveryInterval[];
}

export interface DailyMetric {
  date: string;
  observation_count: number;
  expected_count: number;
  coverage_percent: number;
  mae_mw: number | null;
  rmse_mw: number | null;
  mbe_mw: number | null;
  mape_percent: number | null;
  mean_actual_mw: number | null;
  mean_forecast_mw: number | null;
}

export interface DailyAccuracyResponse {
  from_date: string;
  to_date: string;
  total_days: number;
  daily_breakdown: DailyMetric[];
}

export interface ErrorRecord {
  startTime: string;
  publishTime: string | null;
  lead_time_hours: number | null;
  forecast_mw: number;
  actual_mw: number;
  error_mw: number;
  abs_error_mw: number;
  direction: 'OVER_FORECAST' | 'UNDER_FORECAST';
}

export interface TopErrorsResponse {
  limit: number;
  count: number;
  largest_errors: ErrorRecord[];
}

