"""
Unit tests for the risk-level and threshold-context logic in
app/routes/predict.py — pure functions with no I/O, previously covered
only by manual curl examples pasted into the README.
"""

import pytest

from app.routes.predict import _risk_level, _threshold_context


class TestRiskLevel:
    @pytest.mark.parametrize("prob,expected", [
        (0.0, "low"), (0.10, "low"), (0.39, "low"),
        (0.40, "medium"), (0.50, "medium"), (0.59, "medium"),
        (0.60, "high"), (0.70, "high"), (0.79, "high"),
        (0.80, "critical"), (0.90, "critical"), (1.0, "critical"),
    ])
    def test_boundaries(self, prob, expected):
        assert _risk_level(prob) == expected


class TestThresholdContext:
    def test_unknown_feature_returns_no_threshold(self):
        ctx = _threshold_context("not_a_real_feature", 5.0)
        assert ctx["status"] == "no_threshold"

    @pytest.mark.parametrize("value,expected_status", [
        (10.0, "normal"),
        (25.0, "elevated"),   # exactly at warn threshold
        (30.0, "elevated"),
        (35.0, "critical"),   # exactly at critical threshold
        (50.0, "critical"),
    ])
    def test_slope_angle_thresholds(self, value, expected_status):
        assert _threshold_context("slope_angle", value)["status"] == expected_status

    @pytest.mark.parametrize("value,expected_status", [
        (0.50, "normal"),
        (0.35, "elevated"),   # exactly at warn threshold
        (0.30, "elevated"),
        (0.20, "critical"),   # exactly at critical threshold
        (0.05, "critical"),
    ])
    def test_ndvi_is_inverse_of_other_features(self, value, expected_status):
        # Every other threshold feature treats "higher = worse"; NDVI is the
        # one exception (sparse vegetation = low NDVI = worse), handled by a
        # separate branch in _threshold_context — worth pinning down since
        # it's the easiest of the six thresholds to break with a copy-paste
        # edit of the others.
        assert _threshold_context("ndvi", value)["status"] == expected_status

    def test_context_message_includes_the_value(self):
        ctx = _threshold_context("slope_angle", 40.0)
        assert "40.0" in ctx["context"]
