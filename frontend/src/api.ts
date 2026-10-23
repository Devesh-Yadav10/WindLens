import type {
  OverviewData,
  ForecastsResponse,
  DailyAccuracyResponse,
  TopErrorsResponse,
} from './types';

const API_BASE = '/api';

export async function fetchOverview(): Promise<OverviewData> {
  const res = await fetch(`${API_BASE}/overview`);
  if (!res.ok) throw new Error(`Failed to fetch overview: ${res.statusText}`);
  return res.json();
}

export async function fetchForecasts(date: string): Promise<ForecastsResponse> {
  const res = await fetch(`${API_BASE}/forecasts?date=${encodeURIComponent(date)}`);
  if (!res.ok) throw new Error(`Failed to fetch forecasts for ${date}: ${res.statusText}`);
  return res.json();
}

export async function fetchDailyAccuracy(fromDate: string, toDate: string): Promise<DailyAccuracyResponse> {
  const res = await fetch(`${API_BASE}/accuracy/daily?from=${encodeURIComponent(fromDate)}&to=${encodeURIComponent(toDate)}`);
  if (!res.ok) throw new Error(`Failed to fetch daily accuracy: ${res.statusText}`);
  return res.json();
}

export async function fetchTopErrors(limit: number = 10): Promise<TopErrorsResponse> {
  const res = await fetch(`${API_BASE}/errors?limit=${limit}`);
  if (!res.ok) throw new Error(`Failed to fetch top errors: ${res.statusText}`);
  return res.json();
}

export function getExportUrl(fromDate?: string, toDate?: string): string {
  const params = new URLSearchParams();
  if (fromDate) params.append('from', fromDate);
  if (toDate) params.append('to', toDate);
  return `${API_BASE}/export.csv?${params.toString()}`;
}

