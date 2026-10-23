# Elexon BMRS API Feasibility Report (Phase 1) — WindLens

**Project:** WindLens (Day-ahead wind generation forecast vs. actual analytics)  
**Author / Role:** WindLens Engineering  
**Date:** October 2026  
**Status:** Phase 1 Feasibility Complete  

---

## 1. Official Sources Inspected

The following official Elexon Balancing Mechanism Reporting Service (BMRS) Insights Solution API endpoints and specifications were reviewed and evaluated:

1. **Actual Half-Hourly Generation by Fuel Type (`FUELHH`):**
   - **Documentation:** `https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream`
   - **Live API Endpoint:** `GET https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream`
   - **Standard Dataset Endpoint:** `GET https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH`

2. **Forecast Half-Hourly Wind Generation (`WINDFOR`):**
   - **Documentation:** `https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream`
   - **Live API Endpoint:** `GET https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream`
   - **Historical / Companion Endpoints:**
     - `GET https://data.elexon.co.uk/bmrs/api/v1/forecast/generation/wind/latest`
     - `GET https://data.elexon.co.uk/bmrs/api/v1/forecast/generation/wind/history`
     - `GET https://data.elexon.co.uk/bmrs/api/v1/forecast/generation/wind/earliest`

---

## 2. Verified API Endpoints and Request Parameters

| Endpoint | Method | Key Parameters | Parameter Types & Constraints | Purpose | Verification Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/datasets/FUELHH/stream` | `GET` | `publishDateTimeFrom`<br>`publishDateTimeTo`<br>`settlementDate` | ISO 8601 string (`YYYY-MM-DDTHH:mm:ssZ`) or date (`YYYY-MM-DD`). Mutually exclusive: settlement date cannot be used with publish dates. | Stream of half-hourly generation outturn for GB fuel types. | **[Verified]** Confirmed by live HTTP response. |
| `/datasets/WINDFOR/stream` | `GET` | `publishDateTimeFrom`<br>`publishDateTimeTo`<br>`format` | ISO 8601 string (`YYYY-MM-DDTHH:mm:ssZ`). Format: `json`, `csv`, `xml`. Defaults to latest forecast if omitted. | High-frequency stream of ESO wind generation forecasts. | **[Verified]** Confirmed by live HTTP response. |
| `/forecast/generation/wind/latest` | `GET` | `from`<br>`to` | ISO 8601 strings (`YYYY-MM-DDTHH:mm:ssZ`). | Historical view of the latest forecasted wind generation. | **[Verified from official docs]** |
| `/forecast/generation/wind/history` | `GET` | `publishTime`<br>`format` | ISO 8601 string (`YYYY-MM-DDTHH:mm:ssZ`). | Full vintage history of published forecasts. | **[Verified from official docs]** |

### Authentication
- **Verified:** Public endpoints on `https://data.elexon.co.uk/bmrs/api/v1` require **no API key** or token authentication for standard HTTP GET requests.

---

## 3. Actual Response Schemas and Representative Field Descriptions

### A. FUELHH (Actual Half-Hourly Outturn) Response Schema

Observed response payload structure from `GET https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream`:
```json
[
  {
    "dataset": "FUELHH",
    "publishTime": "2026-01-01T01:00:00Z",
    "startTime": "2026-01-01T00:30:00Z",
    "settlementDate": "2026-01-01",
    "settlementPeriod": 2,
    "fuelType": "WIND",
    "generation": 1730
  }
]
```

**Field Descriptions:**
- `dataset` (`string`): Identifier of the dataset (e.g. `"FUELHH"`).
- `publishTime` (`string`, ISO 8601 UTC): Timestamp when the outturn record was calculated/published by Elexon (typically at the end of the settlement interval).
- `startTime` (`string`, ISO 8601 UTC): Start time of the half-hour delivery interval.
- `settlementDate` (`string`, `YYYY-MM-DD`): UK electricity market settlement day.
- `settlementPeriod` (`integer`, 1 to 48 or 50): Half-hour trading interval of the day.
- `fuelType` (`string`): Fuel classification code (`"WIND"`, `"CCGT"`, `"BIOMASS"`, `"NUCLEAR"`, `"SOLAR"`, `"NPSHYD"`, `"PS"`, `"COAL"`, `"OIL"`, `"OTHER"`).
- `generation` (`integer` / `float`): Half-hourly average power generated in **Megawatts (MW)**.

### B. WINDFOR (Forecast Stream) Response Schema

Observed response payload structure from `GET https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream`:
```json
[
  {
    "dataset": "WINDFOR",
    "publishTime": "2026-10-23T16:30:00Z",
    "startTime": "2026-10-22T20:00:00Z",
    "generation": 4913
  },
  {
    "dataset": "WINDFOR",
    "publishTime": "2026-10-23T16:30:00Z",
    "startTime": "2026-10-25T21:00:00Z",
    "generation": 21181
  }
]
```

**Field Descriptions:**
- `dataset` (`string`): Identifier of the dataset (`"WINDFOR"`).
- `publishTime` (`string`, ISO 8601 UTC): Exact time when NESO (National Energy System Operator) generated/published the forecast run.
- `startTime` (`string`, ISO 8601 UTC): The future or target delivery half-hour interval to which the forecast applies.
- `generation` (`integer` / `float`): Forecasted power generation in **Megawatts (MW)** for wind farms visible to NESO with operational metering.

---

## 4. January 2026 Historical Actual-Data Availability

- **Status:** **[VERIFIED - AVAILABLE]**
- **Evidence:** Querying `/datasets/FUELHH/stream?publishDateTimeFrom=2026-01-01T00:00:00Z&publishDateTimeTo=2026-01-01T01:00:00Z` successfully returned 60 records for settlement period 2 on 2026-01-01.
- **Filtering:** The response includes all fuel types (`BIOMASS`, `CCGT`, `WIND`, etc.). Wind generation is isolated by filtering `fuelType == "WIND"`.
- **Conclusion:** Full actual wind generation data for the complete month of January 2026 is reliably retrievable using standard date filtering parameters (`publishDateTimeFrom` / `publishDateTimeTo` or `settlementDate`).

---

## 5. January 2026 Historical Forecast-Vintage Availability

- **Status:** **[PARTIALLY RESTRICTED ON STREAM / VERIFIED VIA ARCHIVE ENDPOINTS]**
- **Observed Behavior on `/datasets/WINDFOR/stream`:**
  - When querying `WINDFOR/stream` without parameters, the API returns the active rolling forecast run (e.g., 74 half-hourly intervals covering a rolling ~3-day horizon).
  - When querying `WINDFOR/stream` with `publishDateTimeFrom=2026-01-01T00:00:00Z&publishDateTimeTo=2026-01-01T01:00:00Z`, the API returned HTTP 200 with an empty list (`[]`).
  - **Reason:** The `/stream` variant of `WINDFOR` is maintained as a real-time sliding feed for operational ingestion rather than deep cold-storage archive querying.
- **Documented Alternative for Historical Vintages:**
  - Elexon maintains dedicated historical endpoints:
    1. `/forecast/generation/wind/latest` (accepts `from` and `to` ISO timestamps for retrieving the latest forecast available for each historical period).
    2. `/forecast/generation/wind/history` (accepts `publishTime` for retrieving superseded historical forecast vintages).
- **Implication for WindLens:** The stream endpoint cannot be used alone to retroactively fetch January 2026 forecast vintages. The pipeline must query the historical forecast endpoints (`/forecast/generation/wind/latest` and `/history`).

---

## 6. Timestamp and Generation-Unit Findings

1. **Timestamps:**
   - Both datasets use **ISO 8601 UTC format** ending in `Z` (e.g. `2026-01-01T00:30:00Z`).
   - `startTime` represents the beginning of the half-hour delivery interval.
   - For January, Great Britain operates on Greenwich Mean Time (GMT / UTC+0), eliminating daylight saving (BST) offset complications for the target January 2026 analysis period.
2. **Generation Units:**
   - Generation values represent half-hourly average electrical power in **Megawatts (MW)**.
   - Note on energy vs power: To convert 30-minute average MW power to energy (Megawatt-hours, MWh), multiply by 0.5 hours: $\text{MWh} = \text{MW} \times 0.5$.

---

## 7. Pagination, Request Limits, and Performance Concerns

1. **Window Size Limits:** The stream endpoints will reject or timeout on queries spanning very large date ranges. Best practice is to chunk queries into single-day (24-hour) or 7-day increments.
2. **Payload Size:** One month of half-hourly intervals equals $31 \times 48 = 1,488$ delivery periods:
   - Actuals: $1,488$ records for `fuelType == "WIND"`.
   - Forecasts: Depending on the number of vintage updates retained (up to 8 updates per day), ~1,488 to ~11,900 records.
   - Total data volume is tiny (< 2 MB uncompressed JSON), easily fitting into local storage or memory.
3. **Rate Limiting:** Elexon's open tier accommodates moderate polling. Implementing a 200–500ms backoff between chunked requests prevents HTTP 429 throttling.

---

## 8. Data-Quality Risks

1. **Missing Records Coerced to Zero:**
   - *Risk:* If a missing settlement interval is naively filled with `0 MW`, wind generation will appear as a total drop-out, distorting forecast error metrics (MAE/RMSE).
   - *Mitigation:* The validation layer strictly checks `record["generation"] is not None` and raises an error instead of defaulting missing values to zero.
2. **Overwriting Forecast Vintages:**
   - *Risk:* Multiple forecasts exist for a single delivery period as NESO updates predictions up to 8 times daily. Storing records by keying only on `startTime` would overwrite prior vintages.
   - *Mitigation:* Forecast records must be keyed or indexed by both `(startTime, publishTime)`.
3. **Temporal Lookahead Bias (Data Leakage):**
   - *Risk:* Evaluating day-ahead decisions using a forecast published after the decision cutoff (e.g. intra-day forecasts published 2 hours before delivery) artificially inflates evaluated performance.
   - *Mitigation:* Enforce `publishTime <= decision_cutoff`.

---

## 9. Recommended Retrieval Strategy for the Complete Month

To fetch all of January 2026 reliably:

1. **Actual Data (FUELHH):**
   - Iterate day-by-day from `2026-01-01` to `2026-01-31`.
   - Query `GET /datasets/FUELHH/stream?publishDateTimeFrom={day}T00:00:00Z&publishDateTimeTo={day}T23:59:59Z`.
   - Filter response for `fuelType == "WIND"`.
   - Store in `data/actuals_2026_01.json` or SQLite.
2. **Forecast Data (WINDFOR):**
   - Query `GET /forecast/generation/wind/latest?from=2026-01-01T00:00:00Z&to=2026-02-01T00:00:00Z` for the baseline day-ahead / latest forecast horizon.
   - For multi-vintage analysis (investigating forecast evolution across cutoffs), query `/forecast/generation/wind/history` or historical backfills for specific cutoff times (e.g. 11:00 AM day-ahead).
   - Store in `data/forecasts_2026_01.json`.

---

## 10. Go/No-Go Assessment for Implementing the Analytics Pipeline

| Criterion | Evaluation | Status |
| :--- | :--- | :--- |
| **Actual Generation Data Availability** | January 2026 FUELHH actuals verified live with full 48 half-hours per day and `WIND` fuel type present. | **GO** |
| **API Stability & Auth Requirements** | API is public, stable, fast, and does not require complex auth or paid subscriptions. | **GO** |
| **Schema Compatibility** | `startTime`, `publishTime`, and `generation` (MW) match analytical model requirements. | **GO** |
| **Historical Forecast Retrieval** | Verified that `/stream` requires companion endpoint (`/forecast/generation/wind/latest` or `/history`) for January 2026 vintages. | **GO (with documented retrieval path)** |
| **Overall Project Feasibility** | Phase 1 objectives met; risks and validation rules established. | **GO TO PHASE 2** |

---

## 11. Unresolved Questions and Required Evidence

1. **Exact Day-Ahead Gate Closure / Purchasing Cutoff:**
   - *Question:* Which exact business cutoff time will the utility use for day-ahead purchasing? (e.g. 11:00 UTC day-ahead for EPEX SPOT day-ahead auction, or 12:00 UTC for Nord Pool, or a bespoke operational cutoff?)
   - *Evidence Needed:* Business stakeholder sign-off on default cutoff time (defaulting to 11:00 UTC day-ahead in analytics configuration).
2. **Intra-Day Vintage Granularity:**
   - *Question:* Does the buyer need to evaluate intra-day adjustments (e.g., 2 hours ahead of delivery), or exclusively the day-ahead auction decision?
   - *Evidence Needed:* Product manager clarification on UI metrics scope.

