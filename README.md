# Landslide Early Warning System — Rwanda Northern Province

ML-based daily landslide risk prediction and SMS alerting for Gakenke, Burera, Musanze, and Gicumbi districts.

**BSc Software Engineering Capstone — ALU · Supervised by Dirac Murairi**

---

## Architecture

```
CHIRPS v3 rainfall (daily) ─┐
Copernicus DEM 30m ─────────┤─► Feature Matrix (8 cols, per slope unit per day)
Sentinel-2 NDVI ────────────┤         ▼
ISRIC SoilGrids ────────────┘   Random Forest (500 trees)
                                      ▼
                              Probability per slope unit
                                      ▼
                    ┌──── prob ≥ 0.80 ────┐
                    ▼                     ▼
              MongoDB Atlas          Africa's Talking SMS
              (all predictions)      (district officers)
                    ▼
              FastAPI + React dashboard
```

**Key feature:** 5-day antecedent rainfall accumulation (Kuradusenge et al. 2020 — pushes RF accuracy from 89% to 98.74% on Rwandan terrain)

---

## Quick Start

### 1. Clone and configure

```bash
git clone <repo-url>
cd landslide-ews
cp .env.example .env
# Fill in: MONGODB_URI, AT_API_KEY, OPENTOPO_API_KEY
```

### 2. Backend setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 3. Data pipeline (Sprint 1)

```bash
# Run each step, or all at once
python scripts/setup_db.py dem       # Download COP30 DEM + terrain derivatives
python scripts/setup_db.py units     # Generate slope units (saved as data/processed/slope_units.gpkg)
python scripts/setup_db.py ndvi      # Sentinel-2 NDVI via Google Earth Engine
python scripts/setup_db.py soil      # ISRIC SoilGrids texture class
python scripts/setup_db.py chirps    # CHIRPS v3 daily rainfall 2000-2024 (~25 min)
python scripts/setup_db.py load      # Load static features into MongoDB Atlas
```

### 4. Train the model (Sprint 2)

```bash
python scripts/train_model.py --backtest
# Outputs: ml/artifacts/rf_model.joblib + model_metadata.json + backtest_report.csv
```

### 5. Start the API

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

### 6. Start the dashboard

```bash
cd frontend
npm install
npm run dev   # opens at http://localhost:5173
```

### 7. Seed demo data (for video recording)

```bash
python scripts/seed_demo.py
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/risk-map` | GeoJSON FeatureCollection — slope-unit risk scores |
| GET | `/api/alerts` | Alert history (filterable by district) |
| GET | `/api/districts` | Per-district summary stats |
| POST | `/api/trigger` | Manually trigger prediction run |
| POST | `/api/sms/callback` | Africa's Talking inbound SMS webhook |
| GET | `/health` | Uptime check |

**Demo trigger with synthetic rainfall:**
```bash
curl -X POST http://localhost:8000/api/trigger \
  -H "Content-Type: application/json" \
  -d '{"override_daily_mm": 45.0, "override_antecedent_5day_mm": 180.0, "dry_run": true}'
```

---

## Deployment

### Backend → Render (free tier)
1. Push repo to GitHub
2. Create new Web Service on Render, point to `/backend`
3. Add environment variables from `.env` in Render dashboard
4. Set `API_BASE_URL` secret in GitHub repo for daily pipeline cron

### Frontend → Vercel (free tier)
1. Import repo in Vercel, set root to `/frontend`
2. Set `VITE_API_BASE_URL` to your Render URL

### Daily cron
GitHub Actions (`.github/workflows/daily_pipeline.yml`) triggers at 04:00 UTC (06:00 Kigali).
Add `API_BASE_URL` secret in GitHub repo settings → Secrets.

### Uptime (prevent Render sleep)
Register `https://your-app.onrender.com/health` on [UptimeRobot](https://uptimerobot.com) free tier, 5-min interval.

---

## Data Sources

| Source | Method | License |
|--------|--------|---------|
| CHIRPS v3 daily rainfall | UCSB CHC server (no account) | Public domain |
| Copernicus DEM 30m | OpenTopography API (free key) | CC BY 4.0 |
| Sentinel-2 NDVI | Google Earth Engine (free account) | Copernicus |
| ISRIC SoilGrids | soilgrids.org WCS (no account) | CC BY 4.0 |
| NASA COOLR landslide catalog | landslides.nasa.gov (free download) | Public domain |
| MINEMA event data | Hand-populated `data/labels/minema_supplement.csv` | — |

---

## Model Performance Targets

| Metric | Target | Threshold |
|--------|--------|-----------|
| False Negative Rate | < 5% | prob ≥ 0.80 |
| False Positive Rate | < 15% | prob ≥ 0.80 |

Alert threshold set at **0.80** (not 0.50) — deliberate tradeoff to reduce false alarms that erode officer trust.

---

## Ethical Constraints

- No personal data from the public collected or stored.
- System is **decision-support only** — all alerts supplement official MINEMA and Meteo Rwanda protocols.
- SMS is the primary alert channel (works without smartphone/internet for recipients).
