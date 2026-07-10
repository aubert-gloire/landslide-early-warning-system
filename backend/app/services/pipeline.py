"""
DataPipeline — daily operational pipeline.
Exposes: fetch_chirps(date), build_feature_matrix(), run_daily()

run_daily() is called by APScheduler and also by POST /api/trigger for demos.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import geopandas as gpd
import pandas as pd

from ..config import get_settings
from ..database import get_db
from ..ml.xgb_model import XGBModel
from .sms import get_alert_level, send_alert

logger = logging.getLogger(__name__)

# Resolve repo root relative to this file
_REPO_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

# Rwanda Northern Province centroid used for USGS earthquake proximity queries
_NORTHERN_PROVINCE_LAT = -1.50
_NORTHERN_PROVINCE_LON = 29.70
_SEISMIC_RADIUS_KM = 200
_SEISMIC_MIN_MAG = 4.0
_SEISMIC_WINDOW_HOURS = 48
_SEISMIC_THRESHOLD_OVERRIDE = 0.03  # lower than default 0.05 after seismic event


async def fetch_seismic_activity() -> dict:
    """
    Query USGS FDSNWS for earthquakes >= M4.0 within 200km of Rwanda Northern
    Province in the last 48 hours.

    Returns:
        {
          "detected": bool,
          "count": int,
          "max_magnitude": float | None,
          "events": [{"mag": float, "place": str, "time": str}, ...]
        }
    """
    import httpx
    from datetime import timezone

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=_SEISMIC_WINDOW_HOURS)

    params = {
        "format":      "geojson",
        "starttime":   start_time.strftime("%Y-%m-%dT%H:%M:%S"),
        "endtime":     end_time.strftime("%Y-%m-%dT%H:%M:%S"),
        "latitude":    _NORTHERN_PROVINCE_LAT,
        "longitude":   _NORTHERN_PROVINCE_LON,
        "maxradiuskm": _SEISMIC_RADIUS_KM,
        "minmagnitude": _SEISMIC_MIN_MAG,
        "orderby":     "magnitude",
    }
    url = "https://earthquake.usgs.gov/fdsnws/event/1/query"

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        events = [
            {
                "mag":   f["properties"]["mag"],
                "place": f["properties"]["place"],
                "time":  datetime.utcfromtimestamp(
                    f["properties"]["time"] / 1000
                ).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            for f in features
        ]
        detected = len(events) > 0
        max_mag = max((e["mag"] for e in events), default=None)
        return {"detected": detected, "count": len(events), "max_magnitude": max_mag, "events": events}
    except Exception as exc:
        logger.warning("USGS seismic query failed: %s — skipping seismic check", exc)
        return {"detected": False, "count": 0, "max_magnitude": None, "events": [], "error": str(exc)}


class DataPipeline:
    def __init__(self):
        self.settings = get_settings()
        self._slope_units: gpd.GeoDataFrame | None = None
        self._xgb_model: XGBModel | None = None

    def _get_slope_units(self) -> gpd.GeoDataFrame:
        if self._slope_units is None:
            gpkg = self.settings.processed_path() / "slope_units.gpkg"
            if not gpkg.exists():
                raise FileNotFoundError(
                    f"slope_units.gpkg not found at {gpkg}. "
                    "Run scripts/setup_db.py first."
                )
            self._slope_units = gpd.read_file(gpkg)
        return self._slope_units

    def _get_model(self) -> XGBModel:
        if self._xgb_model is None:
            self._xgb_model = XGBModel.load(self.settings.artifacts_path())
        return self._xgb_model

    def fetch_chirps(self, run_date: date | None = None) -> pd.DataFrame:
        """Fetch CHIRPS rainfall for a specific date (defaults to yesterday)."""
        from ml.pipeline.chirps import CHIRPSDownloader
        downloader = CHIRPSDownloader(
            self.settings.raw_path(),
            self.settings.processed_path(),
        )
        slope_units = self._get_slope_units()
        return downloader.fetch_latest(slope_units)

    def build_feature_matrix(self, rainfall_df: pd.DataFrame) -> pd.DataFrame:
        """Join rainfall with static terrain features for inference."""
        from ml.features.matrix import FeatureMatrixBuilder
        builder = FeatureMatrixBuilder(self.settings.processed_path())
        slope_units = self._get_slope_units()
        return builder.build_inference_row(slope_units, rainfall_df)

    async def run_daily(self, log_fn=None) -> dict:
        """
        Full daily pipeline:
        1. Fetch CHIRPS rainfall
        2. Build feature matrix
        3. Check USGS seismic activity (may lower alert threshold)
        4. Run XGBoost inference per slope unit
        5. Write all predictions to MongoDB
        6. Send SMS + write AlertRecord for units with prob ≥ threshold

        log_fn: optional async callable(str) — receives progress messages for live streaming.
        """
        async def log(msg):
            ts = datetime.now().strftime("%H:%M:%S")
            entry = f"[{ts}] {msg}"
            logger.info(msg)
            if log_fn:
                await log_fn(entry)

        await log("Pipeline starting…")
        run_date = date.today()
        db = get_db()

        await log("Loading XGBoost model…")
        model = self._get_model()
        await log(f"Model ready — alert threshold: {model.production_threshold}")

        # Step 1 & 2 — rainfall: MongoDB cache first, CHIRPS download as fallback
        rainfall_date = (run_date - timedelta(days=1)).isoformat()
        from pymongo import UpdateOne as _UpdateOne

        cached = await db.rainfall_records.find({"date": rainfall_date}).to_list(length=5000)

        if len(cached) >= 300:
            # Fast path: all units already saved from a previous run today
            await log(f"Rainfall cache hit for {rainfall_date} — {len(cached)} units from MongoDB (skipping CHIRPS download)")
            history_start = (run_date - timedelta(days=11)).isoformat()
            history_docs = await db.rainfall_records.find(
                {"date": {"$gte": history_start, "$lte": rainfall_date}},
                sort=[("date", 1)],
            ).to_list(length=50000)
            rainfall_df = pd.DataFrame([
                {"unit_id": r["slope_unit_id"], "date": r["date"], "daily_mm": float(r.get("daily_mm") or 0)}
                for r in history_docs
            ])
            rainfall_df["date"] = pd.to_datetime(rainfall_df["date"])
            rainfall_df = rainfall_df.sort_values(["unit_id", "date"])
            for window, col in [(3, "antecedent_3day_mm"), (5, "antecedent_5day_mm"), (10, "antecedent_10day_mm")]:
                rainfall_df[col] = (
                    rainfall_df.groupby("unit_id")["daily_mm"]
                    .transform(lambda s, w=window: s.rolling(w, min_periods=1).sum())
                )
            rainfall_df["rainfall_intensity_ratio"] = (
                rainfall_df["daily_mm"] / (rainfall_df["antecedent_5day_mm"] + 1.0)
            ).round(4)
            rainfall_df = rainfall_df[rainfall_df["date"] == pd.Timestamp(rainfall_date)].reset_index(drop=True)
        else:
            # Slow path: try GPM IMERG first (14h lag), fall back to CHIRPS (4-day lag)
            _su = self._get_slope_units()
            yesterday = run_date - timedelta(days=1)
            daily_df = pd.DataFrame()

            if self.settings.earthdata_token:
                from ml.pipeline.gpm_imerg import GPMIMERGDownloader
                await log("Step 1/3 — Trying GPM IMERG Late Daily (14h lag, bearer token auth)…")
                imerg = GPMIMERGDownloader(
                    self.settings.raw_path(),
                    self.settings.earthdata_token,
                    username=self.settings.earthdata_username,
                    password=self.settings.earthdata_password,
                )
                daily_df = await asyncio.to_thread(imerg.extract_per_unit, yesterday, _su)
                if not daily_df.empty:
                    await log(
                        f"Step 1/3 — IMERG success — {len(daily_df)} units "
                        f"(max {daily_df['daily_mm'].max():.1f} mm, median {daily_df['daily_mm'].median():.1f} mm)"
                    )
                else:
                    await log("Step 1/3 — IMERG unavailable for this date — falling back to CHIRPS…")
            else:
                await log("Step 1/3 — EARTHDATA_TOKEN not set — skipping IMERG, using CHIRPS…")

            if daily_df.empty:
                from ml.pipeline.chirps import CHIRPSDownloader
                downloader = CHIRPSDownloader(self.settings.raw_path(), self.settings.processed_path())
                await log("Step 2/3 — Downloading CHIRPS v2 rainfall file from UCSB (~30-60s)…")
                tif_path = await asyncio.to_thread(downloader.download_day, yesterday)
                if tif_path:
                    await log(f"Step 2/3 — CHIRPS file ready — extracting {len(_su)} slope units (~60s)…")
                else:
                    await log("Step 2/3 — CHIRPS download failed — using zero rainfall fallback…")
                daily_df = await asyncio.to_thread(downloader.extract_per_unit_rainfall, yesterday, _su)

            await log("Step 3/3 — Per-unit extraction complete — computing 3/5/10-day antecedent windows…")

            daily_df["date"] = pd.to_datetime(daily_df["date"])
            history_path = self.settings.processed_path() / "chirps_historical.parquet"
            if history_path.exists():
                history = pd.read_parquet(history_path)
                cutoff = pd.Timestamp(yesterday) - pd.Timedelta(days=9)
                recent = history[history["date"] >= cutoff][["unit_id", "date", "daily_mm"]]
                combined = pd.concat([recent, daily_df], ignore_index=True)
            else:
                combined = daily_df
            combined = combined.sort_values(["unit_id", "date"])
            for window, col in [(3, "antecedent_3day_mm"), (5, "antecedent_5day_mm"), (10, "antecedent_10day_mm")]:
                combined[col] = (
                    combined.groupby("unit_id")["daily_mm"]
                    .transform(lambda s, w=window: s.rolling(w, min_periods=1).sum())
                )
            combined["rainfall_intensity_ratio"] = (
                combined["daily_mm"] / (combined["antecedent_5day_mm"] + 1.0)
            ).round(4)
            rainfall_df = combined[combined["date"] == pd.Timestamp(yesterday)].reset_index(drop=True)
            rain_upserts = [
                _UpdateOne(
                    {"slope_unit_id": int(row["unit_id"]), "date": rainfall_date},
                    {"$set": {
                        "slope_unit_id": int(row["unit_id"]),
                        "date": rainfall_date,
                        "daily_mm": float(row.get("daily_mm", 0) or 0),
                    }},
                    upsert=True,
                )
                for _, row in rainfall_df.iterrows()
            ]
            if rain_upserts:
                await db.rainfall_records.bulk_write(rain_upserts, ordered=False)
            await log(f"Saved {len(rain_upserts)} rainfall records to MongoDB")

        max_rain = float(rainfall_df["antecedent_5day_mm"].max()) if len(rainfall_df) else 0
        await log(f"Rainfall ready — {len(rainfall_df)} units, max 5-day antecedent: {max_rain:.1f} mm")

        await log("Building feature matrix (terrain + NDVI + soil + rainfall)…")
        feature_df = self.build_feature_matrix(rainfall_df)
        await log(f"Feature matrix ready — {len(feature_df)} units × 8 features")

        # Seismic check — lower threshold if significant earthquake nearby in last 48h
        await log("Checking USGS seismic activity near Northern Province (M4.0+, 200km, 48h)…")
        seismic = await fetch_seismic_activity()
        threshold_override = None
        if seismic.get("error"):
            await log(f"Seismic query unavailable ({seismic['error']}) — using default threshold")
        elif seismic["detected"]:
            threshold_override = _SEISMIC_THRESHOLD_OVERRIDE
            await log(
                f"Seismic alert: {seismic['count']} earthquake(s) detected "
                f"(max M{seismic['max_magnitude']:.1f} near {seismic['events'][0]['place']}) — "
                f"lowering alert threshold to {threshold_override} (default {model.production_threshold})"
            )
        else:
            await log(f"No seismic activity detected — threshold: {model.production_threshold}")

        # Step 3 — inference
        await log("Scoring all slope units with XGBoost…")
        predictions_df = model.predict(feature_df, threshold_override=threshold_override)
        n_alerts = int(predictions_df["alert_triggered"].sum())
        max_prob = float(predictions_df["risk_probability"].max())
        await log(
            f"Scoring complete — {n_alerts} units above threshold "
            f"(highest risk: {max_prob*100:.1f}%)"
        )

        # Merge district + sector info from slope units
        _su = self._get_slope_units()
        _cols = ["unit_id", "district"]
        if "sector" in _su.columns:
            _cols.append("sector")
        if "centroid_lat" in _su.columns:
            _cols += ["centroid_lat", "centroid_lon"]
        slope_units = _su[_cols]
        predictions_df = predictions_df.merge(slope_units, on="unit_id", how="left")

        # Step 4 — write all predictions
        await log("Saving predictions to MongoDB…")
        prediction_docs = []
        for _, row in predictions_df.iterrows():
            prob = float(row["risk_probability"])
            alert_level, _ = get_alert_level(prob)
            doc = {
                "slope_unit_id": int(row["unit_id"]),
                "date": run_date.isoformat(),
                "risk_probability": prob,
                "alert_triggered": bool(row["alert_triggered"]),
                "alert_level": alert_level if bool(row["alert_triggered"]) else None,
                "district": str(row.get("district", "Unknown")),
                "sector": str(row.get("sector", "")),
                "top_features": list(row["top_features"]),
                "created_at": datetime.utcnow().isoformat(),
            }
            prediction_docs.append(doc)

        if prediction_docs:
            # Replace today's predictions — avoids duplicates from retries or replays
            await db.predictions.delete_many({"date": run_date.isoformat()})
            await db.predictions.insert_many(prediction_docs)
        await log(f"Saved {len(prediction_docs)} predictions to MongoDB")

        # Step 5 — SMS for high-risk units
        alert_rows = predictions_df[predictions_df["alert_triggered"]]
        alert_count = 0

        if alert_rows.empty:
            await log("No units above alert threshold — no SMS dispatched")
        else:
            await log(f"Dispatching SMS alerts for {len(alert_rows)} high-risk units…")
            for _, row in alert_rows.iterrows():
                district = row.get("district", "Unknown")
                sector = row.get("sector", "")
                recipients = await db.recipients.find(
                    {"$or": [{"district": district}, {"districts": district}], "active": True}
                ).to_list(length=100)

                pred_doc = await db.predictions.find_one(
                    {"slope_unit_id": int(row["unit_id"]), "date": run_date.isoformat()},
                    sort=[("created_at", -1)],
                )
                prediction_id = str(pred_doc["_id"]) if pred_doc else "unknown"

                for recipient in recipients:
                    await send_alert(
                        phone=recipient["phone"],
                        recipient_id=recipient["recipient_id"],
                        prediction_id=prediction_id,
                        district=district,
                        sector=sector,
                        unit_id=int(row["unit_id"]),
                        risk_probability=float(row["risk_probability"]),
                        top_features=list(row["top_features"]),
                        centroid_lat=float(row["centroid_lat"]) if "centroid_lat" in row and row["centroid_lat"] is not None else None,
                        centroid_lon=float(row["centroid_lon"]) if "centroid_lon" in row and row["centroid_lon"] is not None else None,
                    )
                    location = f"{district} / {sector} sector" if sector else district
                    await log(
                        f"SMS → {recipient['name']} ({location}, unit #{int(row['unit_id'])}, "
                        f"{int(row['risk_probability']*100)}% risk)"
                    )
                    alert_count += 1

        summary = {
            "run_date": run_date.isoformat(),
            "units_processed": len(predictions_df),
            "alerts_triggered": int(alert_rows.shape[0]),
            "sms_sent": alert_count,
            "seismic_detected": seismic["detected"],
            "seismic_count": seismic["count"],
            "seismic_max_magnitude": seismic.get("max_magnitude"),
            "threshold_used": threshold_override if threshold_override is not None else model.production_threshold,
        }
        await log(f"Pipeline complete — {alert_count} SMS sent, {len(predictions_df)} units processed")
        logger.info("=== Daily pipeline complete: %s ===", summary)
        return summary
