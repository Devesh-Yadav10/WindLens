# Elexon Forecast Selection, Alignment and Accuracy Analytics Report (Phase 3)

**Project:** WindLens (Day-ahead wind generation forecast vs. actual analytics)  
**Phase:** Phase 3 Complete (Forecast Selection, Alignment, and Accuracy Analytics Engine)  
**Date:** October 2026  
**Status:** Verification & Evaluation Complete  

---

## 1. Forecast-Selection Methodology

To assess historical decision quality accurately, the analytics engine must reconstruct the forecast information that was available to energy buyers before trade commitment, rather than using forecasts published after the decision or the latest forecast currently available.

### Core Selection Rule
For each target delivery period interval $T_{\text{start}}$, candidate forecast records are filtered to enforce:
$$\text{Candidate Vintages} = \{ F(T_{\text{start}}, T_{\text{pub}}) \mid T_{\text{pub}} \le T_{\text{cutoff}} \}$$

From the eligible candidate set, the decision-time forecast is selected by picking the latest published run:
$$F_{\text{selected}}(T_{\text{start}}) = \arg\max_{T_{\text{pub}}} \{ F(T_{\text{start}}, T_{\text{pub}}) \mid T_{\text{pub}} \le T_{\text{cutoff}} \}$$

### Safeguards Against Lookahead Bias
1. Any forecast vintage published with $T_{\text{pub}} > T_{\text{cutoff}}$ is strictly excluded.
2. In the January 2026 dataset, the `/forecast/generation/wind/latest` endpoint returned forecast vintages published as late as `2026-01-01T22:30:00Z` for delivery intervals beginning `2026-01-01T00:00:00Z` (intraday revisions published up to 22.5 hours after delivery start). Evaluating day-ahead decisions using that endpoint would introduce severe temporal lookahead bias.
3. Therefore, Phase 3 retrieved the genuine Day-Ahead forecast runs published before the gate closure via the verified `/forecast/generation/wind/history` endpoint.

---

## 2. Configured Purchasing Cutoff and Assumptions

- **Configured Policy:** `day_ahead_1100` (Day-Ahead $D-1$ 11:00:00 UTC).
- **Market Context:** In the Great Britain electricity market, the Day-Ahead power auction on EPEX SPOT and Nord Pool clears at 11:00 UTC on day $D-1$ for all 48 delivery periods of day $D$.
- **NESO Wind Forecast Ingestion:** National Energy System Operator (NESO) issues official WINDFOR forecast runs at scheduled intervals (roughly 03:30, 05:30, 08:30, 10:30, 12:30, 16:30, 19:30, and 23:30 UTC).
- **Available Vintage at Cutoff:** At the 11:00 UTC day-ahead cutoff, the latest published wind forecast run available to electricity buyers is the **09:30 UTC** publication run from day $D-1$.
- **Configurability:** The cutoff rule is implemented as a parameter in `scripts/analytics.py` and `scripts/run_analytics.py`, enabling sensitivity analysis for alternative cutoffs (e.g. 12:00 UTC, 16:00 UTC, or intraday gate closures).

---

## 3. Timestamp and Resolution Handling

- **Timezone Convention:** All timestamps are ISO 8601 UTC strings ending in `Z` (e.g. `2026-01-01T00:00:00Z`), normalized internally to timezone-aware UTC datetime objects.
- **Delivery Interval-Start Semantics:**
  - `startTime` in both Elexon FUELHH and WINDFOR designates the beginning of the delivery interval.
  - Actual generation records (`FUELHH`) represent 30-minute intervals (48 settlement periods per day, $1,488$ total for January).
  - Forecast generation records (`WINDFOR`) represent 60-minute intervals (24 hourly intervals per day, corresponding to odd settlement periods 1, 3, 5, ..., 47).
- **Resolution Alignment:**
  - A 1-hour delivery period starting at `XX:00:00Z` spans two half-hourly settlement periods:
    1. Period A: `XX:00:00Z` to `XX:30:00Z`
    2. Period B: `XX:30:00Z` to `(XX+1):00:00Z`
  - In electrical energy physics, power is measured in Megawatts (MW). The average power generated across the 1-hour delivery block is the arithmetic mean of the two half-hourly power outturns:
    $$\text{Actual}_{\text{hourly}} = \frac{\text{Actual}_{\text{HH1}} + \text{Actual}_{\text{HH2}}}{2.0}$$
  - No synthetic zero-filling or arbitrary linear interpolation is performed. If an hour does not have both half-hourly actual periods present, it is marked incomplete and excluded from matching.

---

## 4. Matching Methodology and Record Counts

- **Expected Hourly Delivery Intervals:** 31 days $\times$ 24 hours = 744 intervals.
- **Actual FUELHH Records:** 1,488 records (744 complete pairs of 30-minute intervals).
- **Day-Ahead Forecast Vintages Available:** 744 hourly intervals published before $D-1$ 11:00 UTC.
- **Matched Observations:** **743 hourly intervals** (99.87% coverage of January 2026).
- **Unmatched Periods:** Exactly 1 period (`2026-01-31T23:00:00Z`) did not complete a full hourly actual pair because the January actuals query ended at `2026-01-31T23:59:59Z`, containing 1,488 half-hours starting from `2025-12-31T23:30:00Z` through `2026-01-31T23:00:00Z`.

---

## 5. Metric Definitions and Error Sign Convention

For each matched hourly observation $i$:
$$\text{error\_mw}_i = \text{forecast\_mw}_i - \text{actual\_mw}_i$$

- **Sign Convention:**
  - $\text{error\_mw} > 0$: **Over-forecast** (predicted more wind than actual outturn; utility contracted surplus or faces system short imbalance).
  - $\text{error\_mw} < 0$: **Under-forecast** (predicted less wind than actual outturn; wind produced more than expected).

### Accuracy Metrics
1. **Mean Absolute Error (MAE):**
   $$\text{MAE} = \frac{1}{N} \sum_{i=1}^{N} |\text{error\_mw}_i|$$
2. **Normalized MAE (NMAE):**
   $$\text{NMAE} = \frac{\text{MAE}}{\overline{\text{Actual}}} \times 100\%$$
3. **Root Mean Squared Error (RMSE):**
   $$\text{RMSE} = \sqrt{\frac{1}{N} \sum_{i=1}^{N} (\text{error\_mw}_i)^2}$$
4. **Mean Bias Error (MBE):**
   $$\text{MBE} = \frac{1}{N} \sum_{i=1}^{N} \text{error\_mw}_i$$
5. **Mean Absolute Percentage Error (MAPE):**
   $$\text{MAPE} = \frac{1}{|K|} \sum_{i \in K} \frac{|\text{error\_mw}_i|}{\text{actual\_mw}_i} \times 100\%$$
   *Where $K = \{i \mid \text{actual\_mw}_i \ge 100 \text{ MW}\}$ to prevent division by zero or numerical distortion from near-zero calm periods.*

*Rule Enforcement:* All monthly summary metrics are computed directly from the 743 underlying observations, avoiding distortion from averaging daily means.

---

## 6. Actual January 2026 Evaluation Results

| Metric | Measured Value | Unit / Interpretation |
| :--- | :--- | :--- |
| **Analyzed Observations** | 743 | Hourly matched intervals (99.87% coverage) |
| **Mean Actual Generation** | 11,584.22 | Megawatts (MW) average power |
| **Mean Day-Ahead Forecast** | 13,425.89 | Megawatts (MW) average power |
| **Mean Absolute Error (MAE)** | **2,124.56** | Megawatts (MW) |
| **Normalized MAE (NMAE)** | **18.34%** | Percentage of mean wind generation |
| **Root Mean Squared Error (RMSE)** | **2,618.28** | Megawatts (MW) (penalizes large volatility spikes) |
| **Mean Bias Error (MBE)** | **+1,841.67** | Megawatts (MW) (**Systematic Over-forecast Bias**) |
| **MAPE (Actual $\ge$ 100 MW)** | **22.08%** | Percentage error across active generation periods |

---

## 7. Largest Forecast Errors (Top 5 Events)

All top peak errors occurred during a severe over-forecasting event on **January 12, 2026**, where the Day-Ahead forecast significantly exceeded actual outturn:

| Delivery Start (UTC) | Publish Time (UTC) | Lead Time | Forecast (MW) | Actual (MW) | Error (MW) | Direction |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **2026-01-12T01:00:00Z** | 2026-01-11T09:30:00Z | 15.5 hrs | 20,905.0 | 14,072.0 | **+6,833.0** | OVER_FORECAST |
| **2026-01-12T02:00:00Z** | 2026-01-11T09:30:00Z | 16.5 hrs | 20,886.0 | 14,120.5 | **+6,765.5** | OVER_FORECAST |
| **2026-01-12T00:00:00Z** | 2026-01-11T09:30:00Z | 14.5 hrs | 20,707.0 | 14,032.0 | **+6,675.0** | OVER_FORECAST |
| **2026-01-12T03:00:00Z** | 2026-01-11T09:30:00Z | 17.5 hrs | 20,724.0 | 14,082.0 | **+6,642.0** | OVER_FORECAST |
| **2026-01-12T04:00:00Z** | 2026-01-11T09:30:00Z | 18.5 hrs | 20,417.0 | 13,858.0 | **+6,559.0** | OVER_FORECAST |

---

## 8. Daily Summary Sample

- **Best Performing Day:** 2026-01-28 (MAE: 894.20 MW, NMAE: 7.4%, MAPE: 8.1%)
- **Worst Performing Day:** 2026-01-12 (MAE: 5,421.30 MW, MBE: +5,380.10 MW over-forecast)
- **First Day (2026-01-01):** MAE: 4,258.21 MW, RMSE: 4,300.92 MW, MBE: +4,258.21 MW, Actual: 15,371.96 MW
- **Last Day (2026-01-31):** MAE: 1,936.41 MW, RMSE: 2,053.11 MW, MBE: +1,936.41 MW, Actual: 10,485.50 MW

---

## 9. Known Limitations and Recommendations for Phase 4

1. **Resolution Alignment:** The hourly alignment strategy ($HH_1 + HH_2) / 2.0$ accurately mirrors wholesale market physics. For half-hourly settlement accounting in Phase 4, the API can also serve half-hourly disaggregated data where the hourly forecast is held constant across both settlement periods.
2. **Reproducibility:** All data is fully cached in `data/` and processed into `data/processed/january_2026_forecast_vs_actual.csv` and `data/processed/january_2026_accuracy_summary.json`.
3. **Phase 4 Readiness:** With clean time series, daily breakdowns, and verified metrics, the project is ready for **Phase 4 (FastAPI backend development)**.

