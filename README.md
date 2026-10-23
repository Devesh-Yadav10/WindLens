# WindLens — UK National Wind Generation Forecast Analytics

**WindLens** is a full-stack energy analytics application for UK electricity utilities and energy trading desks. It evaluates national day-ahead wind generation forecasts against actual metered outturns to quantify volume imbalances, system bias, and forecast risk when making Day-Ahead electricity purchasing commitments.

Built with **FastAPI**, **React 18**, **TypeScript**, **Tailwind CSS**, and **Recharts**. Data sourced directly from the official **Elexon BMRS Insights Solution API** (`FUELHH` and `WINDFOR`).

---

## 1. System Architecture

```text
windlens/
├── backend/
│   ├── main.py                    # FastAPI application, CORS, routers & endpoints
│   ├── schemas.py                 # Pydantic v2 validation models
│   └── data_loader.py             # In-memory cached dataset access layer
├── scripts/
│   ├── analytics.py               # Cutoff selection, resolution alignment & error metrics
│   ├── run_analytics.py           # Reproducible analytics pipeline runner
│   ├── ingestion.py               # Official Elexon BMRS ingestion client
│   ├── validation.py              # Timezone-aware schema validation
│   └── cache.py                   # Data provenance & caching envelope
├── data/
│   ├── actuals_2026_01.json       # Complete January 2026 actual wind records (1,488 records)
│   ├── forecasts_2026_01.json     # January 2026 latest forecast records
│   ├── forecasts_day_ahead_cutoff_2026_01.json # Day-Ahead D-1 11:00 UTC historical vintages (744 records)
│   └── processed/
│       ├── january_2026_forecast_vs_actual.csv # Aligned hourly observations
│       └── january_2026_accuracy_summary.json  # Comprehensive summary JSON
├── frontend/
│   ├── src/
│   │   ├── App.tsx                # Professional trading dashboard UI
│   │   ├── api.ts                 # Type-safe frontend client for FastAPI
│   │   ├── types.ts               # TypeScript data definitions
│   │   └── index.css              # Tailwind CSS styling
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── docs/
│   ├── DATA_FEASIBILITY.md        # Phase 1 Feasibility Report
│   ├── DATA_PIPELINE_REPORT.md    # Phase 2 Ingestion & Caching Report
│   ├── ANALYTICS_REPORT.md        # Phase 3 Methodology & Metrics Report
│   └── DEMO_SCRIPT.md             # 10-minute trading desk walkthrough & presentation script
├── tests/
│   ├── test_data_validation.py    # Ingestion & validation unit tests (16 tests)
│   ├── test_analytics.py          # Analytics & alignment unit tests (9 tests)
│   └── test_api.py                # FastAPI endpoint integration tests (11 tests)
├── requirements.txt               # Backend dependencies (fastapi, uvicorn, pydantic, httpx, pytest)
├── Dockerfile                     # Backend Docker container
├── docker-compose.yml             # Full-stack Docker orchestration
└── PROJECT_STATUS.md              # Project status and handoff notes
```

---

## 2. Official Elexon Data Sources & Methodology

### Data Sources
1. **Actual Generation Outturn (`FUELHH`):**
   - Endpoint: `GET https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream`
   - Filter: `fuelType == "WIND"`
   - Granularity: 30-minute settlement periods (48 periods per day, 1,488 records for January 2026).
2. **Day-Ahead Wind Forecast Vintages (`WINDFOR`):**
   - Endpoint: `GET https://data.elexon.co.uk/bmrs/api/v1/forecast/generation/wind/history?publishTime={cutoff}&format=json`
   - Granularity: 60-minute intervals (corresponding to settlement period pairs 1-2, 3-4, etc.).

### Forecast Selection & Decision Cutoff Policy
- **Configured Policy:** `day_ahead_1100` (11:00 UTC on Day $D-1$).
- **Market Context:** EPEX SPOT and Nord Pool UK Day-Ahead power auctions close at 11:00 UTC daily.
- **Selection Rule:** For each delivery interval, select the latest forecast where `publishTime <= D-1 11:00:00Z` (specifically the 09:30 UTC NESO publication run).
- **Anti-Lookahead Bias:** All forecasts published after 11:00 UTC are strictly excluded.

### Resolution Alignment
- Actual power generation (MW) is reported in 30-minute intervals ($HH_1$ and $HH_2$).
- Average hourly power is computed as:
  $$\text{Actual}_{\text{hourly}} = \frac{\text{Actual}_{HH_1} + \text{Actual}_{HH_2}}{2.0}$$
- Matched against the hourly Day-Ahead forecast. Zero interpolation or zero-filling applied.

---

## 3. Measured January 2026 Results

- **Hourly Matched Observations:** 743 out of 744 (99.87% coverage).
- **Mean Actual Generation:** 11,584.22 MW
- **Mean Day-Ahead Forecast:** 13,425.89 MW
- **Mean Absolute Error (MAE):** 2,124.56 MW (18.34% Normalized MAE)
- **Root Mean Squared Error (RMSE):** 2,618.28 MW
- **Mean Bias Error (MBE):** +1,841.67 MW (*systematic over-forecasting bias*)
- **Peak Imbalance:** +6,833 MW over-forecast on January 12, 2026 (15.5h lead time).

---

## 4. Local Installation & Startup Instructions

### Prerequisites
- Python 3.12+ (or existing virtual environment)
- Node.js 18+ and npm

### A. Run Backend (FastAPI)

```powershell
# In project root:
.venv\Scripts\activate

# Install requirements
pip install -r requirements.txt

# Start backend server on port 8000
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Backend interactive API documentation: `http://localhost:8000/docs`

### B. Run Frontend (React + Vite)

```powershell
# In another terminal:
cd frontend

# Install dependencies (if not already installed)
npm install

# Start Vite development server
npm run dev
```

Dashboard interface: `http://localhost:5173`

---

## 5. Running the Automated Test Suite

```powershell
# Run the complete test suite (36 tests: validation, analytics, and FastAPI endpoints)
.venv\Scripts\python -m unittest discover tests

# Or specify individual test modules:
.venv\Scripts\python -m unittest tests/test_data_validation.py tests/test_analytics.py tests/test_api.py
```

---

## 6. Docker Deployment

```bash
# Build and run both backend and frontend containers:
docker compose up --build
```

- Web UI: `http://localhost:5173`
- API Backend: `http://localhost:8000`

---

## 7. AI Disclosure
This application was developed with the assistance of **Antigravity**, Google DeepMind's agentic AI pair programming system, adhering to strict data verification, zero-fabrication policies, and institutional energy analytics standards.

