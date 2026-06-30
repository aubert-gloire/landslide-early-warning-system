"""
RFModel — singleton wrapper around the trained joblib model.
Loaded once at FastAPI startup, reused on every request.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class RFModel:
    _instance: "RFModel | None" = None

    def __init__(self, artifacts_dir: Path):
        model_path = artifacts_dir / "rf_model.joblib"
        meta_path = artifacts_dir / "model_metadata.json"

        if not model_path.exists():
            raise FileNotFoundError(
                f"Model file not found at {model_path}. "
                "Run scripts/train_model.py before starting the API."
            )

        self._model = joblib.load(model_path)
        logger.info("RF model loaded from %s", model_path)

        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
            self.feature_cols: list[str] = meta.get("feature_cols", [])
            self.production_threshold: float = meta.get("production_threshold", 0.80)
            self.feature_importances: dict = meta.get("feature_importances", {})
        else:
            logger.warning("model_metadata.json not found — using defaults")
            self.feature_cols = [
                "slope_angle", "aspect", "twi", "drainage_density",
                "ndvi", "soil_class", "daily_mm", "antecedent_5day_mm",
            ]
            self.production_threshold = 0.80
            self.feature_importances = {}

    @classmethod
    def load(cls, artifacts_dir: Path) -> "RFModel":
        if cls._instance is None:
            cls._instance = cls(artifacts_dir)
        return cls._instance

    def predict(self, feature_df: pd.DataFrame) -> pd.DataFrame:
        """
        Run inference and return DataFrame with:
          unit_id, risk_probability, alert_triggered, top_features
        """
        available = [c for c in self.feature_cols if c in feature_df.columns]
        X = feature_df[available].fillna(0).values
        probs = self._model.predict_proba(X)[:, 1]
        alerts = probs >= self.production_threshold

        # Top 3 features by importance for the alert payload
        importances = self._model.feature_importances_
        top_idx = np.argsort(importances)[::-1][:3]
        top_features = [
            (available[i], round(float(importances[i]), 4))
            for i in top_idx if i < len(available)
        ]

        result = feature_df[["unit_id"]].copy()
        result["risk_probability"] = np.round(probs, 4)
        result["alert_triggered"] = alerts
        result["top_features"] = [top_features] * len(result)
        return result
