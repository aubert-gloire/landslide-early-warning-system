"""
XGBModel — singleton wrapper around the trained XGBoost joblib artifact.
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


class XGBModel:
    _instance: "XGBModel | None" = None

    def __init__(self, artifacts_dir: Path):
        model_path = artifacts_dir / "rf_model.joblib"   # artifact filename kept for compatibility
        meta_path  = artifacts_dir / "model_metadata.json"

        if not model_path.exists():
            raise FileNotFoundError(
                f"Model artifact not found at {model_path}. "
                "Run scripts/train_model.py before starting the API."
            )

        self._model = joblib.load(model_path)
        logger.info("XGBoost model loaded from %s", model_path)

        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
            self.feature_cols: list[str]        = meta.get("feature_cols", [])
            self.production_threshold: float    = meta.get("production_threshold", 0.80)
            self.feature_importances: dict      = meta.get("feature_importances", {})
        else:
            logger.warning("model_metadata.json not found — using defaults")
            self.feature_cols = [
                "slope_angle", "aspect", "twi", "drainage_density",
                "ndvi", "soil_class", "daily_mm", "antecedent_5day_mm",
            ]
            self.production_threshold = 0.80
            self.feature_importances = {}

    @classmethod
    def load(cls, artifacts_dir: Path) -> "XGBModel":
        if cls._instance is None:
            cls._instance = cls(artifacts_dir)
        return cls._instance

    def predict(self, feature_df: pd.DataFrame, threshold_override: float | None = None) -> pd.DataFrame:
        """
        Run inference and return DataFrame with:
          unit_id, risk_probability, alert_triggered, top_features

        threshold_override: temporarily lower the alert threshold (e.g. after seismic event).
        """
        threshold = threshold_override if threshold_override is not None else self.production_threshold
        available = [c for c in self.feature_cols if c in feature_df.columns]
        X = feature_df[available].fillna(0).values
        probs  = self._model.predict_proba(X)[:, 1]
        alerts = probs >= threshold

        _clf = self._model.named_steps["clf"] if hasattr(self._model, "named_steps") else self._model
        if hasattr(_clf, "feature_importances_"):
            importances = _clf.feature_importances_
        elif hasattr(_clf, "coef_"):
            importances = np.abs(_clf.coef_[0])
        else:
            importances = np.ones(len(available)) / len(available)
        top_idx = np.argsort(importances)[::-1][:3]
        top_features = [
            (available[i], round(float(importances[i]), 4))
            for i in top_idx if i < len(available)
        ]

        result = feature_df[["unit_id"]].copy()
        result["risk_probability"] = np.round(probs, 4)
        result["alert_triggered"]  = alerts
        result["top_features"]     = [top_features] * len(result)
        return result
