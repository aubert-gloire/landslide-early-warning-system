# Landslide Early Warning System — Rwanda Northern Province

**BSc Software Engineering Capstone · African Leadership University**
**Student:** Aubert Gloire Bihibindi · **Supervisor:** Dirac Murairi

> An ML-based operational early warning system that scores daily landslide risk across 396 slope units in Northern Province Rwanda, dispatches SMS alerts to registered field officers, and provides a real-time monitoring dashboard.

🌐 **Live dashboard:** https://landslide-early-warning-system-zeta.vercel.app
🎥 **Demo video:** [5-minute walkthrough](https://drive.google.com/file/d/1rcH9cV3U6WTQxP2QJvadwM-4VsYsVlPr/view?usp=sharing)
📦 **Backend API:** https://landslide-ews-api.onrender.com/docs

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Installation — Local Development](#installation--local-development)
4. [Deployment](#deployment)
5. [Testing Results & Strategies](#testing-results--strategies)
6. [Analysis of Results](#analysis-of-results)
7. [Discussion](#discussion)
8. [Recommendations](#recommendations)
9. [API Reference](#api-reference)
10. [Data Sources](#data-sources)

---

## System Overview

Northern Province Rwanda records the highest landslide frequency in the country due to steep volcanic terrain and intense seasonal rainfall. MINEMA (National Disaster Management Authority) has no automated district-level alerting tool — field officers currently receive warnings by phone only after events are visually observed.

This system automates the warning pipeline:

1. **Every morning at 08:00 UTC**, a GitHub Actions cron job triggers the backend pipeline
2. Yesterday's rainfall is downloaded from NASA GPM IMERG (~14h latency) with CHIRPS Preliminary as fallback
3. USGS earthquake API is queried — a nearby M4.0+ event lowers the alert threshold
4. An XGBoost classifier scores all 396 slope units (AUC = 0.959)
5. Units above the threshold trigger SMS alerts to registered district officers via Africa's Talking + Telerivet
6. Officers reply YES/NO — feedback is logged and tracked as operational accuracy

---

## Architecture

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  DATA INGESTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  GPM IMERG Late Daily (~14h lag) ──┐
  CHIRPS v2 Preliminary (fallback)  ├──► Rainfall per slope unit centroid
  USGS Earthquake API (seismic)     ┘

  Copernicus 30m DEM ─────────────────► Slope angle, TWI (static)
  Sentinel-2 NDVI (GEE) ──────────────► Vegetation density (static)
  ISRIC SoilGrids ─────────────────────► Soil class (static)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  PIPELINE (backend/app/services/pipeline.py)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Feature Matrix (396 × 8 features)
       ▼
  XGBoost Classifier
  ImbPipeline: Imputer → SMOTE → XGBClassifier
  AUC=0.959 · threshold=0.05 (0.03 if seismic)
       ▼
  risk_probability per slope unit
       ▼
  ┌── prob ≥ threshold ──┐      ┌── prob < threshold ──┐
  ▼                      ▼      ▼
  MongoDB Atlas       SMS Alert (Africa's Talking + Telerivet)
  (all predictions)   → district officer → replies YES/NO

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  INTERFACES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  FastAPI (Python) ──► React dashboard (Vite)
  /api/risk-map         Risk Map tab — 396 GeoJSON polygons
  /api/districts        District cards — per-district peak risk
  /api/alerts           Alert log with officer feedback
  /api/trigger          Manual pipeline run
  POST /api/predict     Single-point prediction + expert SMS
```

**Tech stack:** Python 3.11 · FastAPI · XGBoost · Motor (async MongoDB) · React 18 · Leaflet · Vite · MongoDB Atlas · Render · Vercel · GitHub Actions

---

## Installation — Local Development

### Prerequisites

- Python 3.11+
- Node.js 18+
- MongoDB Atlas account (free tier)
- Africa's Talking account (sandbox for testing)
- NASA Earthdata account (free) — for GPM IMERG
- Google Earth Engine account (free) — for NDVI
- OpenTopography API key (free) — for DEM

### Step 1 — Clone and configure

```bash
git clone https://github.com/aubert-gloire/landslide-early-warning-system.git
cd landslide-early-warning-system
cp .env.example .env
```

Edit `.env` with your credentials:

```env
MONGODB_URI=mongodb+srv://<user>:<pass>@cluster.mongodb.net/
MONGODB_DB_NAME=landslide_ews
AT_USERNAME=your_africastalking_username
AT_API_KEY=your_africastalking_api_key
AT_SENDER_ID=EWS
OFFICER_PASSWORD=your_dashboard_password
EARTHDATA_TOKEN=your_nasa_earthdata_bearer_token
EARTHDATA_USERNAME=your_nasa_earthdata_username
EARTHDATA_PASSWORD=your_nasa_earthdata_password
OPENTOPO_API_KEY=your_opentopography_api_key
APP_ENV=development
```

### Step 2 — Backend setup

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Step 3 — One-time data pipeline (run once to populate MongoDB)

```bash
# From repo root (not backend/)
python scripts/setup_db.py dem      # Download Copernicus 30m DEM + compute slope/TWI
python scripts/setup_db.py units    # Generate 396 slope units via watershed analysis
python scripts/setup_db.py ndvi     # Sentinel-2 NDVI via Google Earth Engine
python scripts/setup_db.py soil     # ISRIC SoilGrids soil class
python scripts/setup_db.py chirps   # CHIRPS historical rainfall 2010–2024
python scripts/setup_db.py load     # Load all features into MongoDB Atlas
```

### Step 4 — Train the model

```bash
python scripts/train_model.py --backtest
# Outputs: ml/artifacts/rf_model.joblib · model_metadata.json · backtest_report.csv
# Expected: AUC ≈ 0.959, FNR ≈ 8.3% at threshold=0.05
```

### Step 5 — Run the backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
# API docs: http://localhost:8000/docs
```

### Step 6 — Run the dashboard

```bash
cd frontend
npm install
VITE_API_BASE_URL=http://localhost:8000 npm run dev
# Opens: http://localhost:5173
```

### Step 7 — Trigger a test pipeline run

```bash
# With real rainfall data
curl -X POST http://localhost:8000/api/trigger

# With synthetic high-risk scenario (for demo/testing)
curl -X POST http://localhost:8000/api/trigger \
  -H "Content-Type: application/json" \
  -d '{"override_daily_mm": 45.0, "override_antecedent_5day_mm": 185.0}'
```

---

## Deployment

### Backend → Render (Starter plan)

1. Push repo to GitHub
2. In Render dashboard → New Web Service → connect `aubert-gloire/landslide-early-warning-system`
3. Root Directory: `backend`
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
6. Add all environment variables from `.env` in Render → Environment tab
7. Health check path: `/health`

### Frontend → Vercel

1. In Vercel dashboard → New Project → import same GitHub repo
2. Framework: Vite · Root Directory: `frontend`
3. Add environment variable: `VITE_API_BASE_URL` = your Render URL
4. Deploy — Vercel auto-deploys on every push to `main`

### Daily automated pipeline → GitHub Actions

File: `.github/workflows/daily_pipeline.yml`
- Triggers at 08:00 UTC (10:00 Kigali time) daily
- POSTs to `/api/trigger` on the Render backend
- Add `API_BASE_URL` secret in GitHub → Settings → Secrets and variables → Actions

---

## Screenshots

### Mobile — Overview with live pipeline running
![Overview on phone](screenshots/overview%20page%20on%20phone%20with%20live%20pipeline%20run.jpeg)

### Mobile — Risk Map (396 slope unit polygons)
![Risk map on phone](screenshots/risk%20map%20on%20phone.jpeg)

### SMS Alert — received on field officer's phone
![Landslide phone alert](screenshots/Landslide%20phone%20alert.jpeg)

### Telerivet — dual SMS provider delivery confirmation
![Telerivet SMS delivery](screenshots/Telerivet.png)

### HelpChat — relevant question answered
![HelpChat relevant](screenshots/relevant%20question%20on%20help%20ai.png)

### HelpChat — unrecognised input (fallback handling)
![HelpChat fallback](screenshots/irrelevant%20questions%20on%20help%20ai.png)

---

## Testing Results & Strategies

### Strategy 1 — Unit / Model Validation (Offline)

The XGBoost model was evaluated using 5-fold stratified cross-validation on the full historical dataset (2010–2024, 396 slope units × 14 years).

| Metric | Value |
|--------|-------|
| AUC-ROC | **0.959** |
| Accuracy | 94.1% |
| False Negative Rate (threshold=0.05) | **8.3%** |
| False Positive Rate (threshold=0.05) | 22.7% |
| Precision | 0.41 |
| Recall | 0.917 |

**Comparison across 4 models (same dataset):**

| Model | AUC |
|-------|-----|
| XGBoost | **0.959** |
| Random Forest | 0.941 |
| Logistic Regression | 0.812 |
| SVM | 0.798 |

XGBoost selected as production model.

**Top feature importances (XGBoost SHAP):**

| Feature | Importance |
|---------|-----------|
| antecedent_5day_mm | 0.46 |
| antecedent_3day_mm | 0.33 |
| daily_mm | 0.05 |
| slope_angle | 0.06 |
| twi | 0.04 |
| ndvi | 0.03 |
| soil_class | 0.02 |
| antecedent_10day_mm | 0.01 |

### Strategy 2 — Integration Testing (API + Database)

Tested all API endpoints with the FastAPI Swagger UI at `/docs`:

| Endpoint | Test | Result |
|----------|------|--------|
| `GET /health` | Uptime check | ✓ 200 OK |
| `GET /api/risk-map` | Returns 396 GeoJSON features | ✓ |
| `GET /api/districts` | Returns 5 district summaries | ✓ |
| `GET /api/alerts` | Returns paginated alert history | ✓ |
| `POST /api/trigger` | Triggers full pipeline run | ✓ |
| `POST /api/predict` | Returns risk % for custom inputs | ✓ |

**Edge case inputs tested on `/api/predict`:**

| Scenario | Inputs | Expected | Actual |
|----------|--------|----------|--------|
| High risk | 35° slope, 45mm rain, 185mm 5day | HIGH / alert | ✓ HIGH |
| Low risk | 10° slope, 2mm rain, 8mm 5day | LOW / no alert | ✓ LOW |
| Dry season | 20° slope, 0mm rain, 0mm 5day | LOW | ✓ LOW |
| Invalid input | slope = -5° | 422 Validation Error | ✓ 422 |
| Missing field | no daily_mm | 422 Validation Error | ✓ 422 |

### Strategy 3 — End-to-End System Test (Pipeline Run)

Manual pipeline trigger with synthetic high-risk rainfall override:

```json
{"override_daily_mm": 45.0, "override_antecedent_5day_mm": 185.0}
```

Result: pipeline scored all 396 units, identified high-risk units, dispatched SMS alerts via Africa's Talking to registered officers, logged feedback loop. Risk map and district cards updated in real time via dashboard key-remount pattern.

### Strategy 4 — SMS Alert Delivery Test

- Africa's Talking sandbox: alert received with correct district, risk %, GPS coordinates, and reply instructions
- Telerivet parallel dispatch: confirmed delivery via Android SIM route on MTN Rwanda
- Officer reply simulation: "YES [unit_id]" and "NO [unit_id]" both correctly logged in alert_records collection

### Strategy 5 — Performance & Browser Testing

| Environment | Browser | Result |
|-------------|---------|--------|
| Windows 11 (local dev) | Chrome 126 | ✓ Full functionality |
| Windows 11 (local dev) | Firefox 127 | ✓ Full functionality |
| Production (Render + Vercel) | Chrome 126 | ✓ Full functionality |
| Mobile (Android) | Chrome Mobile | ✓ Responsive layout |

Pipeline execution time (production, Render Starter): ~45 seconds for full 396-unit run.

---

## Analysis of Results

### Objectives vs Outcomes

**Objective 1: Automate daily landslide risk scoring for Northern Province**
✅ Achieved. The pipeline runs automatically at 08:00 UTC daily via GitHub Actions. All 396 slope units across 5 districts receive a fresh risk score every morning with ~14-hour data lag (GPM IMERG) vs the 4-day lag of the original CHIRPS-only design.

**Objective 2: Achieve AUC ≥ 0.90 on historical validation**
✅ Exceeded. XGBoost achieved AUC = 0.959, above the 0.90 target. Class imbalance (landslide events are rare) was addressed with SMOTE inside a cross-validation-safe ImbPipeline, preventing data leakage.

**Objective 3: Dispatch SMS alerts to field officers with <5 min latency**
✅ Achieved. From pipeline trigger to SMS delivery is under 60 seconds in production. Two providers (Africa's Talking + Telerivet) ensure delivery resilience on MTN Rwanda.

**Objective 4: Build a usable monitoring dashboard for non-technical officers**
✅ Achieved. The dashboard uses role-based login (district buttons, no password complexity), plain-language risk labels (LOW/MEDIUM/HIGH/CRITICAL), and a built-in HelpChat assistant that explains every panel in plain language.

**Objective 5: Production deployment accessible to MINEMA stakeholders**
✅ Achieved. Live at https://landslide-early-warning-system-zeta.vercel.app — accessible from any browser, no installation required.

### Where Results Fell Short

**Training data size:** The model was trained on 12 confirmed Northern Province landslide events from MINEMA records supplemented with NASA COOLR catalog entries. Operational models typically use hundreds of events. With 12 positive cases, the model risks overfitting to specific conditions even with SMOTE. Cross-validated AUC of 0.959 may be optimistic — real-world FNR could be higher than 8.3%.

**Rainfall source latency:** GPM IMERG Late Daily has ~14-hour latency (yesterday's data available by midday today). For a truly real-time system, GPM IMERG Early Run (~4h) or ground gauge data would be preferable but requires a different data license.

**Geographic scope:** 5 districts of Northern Province are covered. Southern and Western Province, which also experience landslides, are outside scope due to lack of labeled training data from those regions.

---

## Discussion

### Milestone Impact

**Sprint 1 (Data & Infrastructure):** The watershed-based slope unit generation was the most critical design decision. Using slope units instead of pixel grids means the model operates on physically meaningful terrain units where water drainage behaves uniformly. This follows Kuradusenge et al. (2020) and is a major methodological advantage over pixel-based approaches that conflate flat land and steep slopes.

**Sprint 2 (Model Training):** The SMOTE + ImbPipeline combination was essential. Without SMOTE, the classifier predicted "no landslide" for nearly all cases (accurate but useless for warnings). The 5% production threshold, set deliberately below the 80% visual map threshold, reflects the asymmetric cost of missing a real event vs. sending a false alarm.

**Sprint 3 (Integration & Deployment):** The dual SMS provider architecture (Africa's Talking + Telerivet) emerged from a real operational constraint — Africa's Talking shared SMS pool sometimes fails on MTN Rwanda. Telerivet's Android SIM route provides a physical backup that doesn't depend on aggregator infrastructure.

**USGS Seismic Integration:** The dynamic threshold adjustment (5% → 3% when M4.0+ earthquake detected) reflects real geotechnical knowledge — earthquakes loosen soil cohesion and make slopes more susceptible to rainfall-triggered failure. This was not in the original proposal but was added after reviewing the 2023 Rubavu event where a seismic precursor preceded a major landslide.

### Limitations

The system cannot pinpoint the exact location within a slope unit where failure will occur — only that the unit as a whole is at elevated risk. Slope units average ~0.8 km² each. Field officers receiving alerts still need ground-level judgment to identify the specific vulnerable area.

---

## Recommendations

### For MINEMA and District Emergency Officers

1. **Register all 5 district officers** with the system as the initial pilot group. The SMS reply (YES/NO) feedback loop is only as valuable as the response rate — officers should be briefed that their replies directly improve the model over time.

2. **Do not rely solely on this system for evacuation decisions.** The system is decision support. Official evacuation protocols from Meteo Rwanda and MINEMA must remain the primary authority.

3. **Seasonal calibration:** During the dry season (June–September), expect LOW risk for all districts daily. The system is most operationally relevant during the two rainy seasons (March–May and October–December).

### For Future Development

4. **Expand training data:** Every confirmed landslide event should be logged in the system with GPS coordinates and date. After 2–3 more seasons of operation, a retrained model with 30–50 events will be significantly more robust.

5. **Integrate SMAP soil moisture** as a real-time display layer (the module `ml/pipeline/smap.py` is already implemented but not yet wired into the daily pipeline). Soil moisture state provides additional context for field officers interpreting borderline alerts.

6. **Add Early Run IMERG** (4-hour latency) as a secondary option for truly same-day risk assessment during active rain events — relevant during extreme rainfall episodes when waiting until the next morning is too late.

7. **Expand to all Rwanda provinces** by partnering with MINEMA to collect geo-tagged landslide reports from Southern and Western Province — currently blocked by absence of labeled training data outside Northern Province.

8. **Mobile app version** with push notifications would improve alert reach for officers in areas with intermittent SMS delivery.

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/risk-map` | GeoJSON FeatureCollection — 396 slope-unit polygons with risk scores |
| GET | `/api/districts` | Per-district summary: peak risk, unit count, recent alerts |
| GET | `/api/alerts` | Alert history, filterable by district |
| POST | `/api/trigger` | Trigger full pipeline run (accepts rainfall overrides for testing) |
| POST | `/api/predict` | Single-point prediction with SHAP feature explanation |
| POST | `/api/sms/callback` | Africa's Talking inbound SMS webhook (officer YES/NO replies) |
| GET | `/health` | Service health check |

Full interactive docs: https://landslide-ews-api.onrender.com/docs

---

## Data Sources

| Source | Product | Latency | License |
|--------|---------|---------|---------|
| NASA GES DISC | GPM IMERG Late Daily v07C | ~14 hours | Earthdata account required |
| UCSB CHC | CHIRPS v2 Preliminary | ~4 days | Public domain |
| OpenTopography | Copernicus GLO-30 DEM | Static | CC BY 4.0 |
| Google Earth Engine | Sentinel-2 NDVI | Seasonal | Copernicus open |
| ISRIC | SoilGrids 250m | Static | CC BY 4.0 |
| USGS | Earthquake Hazards FDSN API | Real-time | Public domain |
| MINEMA / NASA COOLR | Landslide event catalog | Historical | Public domain |

---

## Repository Structure

```
landslide-ews/
├── backend/                  # FastAPI application
│   ├── app/
│   │   ├── main.py           # App entry point, CORS, lifespan
│   │   ├── config.py         # Pydantic settings
│   │   ├── database.py       # Motor async MongoDB client
│   │   ├── ml/               # XGBoost model wrapper
│   │   ├── routes/           # API route handlers
│   │   └── services/         # Pipeline, SMS, scheduler
│   └── requirements.txt
├── frontend/                 # React dashboard (Vite)
│   └── src/
│       ├── components/       # RiskMap, DistrictCards, AlertTable, HelpChat, …
│       └── hooks/            # useApi (with cold-start retry logic)
├── ml/
│   ├── model/                # train.py, predict.py
│   ├── pipeline/             # chirps.py, gpm_imerg.py, smap.py
│   └── features/             # Feature matrix builder
├── scripts/                  # setup_db.py, train_model.py, replay_historical.py, …
├── data/                     # Raw + processed geodata (not committed)
├── .github/workflows/        # daily_pipeline.yml (GitHub Actions cron)
└── render.yaml               # Render deployment config
```

---

*Decision-support only. All alerts supplement — and do not replace — official MINEMA and Meteo Rwanda early warning protocols.*
