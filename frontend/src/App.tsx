import { useEffect, useState } from 'react';
import {
  Wind,
  TrendingUp,
  AlertTriangle,
  Download,
  Calendar,
  Layers,
  HelpCircle,
  Activity,
  ArrowUpRight,
  ShieldCheck,
  CheckCircle2,
  Loader2
} from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  BarChart,
  Bar,
  ReferenceLine
} from 'recharts';

import {
  fetchOverview,
  fetchForecasts,
  fetchDailyAccuracy,
  fetchTopErrors,
  getExportUrl
} from './api';
import type {
  OverviewData,
  ForecastsResponse,
  DailyAccuracyResponse,
  TopErrorsResponse
} from './types';

export default function App() {
  const [selectedDate, setSelectedDate] = useState('2026-01-15');
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [forecasts, setForecasts] = useState<ForecastsResponse | null>(null);
  const [dailyAccuracy, setDailyAccuracy] = useState<DailyAccuracyResponse | null>(null);
  const [topErrors, setTopErrors] = useState<TopErrorsResponse | null>(null);
  const [activeTab, setActiveTab] = useState<'explorer' | 'accuracy' | 'table' | 'methodology'>('explorer');
  const [loading, setLoading] = useState(true);
  const [forecastLoading, setForecastLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load overview, daily trends, and top errors once
  useEffect(() => {
    async function loadInitialData() {
      try {
        setLoading(true);
        const [ovData, dailyData, errData] = await Promise.all([
          fetchOverview(),
          fetchDailyAccuracy('2026-01-01', '2026-01-31'),
          fetchTopErrors(10)
        ]);
        setOverview(ovData);
        setDailyAccuracy(dailyData);
        setTopErrors(errData);
      } catch (err: any) {
        setError(err.message || 'Error loading dashboard data');
      } finally {
        setLoading(false);
      }
    }
    loadInitialData();
  }, []);

  // Load hourly forecasts whenever selectedDate changes
  useEffect(() => {
    async function loadDateForecasts() {
      try {
        setForecastLoading(true);
        const fcData = await fetchForecasts(selectedDate);
        setForecasts(fcData);
      } catch (err: any) {
        console.error('Forecast load error:', err);
      } finally {
        setForecastLoading(false);
      }
    }
    loadDateForecasts();
  }, [selectedDate]);

  const formatMW = (val?: number | null) => (val != null ? `${val.toLocaleString()} MW` : 'N/A');
  const formatPercent = (val?: number | null) => (val != null ? `${val.toFixed(1)}%` : 'N/A');

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-serif">
      {/* Top Header */}
      <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-teal-500/10 border border-teal-500/30 flex items-center justify-center text-teal-400">
              <Wind className="w-6 h-6 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold tracking-tight text-white font-serif">WindLens</h1>
                <span className="text-xs font-bold px-2 py-0.5 rounded bg-teal-500/20 text-teal-300 border border-teal-500/30 font-serif">
                  GB Utility Analytics
                </span>
              </div>
              <p className="text-xs text-slate-400 font-normal">Day-Ahead Wind Generation Forecast vs. Actual Imbalance</p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-2 bg-slate-800/80 border border-slate-700/60 rounded-md px-3 py-1.5 text-xs text-slate-300 font-medium">
              <Calendar className="w-4 h-4 text-teal-400" />
              <span>Target Month:</span>
              <span className="font-bold text-white">January 2026</span>
            </div>

            <a
              href={getExportUrl('2026-01-01', '2026-01-31')}
              download
              className="flex items-center gap-2 bg-teal-600 hover:bg-teal-500 text-white text-xs font-bold px-3 py-2 rounded-md transition shadow-sm cursor-pointer font-serif"
            >
              <Download className="w-4 h-4" />
              Export CSV
            </a>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {loading && (
          <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg flex items-center gap-3 text-sm text-teal-400">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span className="font-medium">Connecting to Elexon analytics backend...</span>
          </div>
        )}

        {error && (
          <div className="p-4 bg-red-900/30 border border-red-700/50 rounded-lg text-red-200 flex items-center gap-3 text-sm">
            <AlertTriangle className="w-5 h-5 flex-shrink-0 text-red-400" />
            <span className="font-medium">{error}</span>
          </div>
        )}

        {/* Executive KPI Overview Cards */}
        <section className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 flex flex-col justify-between shadow-sm">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider font-serif">MAE (Mean Error)</span>
            <div className="mt-2 text-2xl md:text-3xl font-extrabold text-white tracking-tight font-serif">
              {formatMW(overview?.metrics.mae_mw)}
            </div>
            <span className="text-xs text-slate-400 mt-1 font-normal">Mean Absolute Error</span>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 flex flex-col justify-between shadow-sm">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider font-serif">Normalized MAE</span>
            <div className="mt-2 text-2xl md:text-3xl font-extrabold text-teal-400 tracking-tight font-serif">
              {formatPercent(overview?.metrics.nmae_percent)}
            </div>
            <span className="text-xs text-slate-400 mt-1 font-normal">% of Mean Outturn</span>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 flex flex-col justify-between shadow-sm">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider font-serif">RMSE (Volatility)</span>
            <div className="mt-2 text-2xl md:text-3xl font-extrabold text-white tracking-tight font-serif">
              {formatMW(overview?.metrics.rmse_mw)}
            </div>
            <span className="text-xs text-slate-400 mt-1 font-normal">Penalizes large swings</span>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 flex flex-col justify-between shadow-sm">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider font-serif">MBE (System Bias)</span>
            <div className="mt-2 text-2xl md:text-3xl font-extrabold text-amber-400 tracking-tight flex items-center gap-1 font-serif">
              +{formatMW(overview?.metrics.mbe_mw)}
            </div>
            <span className="text-xs font-semibold text-amber-400/90 mt-1 flex items-center gap-1">
              <ArrowUpRight className="w-3.5 h-3.5" /> Over-forecast Bias
            </span>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 flex flex-col justify-between shadow-sm">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider font-serif">Mean Outturn</span>
            <div className="mt-2 text-2xl md:text-3xl font-extrabold text-white tracking-tight font-serif">
              {formatMW(overview?.metrics.mean_actual_mw)}
            </div>
            <span className="text-xs text-slate-400 mt-1 font-normal">Actual Wind Generation</span>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 flex flex-col justify-between shadow-sm">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider font-serif">Coverage</span>
            <div className="mt-2 text-2xl md:text-3xl font-extrabold text-emerald-400 tracking-tight flex items-center gap-1 font-serif">
              {formatPercent(overview?.coverage_percentage)}
            </div>
            <span className="text-xs text-slate-400 mt-1 font-normal">743 / 744 Hours Matched</span>
          </div>
        </section>

        {/* Navigation Tabs */}
        <div className="flex border-b border-slate-800 space-x-2 text-sm font-semibold">
          <button
            onClick={() => setActiveTab('explorer')}
            className={`pb-3 px-3 transition border-b-2 flex items-center gap-2 cursor-pointer font-serif ${
              activeTab === 'explorer'
                ? 'border-teal-400 text-teal-400 font-bold'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Activity className="w-4 h-4" />
            Forecast Explorer
          </button>
          <button
            onClick={() => setActiveTab('accuracy')}
            className={`pb-3 px-3 transition border-b-2 flex items-center gap-2 cursor-pointer font-serif ${
              activeTab === 'accuracy'
                ? 'border-teal-400 text-teal-400 font-bold'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <TrendingUp className="w-4 h-4" />
            Accuracy & Trends
          </button>
          <button
            onClick={() => setActiveTab('table')}
            className={`pb-3 px-3 transition border-b-2 flex items-center gap-2 cursor-pointer font-serif ${
              activeTab === 'table'
                ? 'border-teal-400 text-teal-400 font-bold'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Layers className="w-4 h-4" />
            Delivery Intervals Table
          </button>
          <button
            onClick={() => setActiveTab('methodology')}
            className={`pb-3 px-3 transition border-b-2 flex items-center gap-2 cursor-pointer font-serif ${
              activeTab === 'methodology'
                ? 'border-teal-400 text-teal-400 font-bold'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <HelpCircle className="w-4 h-4" />
            Methodology & Provenance
          </button>
        </div>

        {/* TAB 1: Forecast Explorer */}
        {activeTab === 'explorer' && (
          <section className="space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <h2 className="text-lg font-bold text-white flex items-center gap-2 font-serif">
                    Hourly Day-Ahead Forecast vs. Actual Generation
                  </h2>
                  <p className="text-xs text-slate-400 mt-0.5 font-normal">
                    Viewing Day-Ahead 11:00 UTC cutoff forecast against averaged 30-minute outturn
                  </p>
                </div>

                <div className="flex items-center gap-3">
                  <label htmlFor="date-picker" className="text-xs font-bold text-slate-300 font-serif">
                    Delivery Day:
                  </label>
                  <input
                    id="date-picker"
                    type="date"
                    min="2026-01-01"
                    max="2026-01-31"
                    value={selectedDate}
                    onChange={(e) => setSelectedDate(e.target.value)}
                    className="bg-slate-800 border border-slate-700 text-slate-100 font-semibold rounded-md px-3 py-1.5 text-xs focus:ring-1 focus:ring-teal-500 outline-none cursor-pointer font-serif"
                  />
                </div>
              </div>

              {forecastLoading ? (
                <div className="h-80 flex items-center justify-center text-slate-500 text-sm font-medium">
                  Loading hourly timeseries for {selectedDate}...
                </div>
              ) : forecasts && forecasts.data.length > 0 ? (
                <div className="h-80 w-full pt-2">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={forecasts.data}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis
                        dataKey="startTime"
                        tickFormatter={(ts) => ts.substring(11, 16)}
                        stroke="#64748b"
                        fontSize={11}
                        style={{ fontFamily: '"Times New Roman", Times, serif' }}
                      />
                      <YAxis
                        stroke="#64748b"
                        fontSize={11}
                        style={{ fontFamily: '"Times New Roman", Times, serif' }}
                        tickFormatter={(v) => `${(v / 1000).toFixed(1)}k`}
                        label={{ value: 'Generation (MW)', angle: -90, position: 'insideLeft', fill: '#64748b', fontSize: 11, style: { fontFamily: '"Times New Roman", Times, serif' } }}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#0f172a',
                          borderColor: '#334155',
                          borderRadius: '0.375rem',
                          fontSize: '12px',
                          fontFamily: '"Times New Roman", Times, serif'
                        }}
                        formatter={(val: any, name: any) => [`${Number(val).toLocaleString()} MW`, name]}
                        labelFormatter={(lbl: any) => `Interval: ${String(lbl).substring(0, 16).replace('T', ' ')} UTC`}
                      />
                      <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '10px', fontFamily: '"Times New Roman", Times, serif', fontWeight: 600 }} />
                      <Line
                        type="monotone"
                        dataKey="forecast_mw"
                        name="Day-Ahead Forecast (MW)"
                        stroke="#2dd4bf"
                        strokeWidth={2}
                        dot={{ r: 2 }}
                        activeDot={{ r: 5 }}
                      />
                      <Line
                        type="monotone"
                        dataKey="actual_mw"
                        name="Actual Generation (MW)"
                        stroke="#38bdf8"
                        strokeWidth={2}
                        dot={{ r: 2 }}
                        activeDot={{ r: 5 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="h-80 flex items-center justify-center text-slate-500 text-sm">
                  No data available for {selectedDate}
                </div>
              )}
            </div>

            {/* Daily Error Sub-Chart */}
            {forecasts && forecasts.data.length > 0 && (
              <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
                <h3 className="text-base font-bold text-slate-200 mb-2 font-serif">
                  Hourly Forecast Error (Forecast − Actual) on {selectedDate}
                </h3>
                <div className="h-44 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={forecasts.data}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis
                        dataKey="startTime"
                        tickFormatter={(ts) => ts.substring(11, 16)}
                        stroke="#64748b"
                        fontSize={10}
                        style={{ fontFamily: '"Times New Roman", Times, serif' }}
                      />
                      <YAxis
                        stroke="#64748b"
                        fontSize={10}
                        tickFormatter={(v) => `${v} MW`}
                        style={{ fontFamily: '"Times New Roman", Times, serif' }}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#0f172a',
                          borderColor: '#334155',
                          borderRadius: '0.375rem',
                          fontSize: '11px',
                          fontFamily: '"Times New Roman", Times, serif'
                        }}
                        formatter={(val: any) => [`${Number(val).toLocaleString()} MW`, 'Error']}
                        labelFormatter={(lbl: any) => `Interval: ${String(lbl).substring(11, 16)} UTC`}
                      />
                      <ReferenceLine y={0} stroke="#475569" />
                      <Bar
                        dataKey="error_mw"
                        name="Error (MW)"
                        fill="#f59e0b"
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </section>
        )}

        {/* TAB 2: Accuracy & Trends */}
        {activeTab === 'accuracy' && (
          <section className="space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-4">
              <h2 className="text-lg font-bold text-white font-serif">
                Daily Mean Absolute Error (MAE) Trend — January 2026
              </h2>
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={dailyAccuracy?.daily_breakdown || []}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis
                      dataKey="date"
                      tickFormatter={(d) => d.substring(8, 10)}
                      stroke="#64748b"
                      fontSize={11}
                      style={{ fontFamily: '"Times New Roman", Times, serif' }}
                    />
                    <YAxis
                      stroke="#64748b"
                      fontSize={11}
                      tickFormatter={(v) => `${(v / 1000).toFixed(1)}k`}
                      style={{ fontFamily: '"Times New Roman", Times, serif' }}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#0f172a',
                        borderColor: '#334155',
                        borderRadius: '0.375rem',
                        fontSize: '12px',
                        fontFamily: '"Times New Roman", Times, serif'
                      }}
                      formatter={(val: any, name: any) => [`${Number(val).toLocaleString()} MW`, name]}
                      labelFormatter={(lbl: any) => `Date: ${lbl}`}
                    />
                    <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '8px', fontFamily: '"Times New Roman", Times, serif', fontWeight: 600 }} />
                    <Bar dataKey="mae_mw" name="Daily MAE (MW)" fill="#2dd4bf" radius={[2, 2, 0, 0]} />
                    <Bar dataKey="mbe_mw" name="Daily Bias MBE (MW)" fill="#f59e0b" radius={[2, 2, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Peak Error Events */}
            <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
              <h3 className="text-base font-bold text-white flex items-center gap-2 mb-3 font-serif">
                <AlertTriangle className="w-5 h-5 text-amber-400" />
                Top 10 Largest Forecast Imbalance Errors
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-300 font-bold uppercase tracking-wider">
                      <th className="py-2.5 px-3">Delivery Interval (UTC)</th>
                      <th className="py-2.5 px-3">Publish Time</th>
                      <th className="py-2.5 px-3">Lead Time</th>
                      <th className="py-2.5 px-3">Forecast (MW)</th>
                      <th className="py-2.5 px-3">Actual (MW)</th>
                      <th className="py-2.5 px-3">Error (MW)</th>
                      <th className="py-2.5 px-3">Classification</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-serif">
                    {topErrors?.largest_errors.map((err, idx) => (
                      <tr key={idx} className="hover:bg-slate-800/40 transition">
                        <td className="py-2.5 px-3 font-semibold text-slate-200">{err.startTime.replace('T', ' ')}</td>
                        <td className="py-2.5 px-3 text-slate-400">{err.publishTime?.replace('T', ' ') || 'N/A'}</td>
                        <td className="py-2.5 px-3 font-semibold text-slate-300">{err.lead_time_hours}h</td>
                        <td className="py-2.5 px-3 font-bold text-teal-400">{err.forecast_mw.toLocaleString()}</td>
                        <td className="py-2.5 px-3 font-bold text-sky-400">{err.actual_mw.toLocaleString()}</td>
                        <td className={`py-2.5 px-3 font-extrabold ${err.error_mw > 0 ? 'text-amber-400' : 'text-purple-400'}`}>
                          {err.error_mw > 0 ? `+${err.error_mw.toLocaleString()}` : err.error_mw.toLocaleString()}
                        </td>
                        <td className="py-2.5 px-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-wide ${
                            err.direction === 'OVER_FORECAST'
                              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                              : 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                          }`}>
                            {err.direction}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        )}

        {/* TAB 3: Delivery Intervals Table */}
        {activeTab === 'table' && (
          <section className="bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-bold text-white font-serif">Delivery Period Audit Table</h2>
                <p className="text-xs text-slate-400 font-normal">
                  Detailed inspection of verified forecasts, 30-min actuals (HH1 & HH2), and error values for {selectedDate}
                </p>
              </div>
              <input
                type="date"
                min="2026-01-01"
                max="2026-01-31"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                className="bg-slate-800 border border-slate-700 text-slate-100 font-semibold rounded-md px-3 py-1.5 text-xs focus:ring-1 focus:ring-teal-500 outline-none cursor-pointer self-start sm:self-auto font-serif"
              />
            </div>

            <div className="overflow-x-auto max-h-[500px]">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="sticky top-0 bg-slate-900 border-b border-slate-800 text-slate-300 font-bold uppercase tracking-wider z-10">
                  <tr>
                    <th className="py-2.5 px-3">Hour Start (UTC)</th>
                    <th className="py-2.5 px-3">Publish Time</th>
                    <th className="py-2.5 px-3">Day-Ahead Forecast</th>
                    <th className="py-2.5 px-3">Actual HH1 (:00)</th>
                    <th className="py-2.5 px-3">Actual HH2 (:30)</th>
                    <th className="py-2.5 px-3">Avg Actual</th>
                    <th className="py-2.5 px-3">Error (MW)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-serif">
                  {forecasts?.data.map((r, i) => (
                    <tr key={i} className="hover:bg-slate-800/30 transition">
                      <td className="py-2 px-3 font-semibold text-slate-200">{r.startTime.substring(11, 16)}</td>
                      <td className="py-2 px-3 text-slate-400">{r.publishTime?.substring(11, 16) || 'N/A'}</td>
                      <td className="py-2 px-3 text-teal-400 font-bold">{r.forecast_mw.toLocaleString()} MW</td>
                      <td className="py-2 px-3 text-slate-400">{r.actual_hh1_mw?.toLocaleString() || '-'}</td>
                      <td className="py-2 px-3 text-slate-400">{r.actual_hh2_mw?.toLocaleString() || '-'}</td>
                      <td className="py-2 px-3 text-sky-400 font-bold">{r.actual_mw.toLocaleString()} MW</td>
                      <td className={`py-2 px-3 font-extrabold ${r.error_mw > 0 ? 'text-amber-400' : 'text-purple-400'}`}>
                        {r.error_mw > 0 ? `+${r.error_mw.toLocaleString()}` : r.error_mw.toLocaleString()} MW
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {/* TAB 4: Methodology & Data Provenance */}
        {activeTab === 'methodology' && (
          <section className="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-6 text-sm text-slate-300">
            <div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2 mb-2 font-serif">
                <ShieldCheck className="w-5 h-5 text-teal-400" />
                Data Provenance & Analytics Methodology
              </h2>
              <p className="text-slate-400 text-xs font-normal">
                WindLens adheres to strict institutional-grade utility transparency principles. No synthetic records or fabricated metrics are introduced into the analytics pipeline.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-3 bg-slate-950/60 p-4 rounded-lg border border-slate-800/80">
                <h3 className="font-bold text-white flex items-center gap-2 text-sm font-serif">
                  <CheckCircle2 className="w-4 h-4 text-teal-400" />
                  1. Verified Data Sources
                </h3>
                <ul className="list-disc list-inside space-y-1.5 text-xs text-slate-400 font-normal">
                  <li>
                    <strong className="text-slate-200 font-semibold">Actual Outturn:</strong> Elexon BMRS <code className="text-teal-300">/datasets/FUELHH/stream</code> filtered for <code className="text-teal-300">fuelType == 'WIND'</code> (1,488 half-hour settlement periods).
                  </li>
                  <li>
                    <strong className="text-slate-200 font-semibold">Historical Forecasts:</strong> Elexon BMRS <code className="text-teal-300">/forecast/generation/wind/history</code> with original NESO publication timestamps.
                  </li>
                </ul>
              </div>

              <div className="space-y-3 bg-slate-950/60 p-4 rounded-lg border border-slate-800/80">
                <h3 className="font-bold text-white flex items-center gap-2 text-sm font-serif">
                  <CheckCircle2 className="w-4 h-4 text-teal-400" />
                  2. Decision Cutoff Policy
                </h3>
                <p className="text-xs text-slate-400 leading-relaxed font-normal">
                  Decisions are evaluated against the UK Day-Ahead power auction gate closure: <strong className="text-slate-200 font-semibold">11:00 UTC on Day D-1</strong>. The selection logic enforces:
                </p>
                <div className="p-2 bg-slate-900 rounded font-serif text-xs text-teal-300 border border-slate-800 font-semibold">
                  selected_forecast = latest vintage where publishTime &le; D-1 11:00:00Z
                </div>
              </div>

              <div className="space-y-3 bg-slate-950/60 p-4 rounded-lg border border-slate-800/80">
                <h3 className="font-bold text-white flex items-center gap-2 text-sm font-serif">
                  <CheckCircle2 className="w-4 h-4 text-teal-400" />
                  3. Resolution Alignment Semantics
                </h3>
                <p className="text-xs text-slate-400 leading-relaxed font-normal">
                  Actual FUELHH generation is published at 30-minute intervals, whereas WINDFOR national forecasts are issued at hourly resolution (corresponding to settlement period pairs 1-2, 3-4, etc.).
                  The hourly average power outturn is computed as:
                </p>
                <div className="p-2 bg-slate-900 rounded font-serif text-xs text-teal-300 border border-slate-800 font-semibold">
                  Actual_hourly = (Actual_HH1 + Actual_HH2) / 2.0
                </div>
              </div>

              <div className="space-y-3 bg-slate-950/60 p-4 rounded-lg border border-slate-800/80">
                <h3 className="font-bold text-white flex items-center gap-2 text-sm font-serif">
                  <CheckCircle2 className="w-4 h-4 text-teal-400" />
                  4. Known Coverage & Caveats
                </h3>
                <ul className="list-disc list-inside space-y-1.5 text-xs text-slate-400 font-normal">
                  <li>Total hours analyzed: 743 out of 744 (99.87% coverage).</li>
                  <li>Interval 2026-01-31 23:00 UTC did not complete a pair in the query boundary and was safely excluded.</li>
                  <li>Signed error convention: <code className="text-slate-300">Error = Forecast − Actual</code>. Positive error indicates over-forecasting.</li>
                </ul>
              </div>
            </div>
          </section>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 bg-slate-900/60 py-4 mt-auto text-xs text-slate-500 font-serif">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span className="font-medium">WindLens v1.0 • UK Electricity Utility Wind Analytics</span>
          <span className="font-normal">Data Sources: Elexon BMRS Insights Solution (FUELHH & WINDFOR)</span>
        </div>
      </footer>
    </div>
  );
}
