"""
Inference wrapper — loaded once at FastAPI startup via RFModel in backend/app/ml/rf_model.py.
"""

from __future__ import annotations

import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

ARTIFACTS_DIR = Path(__file__).parent.parent / "artifacts"


def load_model(artifacts_dir: Path | str | None = None):
    artifacts_dir = Path(artifacts_dir) if artifacts_dir else ARTIFACTS_DIR
    model_path = artifacts_dir / "rf_model.joblib"
    if not model_path.exists():
        raise FileNotFoundError(
            f"Model not found at {model_path}. Run scripts/train_model.py first."
        )
    model = joblib.load(model_path)
    logger.info("Model loaded from %s", model_path)
    return model


def predict_batch(
    model,
    feature_df: pd.DataFrame,
    feature_cols: list[str],
    threshold: float = 0.80,
) -> pd.DataFrame:
    """
    Run inference on a batch of slope-unit rows.

    Returns DataFrame with: unit_id, risk_probability, alert_triggered,
    top_features (list of (name, importance) tuples for the alert payload).
    """
    X = feature_df[feature_cols].fillna(0).values
    probs = model.predict_proba(X)[:, 1]
    alerts = (probs >= threshold).astype(bool)

    _clf = model.named_steps['clf'] if hasattr(model, 'named_steps') else model
    if hasattr(_clf, 'feature_importances_'):
        importances = _clf.feature_importances_
    elif hasattr(_clf, 'coef_'):
        importances = np.abs(_clf.coef_[0])
    else:
        importances = np.ones(len(feature_cols)) / len(feature_cols)
    top_idx = np.argsort(importances)[::-1][:3]
    top_features = [(feature_cols[i], round(float(importances[i]), 4)) for i in top_idx]

    result = feature_df[["unit_id"]].copy()
    result["risk_probability"] = np.round(probs, 4)
    result["alert_triggered"] = alerts
    result["top_features"] = [top_features] * len(result)

    logger.info(
        "Inference complete: %d units, %d alerts (threshold=%.2f)",
        len(result), int(alerts.sum()), threshold
    )
    return result
