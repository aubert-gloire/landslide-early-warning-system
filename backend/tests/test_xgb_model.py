"""
Unit tests for XGBModel.predict() (app/ml/xgb_model.py) against the actual
trained artifact in ml/artifacts/ — not a mock. Previously covered only by
manual curl calls against the live API, pasted into the README.
"""

from pathlib import Path

import pandas as pd
import pytest

from app.ml.xgb_model import XGBModel

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ARTIFACTS_DIR = _REPO_ROOT / "ml" / "artifacts"


@pytest.fixture(scope="module")
def model():
    # XGBModel is a process-wide singleton (by design — see xgb_model.py) —
    # reset it so this test module always loads fresh from the artifact
    # instead of silently reusing whatever another test/process left behind.
    XGBModel._instance = None
    return XGBModel.load(_ARTIFACTS_DIR)


def _feature_row(model, **overrides):
    row = {c: 0.0 for c in model.feature_cols}
    row.update(overrides)
    row["unit_id"] = 0
    return pd.DataFrame([row])


class TestXGBModelPredict:
    def test_high_risk_scenario_from_readme(self, model):
        # README "Strategy 3" documents this exact input as
        # risk_probability_pct=98.9, alert_triggered=true against production.
        df = _feature_row(
            model, slope_angle=35, daily_mm=45, antecedent_3day_mm=120,
            antecedent_5day_mm=185, antecedent_10day_mm=280, twi=14,
            ndvi=0.25, soil_class=5,
        )
        result = model.predict(df)
        prob = result["risk_probability"].iloc[0]
        assert prob > 0.90
        assert bool(result["alert_triggered"].iloc[0]) is True

    def test_low_risk_scenario_from_readme(self, model):
        # README's paired low-risk example: risk_probability_pct=0.8,
        # alert_triggered=false.
        df = _feature_row(
            model, slope_angle=8, daily_mm=1, antecedent_3day_mm=3,
            antecedent_5day_mm=12, antecedent_10day_mm=18, twi=6,
            ndvi=0.65, soil_class=1,
        )
        result = model.predict(df)
        prob = result["risk_probability"].iloc[0]
        assert prob < 0.05
        assert bool(result["alert_triggered"].iloc[0]) is False

    def test_missing_optional_features_do_not_crash(self, model):
        # Mirrors a real slope unit missing e.g. landuse_class on a given
        # day — predict() only uses columns present in feature_cols AND the
        # input frame, then fillna(0) on what's left.
        df = pd.DataFrame([{
            "unit_id": 0, "slope_angle": 20, "daily_mm": 10,
            "antecedent_5day_mm": 50,
        }])
        result = model.predict(df)
        assert len(result) == 1
        assert 0.0 <= result["risk_probability"].iloc[0] <= 1.0

    def test_threshold_override_changes_alert_but_not_probability(self, model):
        df = _feature_row(model, slope_angle=15, daily_mm=5, antecedent_5day_mm=20)
        default_result = model.predict(df)
        overridden = model.predict(df, threshold_override=0.0001)
        assert bool(overridden["alert_triggered"].iloc[0]) is True
        assert default_result["risk_probability"].iloc[0] == overridden["risk_probability"].iloc[0]

    def test_top_features_returns_between_one_and_three(self, model):
        df = _feature_row(model, slope_angle=30, daily_mm=20, antecedent_5day_mm=100)
        top = model.predict(df)["top_features"].iloc[0]
        assert 1 <= len(top) <= 3

    def test_higher_antecedent_rainfall_does_not_decrease_risk(self, model):
        # Loose monotonicity check, not a strict guarantee for a tree
        # ensemble in general — but antecedent_5day_mm is the model's single
        # highest-importance feature (~46%, per model_metadata.json), so a
        # large increase with terrain held fixed should not lower the score.
        low = _feature_row(model, slope_angle=25, daily_mm=5, antecedent_5day_mm=10)
        high = _feature_row(model, slope_angle=25, daily_mm=5, antecedent_5day_mm=200)
        prob_low = model.predict(low)["risk_probability"].iloc[0]
        prob_high = model.predict(high)["risk_probability"].iloc[0]
        assert prob_high >= prob_low
