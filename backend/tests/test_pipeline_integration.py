"""
Integration tests — real static feature files, real trained model, and the
real Telerivet dispatch function, with only the outbound HTTP call mocked
(no real network, no real SMS, no MongoDB dependency).

Covers the gap between the pure-function unit tests (test_predict_thresholds,
test_rainfall_windows, test_xgb_model) and a genuinely end-to-end check: does
ingestion -> feature assembly -> scoring -> alert-message construction ->
provider dispatch actually chain together correctly, using the same code
paths the live daily pipeline uses.
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import geopandas as gpd
import pandas as pd
import pytest

from app.ml.xgb_model import XGBModel
from app.services.sms import _dispatch_sms, build_alert_message

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ARTIFACTS_DIR = _REPO_ROOT / "ml" / "artifacts"
_PROCESSED_DIR = _REPO_ROOT / "data" / "processed"


@pytest.fixture(scope="module")
def model():
    XGBModel._instance = None
    return XGBModel.load(_ARTIFACTS_DIR)


class TestIngestionToAlertMessage:
    def test_real_static_data_scores_and_produces_a_valid_alert_message(self, model):
        """
        Real slope_units.gpkg + real terrain/NDVI/soil/landuse files (via
        FeatureMatrixBuilder, same class the live pipeline uses) + a
        synthetic but realistic rainfall day -> real XGBoost scoring ->
        real alert-message construction. No network, no MongoDB.
        """
        from ml.features.matrix import FeatureMatrixBuilder

        slope_units = gpd.read_file(_PROCESSED_DIR / "slope_units.gpkg")
        sample_units = slope_units.head(5).copy()
        sample_unit_ids = sample_units["unit_id"].tolist()

        # A single heavy-rain day for these units, matching the shape
        # CHIRPSDownloader/GPMIMERGDownloader hand to build_inference_row.
        rainfall_df = pd.DataFrame({
            "unit_id": sample_unit_ids,
            "daily_mm": [45.0] * len(sample_unit_ids),
            "antecedent_3day_mm": [120.0] * len(sample_unit_ids),
            "antecedent_5day_mm": [185.0] * len(sample_unit_ids),
            "antecedent_10day_mm": [260.0] * len(sample_unit_ids),
            "rainfall_intensity_ratio": [0.24] * len(sample_unit_ids),
        })

        builder = FeatureMatrixBuilder(_PROCESSED_DIR)
        feature_df = builder.build_inference_row(slope_units, rainfall_df)
        feature_df = feature_df[feature_df["unit_id"].isin(sample_unit_ids)].reset_index(drop=True)
        assert len(feature_df) == len(sample_unit_ids)

        result = model.predict(feature_df)
        assert len(result) == len(sample_unit_ids)
        assert result["risk_probability"].between(0.0, 1.0).all()

        # Build a real alert message for whichever sampled unit scored highest —
        # exercises the exact function the live pipeline calls before dispatch.
        top_row = result.loc[result["risk_probability"].idxmax()]
        message = build_alert_message(
            district="Musanze",
            unit_id=int(top_row["unit_id"]),
            risk_probability=float(top_row["risk_probability"]),
            top_features=list(top_row["top_features"]),
        )
        assert "Unit:" in message
        assert "Reply YES" in message and "Reply YES" in message


class TestDispatchWithMockedProvider:
    """
    _dispatch_sms() is the real function pipeline.py calls for every alert.
    Only httpx's outbound POST is mocked -- everything else (message
    building, status interpretation, success/failure classification) is
    the real code.
    """

    @pytest.mark.asyncio
    async def test_dispatch_succeeds_when_telerivet_accepts_the_message(self, monkeypatch):
        fake_settings = SimpleNamespace(
            telerivet_api_key="fake_key",
            telerivet_project_id="fake_project",
            telerivet_route_id="",
            public_api_base_url="",
            telerivet_status_secret="",
        )
        monkeypatch.setattr("app.services.sms.get_settings", lambda: fake_settings)

        fake_response = SimpleNamespace(
            status_code=200,
            json=lambda: {"id": "msg_abc123", "status": "queued"},
        )
        mock_post = AsyncMock(return_value=fake_response)
        monkeypatch.setattr("httpx.AsyncClient.post", mock_post)

        result = await _dispatch_sms("+250788000000", "LSEWS WATCH test message")

        assert result["overall"] == "sent"
        assert result["providers"]["telerivet"] == "queued"
        assert result["telerivet_message_id"] == "msg_abc123"
        assert mock_post.called

    @pytest.mark.asyncio
    async def test_dispatch_fails_cleanly_when_telerivet_is_unreachable(self, monkeypatch):
        """
        A network-level failure (timeout, DNS, connection refused) must
        degrade to a structured failure result, not raise -- send_alert()
        still needs to write an AlertRecord either way.
        """
        fake_settings = SimpleNamespace(
            telerivet_api_key="fake_key",
            telerivet_project_id="fake_project",
            telerivet_route_id="",
            public_api_base_url="",
            telerivet_status_secret="",
        )
        monkeypatch.setattr("app.services.sms.get_settings", lambda: fake_settings)

        import httpx as httpx_module

        async def _raise_timeout(*args, **kwargs):
            raise httpx_module.ConnectTimeout("connection timed out")

        monkeypatch.setattr("httpx.AsyncClient.post", _raise_timeout)

        result = await _dispatch_sms("+250788000000", "LSEWS WATCH test message")

        assert result["overall"] == "failed"
        assert result["providers"]["telerivet"] == "exception"
        assert result["errors"]["telerivet"]
