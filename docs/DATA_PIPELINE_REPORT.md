# Data Pipeline and Quality Report (Phase 2) — WindLens

**Project:** WindLens (Day-ahead wind generation forecast vs. actual analytics)  
**Phase:** Phase 2 (Historical Data Pipeline and Caching)  
**Date:** October 2026  
**Status:** Verification Complete & Data Successfully Cached  

---

## 1. Actual API Endpoint and Verified Parameters

- **Dataset:** Actual Half-Hourly Generation by Fuel Type (`FUELHH`)
- **Official Documentation:** `https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream`
- **Verified Endpoint URL:**
  ```http
  GET https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream
  ```
- **Verified Query Parameters:**
  - `publishDateTimeFrom` (ISO 8601 UTC string, e.g. `2026-01-01T00:00:00Z`): Inclusive start of publish timestamp window.
  - `publishDateTimeTo` (ISO 8601 UTC string, e.g. `2026-01-01T23:59:59Z`): Inclusive end of publish timestamp window.
- **Filtering Behavior:** The stream returns generation records for all active GB fuel categories (`BIOMASS`, `CCGT`, `NUCLEAR`, `WIND`, `SOLAR`, `NPSHYD`, `PS`, `COAL`, `OIL`, `OTHER`). The pipeline strictly normalizes and filters for `fuelType == "WIND"`.

---

## 2. Forecast API Endpoint and Verified Parameters

### Primary Historical Forecast Endpoint (Latest View)
- **Dataset:** Wind Generation Forecast Latest View (`WINDFOR`)
- **Official Documentation:** `https://bmrs.elexon.co.uk/api-documentation/endpoint/forecast/generation/wind/latest`
- **Verified Endpoint URL:**
  ```http
  GET https://data.elexon.co.uk/bmrs/api/v1/forecast/generation/wind/latest
  ```
- **Verified Query Parameters:**
  - `from` (ISO 8601 UTC string, e.g. `2026-01-01T00:00:00Z`): Delivery start interval.
  - `to` (ISO 8601 UTC string, e.g. `2026-02-01T00:00:00Z`): Delivery end interval.
- **Observed Behavior:** Returns wrapped object `{"metadata": {"datasets": ["WINDFOR"]}, "data": [...]}` containing the latest forecast issued for each delivery period.

### Secondary Historical Forecast Endpoint (Vintage History by Publish Run)
- **Official Documentation:** `https://bmrs.elexon.co.uk/api-documentation/endpoint/forecast/generation/wind/history`
- **Verified Endpoint URL:**
  ```http
  GET https://data.elexon.co.uk/bmrs/api/v1/forecast/generation/wind/history?publishTime={publish_time}&format=json
  ```
- **Observed Behavior:** Returns the specific forecast run issued by the System Operator (NESO) at `publishTime`, including target intervals spanning up to Day $D+2$.

### Stream Endpoint Assessment (`/datasets/WINDFOR/stream`)
- **Finding:** The `/datasets/WINDFOR/stream` endpoint serves real-time rolling streams (active 2–3 day horizon) and returns 0 records when passed deep historical January 2026 publication dates. It cannot be used for historical backfilling.

---

## 3. Date Range Successfully Retrieved for Each Dataset

| Dataset | Date Range (UTC) | Endpoints Used | Status |
| :--- | :--- | :--- | :--- |
| **Actuals (FUELHH - Wind)** | `2026-01-01T00:00:00Z` to `2026-01-31T23:59:59Z` | `/datasets/FUELHH/stream` (batched day-by-day) | **100% Retrieved** |
| **Forecasts (WINDFOR - Latest)** | `2026-01-01T00:00:00Z` to `2026-02-01T00:00:00Z` | `/forecast/generation/wind/latest` | **100% Retrieved** |

---

## 4. Actual Record Counts

- **Target Duration:** January 1, 2026 to January 31, 2026 (31 days).
- **Settlement Periods per Day:** 48 half-hour intervals (Great Britain standard).
- **Expected Records:** $31 \times 48 = 1,488$ half-hourly intervals.
- **Actual Records Retrieved:** **1,488 records**.
- **Coverage:** **100.0%**. Every single day (Day 01 through Day 31) returned exactly 48 records of `fuelType == "WIND"`.

---

## 5. Forecast Record Counts and Distinct Publication Counts

- **Forecast Intervals Retrieved:** **745 records** covering `2026-01-01T00:00:00Z` through `2026-02-01T00:00:00Z`.
- **Temporal Resolution:** Hourly forecast intervals (corresponding to settlement periods 1, 3, 5, ..., 47). In GB electricity market operations, NESO WINDFOR baseline national forecasts are issued at hourly resolution covering 30-minute settlement pairs.
- **Original Publication Timestamps:** **Retained in all records**. Every record includes the exact NESO model publication timestamp (`publishTime`), such as `2026-01-01T22:30:00Z` or `2025-12-31T09:30:00Z`.
- **Pre-January Delivery Availability:** Verified. Historical runs published prior to delivery (e.g. `2025-12-31T09:30:00Z` for `2026-01-01` delivery) are retrievable and retain original timestamps.

---

## 6. Duplicate and Missing-Record Observations

- **Actuals (FUELHH):**
  - **Duplicates:** Zero duplicate `(startTime, fuelType)` pairs observed.
  - **Missing Records:** Zero missing periods across January 2026.
- **Forecasts (WINDFOR):**
  - **Duplicates within Latest View:** Zero duplicate `startTime` records in the latest dataset (745 unique hourly timestamps).
  - **Multi-Vintage Multiplicity:** When querying historical publication runs (`/forecast/generation/wind/history`), overlapping delivery intervals exist across sequential publish times. The normalization module preserves both `startTime` and `publishTime` without discarding earlier vintages.
  - **Missing Data Coercion:** Missing periods are never coerced to zero. The validation rules throw explicit validation exceptions if `generation` is absent.

---

## 7. Timestamp and Generation-Unit Findings

- **Timezone:** All timestamps are ISO 8601 UTC (ending in `Z`), normalized to timezone-aware Python `datetime` with `tzinfo=timezone.utc`.
- **Units:**
  - Actual Generation: **Megawatts (MW)** half-hourly average power.
  - Forecast Generation: **Megawatts (MW)** hourly forecasted average power.
  - **Energy Conversion:** In Phase 3, comparing 30-minute actuals to 60-minute forecasts can be accomplished either by aggregating actuals to hourly averages:
    $$\text{Actual}_{\text{hourly}} = \frac{\text{Actual}_{HH_1} + \text{Actual}_{HH_2}}{2}$$
    or by mapping the hourly forecast across both corresponding half-hour settlement periods ($SP_{2k-1}$ and $SP_{2k}$).

---

## 8. API Errors, Rate Limits, and Access Restrictions

- **Authentication:** No API key required. Public access is granted under standard Elexon BMRS Open Data license terms.
- **Rate Limiting:** A 100ms pause between daily batch queries was applied. Zero HTTP 429 (Too Many Requests) or HTTP 5xx errors were encountered.
- **Sandbox Boundary:** Direct socket access from inside the restricted Windows sandbox container was blocked by host sandbox networking policies; commands requiring external internet connectivity to `data.elexon.co.uk` were executed unsandboxed with user authorization.

---

## 9. Availability of Historical Forecast Vintages

- **Verified:** Historical forecast runs retain original `publishTime` values.
- **Decision Cutoff Selection Rule:**
  $$\text{Selected Forecast} = \arg\max_{\text{publishTime} \le \text{cutoff}} \{ \text{Forecast}(\text{startTime}, \text{publishTime}) \}$$
- Verified that Day-Ahead forecasts published prior to decision cutoffs (e.g. 11:00 UTC day-ahead for EPEX SPOT day-ahead auction) are accessible and distinguishable from intra-day revisions.

---

## 10. Go / No-Go Assessment for Phase 3 (Analytics & Metrics)

| Assessment Dimension | Observed Evidence | Verdict |
| :--- | :--- | :--- |
| **Actual Wind Data Completeness** | 1,488 / 1,488 half-hours (100%) verified and cached. | **GO** |
| **Forecast Data Completeness** | 745 / 745 hourly delivery intervals (100%) verified and cached. | **GO** |
| **Vintage & Timestamp Integrity** | Original `publishTime` and `startTime` preserved; UTC normalized. | **GO** |
| **Validation & Failure Handling** | 16 automated tests covering edge cases, invalid data, HTTP errors, and cutoff selection logic passing. | **GO** |
| **Overall Readiness** | Solid, reproducible foundation with verifiable local data caches. | **GO FOR PHASE 3** |

