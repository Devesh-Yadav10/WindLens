# WindLens — 10-Minute Presentation & Demo Script

**Target Audience:** Electricity Trading Desk & Head of Risk  
**Speaker Role:** Lead Energy Analytics & Systems Engineer  
**Duration:** 10 Minutes Total (00:00 – 10:00)

---

## Part 1: Domain Problem & Trading Context (00:00 – 04:30)

### 00:00 – 01:15 | The Operational Challenge
> "Good morning, everyone. In the UK electricity market, power cannot be stored in large quantities at scale. Supply and demand must balance continuously. Every single day at 11:00 UTC, day-ahead power auctions close across European power exchanges (EPEX SPOT and Nord Pool).
> 
> As an energy buyer or desk trader, you must commit to physical delivery volumes 13 to 37 hours before electricity actually flows. If your contracted position differs from physical output during delivery, you enter the Elexon Balancing Mechanism at the System Buy Price (SBP) or System Sell Price (SSP) cashout. 
> 
> When wind generates less than expected, you are caught short in a tight market, paying extreme balancing cashout penalties."

### 01:15 – 02:45 | The Specific Risk: Lookahead Bias & Forecast Vintages
> "Most analytics platforms report forecast error by comparing the *latest* forecast published just minutes before delivery against actual generation. That is completely useless for day-ahead purchasing decisions.
> 
> To evaluate real trading risk, you must reconstruct the exact forecast that was on your desk at **11:00 UTC on day $D-1$**. Any forecast published at 11:05 UTC, 18:00 UTC, or during day $D$ introduces lookahead bias.
> 
> WindLens was built specifically to solve this. We ingest official Elexon and NESO data streams, apply strict point-in-time gate-closure cutoff filters, and provide trading desks with ground-truth accuracy metrics and bias analysis."

### 02:45 – 04:30 | January 2026 Ground Truth Findings
> "Let us look at what happened in January 2026 across Great Britain:
> 
> 1. **Persistent Overforecasting (Positive Bias):** The mean bias (MBE) was **+1,841.67 MW**. On average, day-ahead forecasts predicted 1.84 GW more wind generation than was actually delivered.
> 2. **Mean Absolute Error (MAE):** The average absolute forecast error was **2,124.56 MW**, representing a Normalized MAE of **18.34%** against national wind capacity (~11.58 GW average output).
> 3. **The Trading Consequence:** A trader relying blindly on unadjusted NESO day-ahead wind forecasts in January 2026 would have systematically bought less conventional replacement generation, exposing the portfolio to balancing mechanism cashout charges during shortfalls.
> 4. **Extreme Imbalance Event (January 26, 2026, 17:00 UTC):** Forecasted wind was 13,382 MW; actual generation collapsed to 6,024.5 MW. That was a **single-hour deficit of 7,357.5 MW**, creating significant market stress and price spikes."

---

## Part 2: Live Application Walkthrough (04:30 – 07:30)

### 04:30 – 05:15 | Navigation & Overview KPI Ribbon
*(Screen: Dashboard Overview tab)*
> "Here on the WindLens dashboard, notice our primary typographic hierarchy and high-contrast KPI cards:
> - **Total Hours Analyzed:** 743 matched delivery hours out of 744 (99.87% coverage).
> - **MAE:** 2,124.56 MW
> - **RMSE:** 2,618.28 MW
> - **Mean Bias:** +1,841.67 MW with a clear 'Overforecasting' indicator tag.
> - **NMAE & MAPE:** 18.34% and 22.08% respectively.
> 
> Everything here is backed by validated, verified Elexon datasets. There are no fabricated fallback figures."

### 05:15 – 06:15 | Forecast Explorer & Interactive Date Drill-down
*(Screen: Select date `2026-01-26` in the Forecast Explorer)*
> "Let us drill into January 26th—the day of the largest wind drop. 
> 
> The interactive chart plots the D-1 11:00 UTC Day-Ahead Forecast curve (in blue) against the Half-Hourly FUELHH Actual Generation curve (in amber).
> 
> Hovering over 17:00 UTC, we see the forecast expected peak output above 13.3 GW, while actual wind stalled at 6.0 GW. A buyer using WindLens could immediately flag that early morning wind forecasts diverged, enabling intraday hedges before the prompt market surged."

### 06:15 – 07:30 | Daily Accuracy, Peak Imbalances & Data Export
*(Screen: Scroll down to Daily MAE Bar Chart and Peak Undergeneration Table)*
> "Below the explorer, the **Daily MAE Trend** shows that volatility peaked during the final week of January (Jan 24–28). 
> 
> The **Peak Imbalance Table** highlights the top 10 undergeneration intervals, detailing the exact forecast publication time (`publishTime`), delivery timestamp (`startTime`), and error magnitude in megawatts.
> 
> For quantitative traders and risk analysts wanting to plug this into Python or Excel models, one click on **'Export Matched Dataset (CSV)'** downloads the complete 743-row reconciled time series."

---

## Part 3: Architecture & Engineering Rigor (07:30 – 09:15)

### 07:30 – 08:15 | Data Pipelines & Cutoff Selection Engine
> "Under the hood, WindLens operates a decoupled three-tier architecture:
> 
> 1. **Data Ingestion (`scripts/ingestion.py`):** Pulls FUELHH (half-hourly actuals) and WINDFOR (forecast vintages). We convert 30-minute actuals to 60-minute averages using clean arithmetic to align with hourly WINDFOR deliveries.
> 2. **Point-in-Time Selection (`scripts/analytics.py`):** For each delivery date $D$, we compute the gate-closure cutoff timestamp $T_{cutoff} = (D-1) \text{ 11:00:00 UTC}$. For each delivery hour $h$, we filter all historical forecasts where $\text{publishTime} \le T_{cutoff}$, and select the latest valid vintage.
> 3. **Single Documented Missing Interval:** On January 1st, 00:00 UTC, the latest forecast prior to Dec 31, 11:00 UTC had a 24-hour horizon ending Dec 31, 23:00 UTC. Rather than hallucinating or backfilling data, WindLens transparently reports 743/744 valid hours."

### 08:15 – 09:15 | Backend, Frontend, and Automated Testing
> "Our backend is built with FastAPI and Pydantic v2:
> - Validated query parameters, strict schema serialization, and CORS configuration.
> - High-performance in-memory caching of pre-reconciled datasets ensures sub-5ms response times.
> - The frontend is built with React 18, TypeScript, Tailwind CSS, and Recharts, utilizing system serif typography for a clean, publication-ready financial aesthetic.
> - We maintain a **36-test automated suite** covering schema validation, time interval alignment, metric computations, and API route contracts with 100% test passing."

---

## Part 4: Q&A and Production Roadmap (09:15 – 10:00)

### 09:15 – 10:00 | Production Readiness & Next Steps
> "To conclude: WindLens proves that day-ahead wind forecast error in January 2026 introduced substantial short imbalance risk (+1.84 GW bias).
> 
> With our containerized Docker deployment (`docker-compose.yml`), the system can be deployed immediately to cloud infrastructure (Render, AWS ECS, or Kubernetes).
> 
> In the next phase, we can connect live real-time webhooks for daily automatic updates and add automated imbalance price penalty calculations.
> 
> Thank you, and I welcome any questions from the desk."
