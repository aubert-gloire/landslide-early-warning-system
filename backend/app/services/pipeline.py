"""
DataPipeline — daily operational pipeline.
Exposes: fetch_chirps(date), build_feature_matrix(), run_daily()

run_daily() is called by APScheduler and also by POST /api/trigger for demos.
"""

from __future__ import annotations

import logging
import sys
from datetime import date, datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd

from ..config import get_settings
from ..database import get_db
from ..ml.rf_model import RFModel
from .sms import send_alert

logger = logging.getLogger(__name__)

# Resolve repo root relative to this file
_REPO_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))


class DataPipeline:
    def __init__(self):
        self.settings = get_settings()
        self._slope_units: gpd.GeoDataFrame | None = None
        self._rf_model: RFModel | None = None

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

    def _get_model(self) -> RFModel:
        if self._rf_model is None:
            self._rf_model = RFModel.load(self.settings.artifacts_path())
        return self._rf_model

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

    async def run_daily(self) -> dict:
        """
        Full daily pipeline:
        1. Fetch CHIRPS rainfall
        2. Build feature matrix
        3. Run RF inference per slope unit
        4. Write all predictions to MongoDB
        5. Send SMS + write AlertRecord for units with prob ≥ threshold
        """
        logger.info("=== Daily pipeline starting ===")
        run_date = date.today()
        db = get_db()
        model = self._get_model()

        # Step 1 & 2
        rainfall_df = self.fetch_chirps(run_date)
        feature_df = self.build_feature_matrix(rainfall_df)

        # Step 3 — inference
        predictions_df = model.predict(feature_df)

        # Merge district info from slope units
        slope_units = self._get_slope_units()[["unit_id", "district"]]
        predictions_df = predictions_df.merge(slope_units, on="unit_id", how="left")

        # Step 4 — write all predictions
        prediction_docs = []
        for _, row in predictions_df.iterrows():
            doc = {
                "slope_unit_id": int(row["unit_id"]),
                "date": run_date.isoformat(),
                "risk_probability": float(row["risk_probability"]),
                "alert_triggered": bool(row["alert_triggered"]),
                "top_features": list(row["top_features"]),
                "created_at": datetime.utcnow().isoformat(),
            }
            prediction_docs.append(doc)

        if prediction_docs:
            await db.predictions.insert_many(prediction_docs)

        # Step 5 — SMS for high-risk units
        alert_rows = predictions_df[predictions_df["alert_triggered"]]
        alert_count = 0
        for _, row in alert_rows.iterrows():
            district = row.get("district", "Unknown")
            recipients = await db.recipients.find(
                {"district": district, "active": True}
            ).to_list(length=100)

            # Find the prediction_id we just wrote
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
                    unit_id=int(row["unit_id"]),
                    risk_probability=float(row["risk_probability"]),
                    top_features=list(row["top_features"]),
                )
                alert_count += 1

        summary = {
            "run_date": run_date.isoformat(),
            "units_processed": len(predictions_df),
            "alerts_triggered": int(alert_rows.shape[0]),
            "sms_sent": alert_count,
        }
        logger.info("=== Daily pipeline complete: %s ===", summary)
        return summary
