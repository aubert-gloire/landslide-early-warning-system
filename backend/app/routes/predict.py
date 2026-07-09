"""
POST /api/predict  — single-point prediction with feature explanation.

Accepts explicit feature values, validates them, runs inference, and returns:
  - risk_probability and risk_level
  - top contributing features with their values and thresholds
  - a human-readable risk narrative explaining WHY the model flagged risk
  - validation errors for out-of-range or physically impossible inputs

This endpoint is used for demo, testing, and showcasing model explainability.
Invalid inputs (negative rainfall, slope > 90°, etc.) are rejected with
422 Unprocessable Entity — demonstrating system robustness.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from ..config import get_settings
from ..database import get_db
from ..ml.xgb_model import XGBModel
from ..services.sms import send_alert

router = APIRouter()

# Evidence-based thresholds for Rwanda Northern Province (Kuradusenge et al. 2020)
THRESHOLDS = {
    "slope_angle":         {"warn": 25.0, "critical": 35.0, "unit": "°",   "label": "slope angle"},
    "daily_mm":            {"warn": 25.0, "critical": 50.0, "unit": "mm",  "label": "daily rainfall"},
    "antecedent_5day_mm":  {"warn": 80.0, "critical": 150.0,"unit": "mm",  "label": "5-day antecedent rainfall"},
    "twi":                 {"warn": 8.0,  "critical": 12.0, "unit": "",    "label": "topographic wetness index"},
    "ndvi":                {"warn": 0.35, "critical": 0.20, "unit": "",    "label": "NDVI (vegetation cover)"},
    "drainage_density":    {"warn": 2.0,  "critical": 4.0,  "unit": "km/km²", "label": "drainage density"},
}


class PredictRequest(BaseModel):
    slope_angle: float = Field(
        ..., ge=0.0, le=90.0,
        description="Slope angle in degrees (0–90). Values above 90° are physically impossible.",
        json_schema_extra={"example": 38.5},
    )
    daily_mm: float = Field(
        ..., ge=0.0, le=600.0,
        description="Daily rainfall in mm. Must be non-negative. Max 600mm (global 24h record).",
        json_schema_extra={"example": 62.0},
    )
    antecedent_5day_mm: float = Field(
        ..., ge=0.0, le=2000.0,
        description="Cumulative rainfall over the previous 5 days in mm.",
        json_schema_extra={"example": 175.0},
    )
    antecedent_3day_mm: float | None = Field(
        default=None, ge=0.0, le=600.0,
        description="Cumulative rainfall over the previous 3 days in mm (shallow soil saturation).",
    )
    antecedent_10day_mm: float | None = Field(
        default=None, ge=0.0, le=3000.0,
        description="Cumulative rainfall over the previous 10 days in mm (deep clay soil saturation).",
    )
    rainfall_intensity_ratio: float | None = Field(
        default=None, ge=0.0,
        description="daily_mm / (antecedent_5day_mm + 1). High = sudden burst; low = gradual accumulation.",
    )
    aspect: float | None = Field(
        default=None, ge=0.0, le=360.0,
        description="Slope aspect in degrees (0=North, 90=East, 180=South, 270=West).",
    )
    twi: float | None = Field(
        default=None, ge=0.0, le=30.0,
        description="Topographic Wetness Index (ln(catchment_area / tan(slope))). Typical range 2–20.",
    )
    drainage_density: float | None = Field(
        default=None, ge=0.0, le=20.0,
        description="Stream network density in km of channel per km² of catchment area.",
    )
    ndvi: float | None = Field(
        default=None, ge=-1.0, le=1.0,
        description="Normalised Difference Vegetation Index (-1 to 1). Low NDVI = sparse vegetation = less root cohesion.",
    )
    soil_class: int | None = Field(
        default=None, ge=1, le=10,
        description="SoilGrids soil class (integer 1–10). Class 5 = clay-rich = high saturation risk.",
    )
    landuse_class: int | None = Field(
        default=None, ge=10, le=100,
        description="ESA WorldCover 2021 class (10=forest, 30=grassland, 40=cropland, 60=bare). Low values = lower risk.",
    )

    @model_validator(mode="after")
    def physical_consistency(self) -> "PredictRequest":
        if self.daily_mm > 0 and self.antecedent_5day_mm == 0:
            # Not an error — could be first rain after dry period — but flag it
            pass
        if self.slope_angle == 0 and (self.daily_mm or 0) > 0:
            # Flat land with rain — no slope risk; model will return low probability
            pass
        return self


def _risk_level(prob: float) -> str:
    if prob >= 0.80:
        return "critical"
    if prob >= 0.60:
        return "high"
    if prob >= 0.40:
        return "medium"
    return "low"


def _threshold_context(feature: str, value: float) -> dict:
    """Return how a feature value compares to known risk thresholds."""
    t = THRESHOLDS.get(feature)
    if t is None:
        return {"status": "no_threshold", "context": ""}

    unit = t["unit"]
    label = t["label"]

    # NDVI is inverse — low value is worse
    if feature == "ndvi":
        if value <= t["critical"]:
            return {"status": "critical", "context": f"{label} {value:.2f} is below critical threshold {t['critical']} — very sparse vegetation"}
        if value <= t["warn"]:
            return {"status": "elevated", "context": f"{label} {value:.2f} is below warning threshold {t['warn']} — reduced root cohesion"}
        return {"status": "normal", "context": f"{label} {value:.2f} — adequate vegetation cover"}

    if value >= t["critical"]:
        return {"status": "critical", "context": f"{label} {value:.1f}{unit} exceeds critical threshold {t['critical']}{unit}"}
    if value >= t["warn"]:
        return {"status": "elevated", "context": f"{label} {value:.1f}{unit} above warning threshold {t['warn']}{unit}"}
    return {"status": "normal", "context": f"{label} {value:.1f}{unit} within normal range"}


def _build_narrative(
    req: PredictRequest,
    prob: float,
    risk_level: str,
    top_features: list[dict],
) -> str:
    """
    Produce a human-readable explanation of why the model assigned this risk level.
    Mirrors the reasoning an expert hydrologist would apply.
    """
    parts: list[str] = []

    # Slope
    if req.slope_angle >= 35:
        parts.append(f"steep slope ({req.slope_angle:.1f}°, critical ≥35°)")
    elif req.slope_angle >= 25:
        parts.append(f"moderately steep slope ({req.slope_angle:.1f}°)")

    # Rainfall — the primary trigger in Rwandan landslides
    if req.daily_mm >= 50:
        parts.append(f"extreme daily rainfall ({req.daily_mm:.0f}mm, threshold 50mm)")
    elif req.daily_mm >= 25:
        parts.append(f"elevated daily rainfall ({req.daily_mm:.0f}mm)")

    if req.antecedent_5day_mm >= 150:
        parts.append(f"heavily saturated antecedent conditions ({req.antecedent_5day_mm:.0f}mm over 5 days)")
    elif req.antecedent_5day_mm >= 80:
        parts.append(f"elevated antecedent moisture ({req.antecedent_5day_mm:.0f}mm over 5 days)")

    # Vegetation
    if req.ndvi is not None and req.ndvi < 0.35:
        parts.append(f"low vegetation cover (NDVI {req.ndvi:.2f}, poor root cohesion)")

    # TWI
    if req.twi is not None and req.twi >= 10:
        parts.append(f"high terrain convergence (TWI {req.twi:.1f}, water accumulation zone)")

    if not parts:
        parts.append("input conditions are within normal range")

    # Compose sentence
    factors_str = "; ".join(parts)
    if risk_level in ("critical", "high"):
        intro = f"HIGH RISK flagged: {factors_str}."
        outro = " Kuradusenge et al. (2020) identify steep slopes combined with high antecedent rainfall as the primary trigger mechanism for Northern Province landslides."
    elif risk_level == "medium":
        intro = f"MODERATE RISK: {factors_str}."
        outro = " Conditions are elevated but do not yet meet the alert threshold. Monitor closely."
    else:
        intro = f"LOW RISK: {factors_str}."
        outro = " Current conditions do not indicate imminent landslide hazard."

    # Name the top driver from model importances
    if top_features:
        top_name = top_features[0]["feature"].replace("_", " ")
        intro += f" Primary model driver: {top_name}."

    return intro + outro


@router.post("/predict")
async def predict_point(body: PredictRequest):
    """
    Run a single-point landslide risk prediction.

    Returns risk probability, level, top contributing features with threshold context,
    and a human-readable narrative explaining the model's reasoning.

    Validates all inputs — negative rainfall, slope > 90°, NDVI outside [-1,1], etc.
    return 422 with field-level error messages.
    """
    settings = get_settings()
    artifacts_dir = settings.artifacts_path()

    try:
        model_wrapper = XGBModel.load(artifacts_dir)
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. Run the training notebook and restart the API.",
        )

    # Build feature row — use model's expected feature order
    # Auto-derive optional features when not supplied
    ant3  = body.antecedent_3day_mm
    ant10 = body.antecedent_10day_mm
    ratio = body.rainfall_intensity_ratio
    if ratio is None:
        ratio = round(body.daily_mm / (body.antecedent_5day_mm + 1.0), 4)

    feature_vals = {
        "slope_angle":             body.slope_angle,
        "aspect":                  body.aspect,
        "twi":                     body.twi,
        "drainage_density":        body.drainage_density,
        "ndvi":                    body.ndvi,
        "soil_class":              body.soil_class,
        "landuse_class":           body.landuse_class,
        "daily_mm":                body.daily_mm,
        "antecedent_3day_mm":      ant3,
        "antecedent_5day_mm":      body.antecedent_5day_mm,
        "antecedent_10day_mm":     ant10,
        "rainfall_intensity_ratio": ratio,
    }

    # Only use columns the model was trained on
    available = [c for c in model_wrapper.feature_cols if c in feature_vals]
    row = {c: feature_vals[c] for c in available}
    feature_df = pd.DataFrame([row])
    feature_df["unit_id"] = 0  # dummy id

    result = model_wrapper.predict(feature_df)
    prob = float(result["risk_probability"].iloc[0])
    alert = bool(result["alert_triggered"].iloc[0])
    raw_top = result["top_features"].iloc[0]  # list of (name, importance) tuples

    # Enrich top features with actual input values and threshold context
    top_features_enriched = []
    for name, imp in raw_top:
        val = feature_vals.get(name)
        ctx = _threshold_context(name, val) if val is not None else {"status": "no_value", "context": ""}
        top_features_enriched.append({
            "feature":    name,
            "label":      name.replace("_", " "),
            "value":      val,
            "importance": imp,
            "threshold_status":  ctx["status"],
            "threshold_context": ctx["context"],
        })

    risk_level = _risk_level(prob)
    narrative = _build_narrative(body, prob, risk_level, top_features_enriched)

    return {
        "risk_probability":   round(prob, 4),
        "risk_probability_pct": round(prob * 100, 1),
        "risk_level":          risk_level,
        "alert_triggered":     alert,
        "production_threshold": model_wrapper.production_threshold,
        "top_features":        top_features_enriched,
        "risk_narrative":      narrative,
        "input_summary": {
            "slope_angle":        body.slope_angle,
            "daily_mm":           body.daily_mm,
            "antecedent_5day_mm": body.antecedent_5day_mm,
        },
    }


class ManualAlertRequest(PredictRequest):
    district: str = Field(
        ..., min_length=1,
        description="District name to alert (must match recipients in MongoDB).",
        json_schema_extra={"example": "Musanze"},
    )
    force: bool = Field(
        False,
        description="Send SMS even if model probability is below the production threshold.",
    )


@router.post("/predict/alert")
async def predict_and_alert(body: ManualAlertRequest):
    """
    Expert override: run prediction and dispatch SMS to all active recipients
    in the specified district. Intended for meteorologists who have live data
    and want to send a warning manually.

    If force=true, sends even when model probability is below threshold.
    """
    settings = get_settings()
    try:
        model_wrapper = XGBModel.load(settings.artifacts_path())
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Model not loaded.")

    ant3  = body.antecedent_3day_mm
    ant10 = body.antecedent_10day_mm
    ratio = body.rainfall_intensity_ratio
    if ratio is None:
        ratio = round(body.daily_mm / (body.antecedent_5day_mm + 1.0), 4)

    feature_vals = {
        "slope_angle": body.slope_angle, "aspect": body.aspect,
        "twi": body.twi, "drainage_density": body.drainage_density,
        "ndvi": body.ndvi, "soil_class": body.soil_class,
        "landuse_class": body.landuse_class, "daily_mm": body.daily_mm,
        "antecedent_3day_mm": ant3, "antecedent_5day_mm": body.antecedent_5day_mm,
        "antecedent_10day_mm": ant10, "rainfall_intensity_ratio": ratio,
    }
    available = [c for c in model_wrapper.feature_cols if c in feature_vals]
    feature_df = pd.DataFrame([{c: feature_vals[c] for c in available}])
    feature_df["unit_id"] = 0

    result_df = model_wrapper.predict(feature_df)
    prob = float(result_df["risk_probability"].iloc[0])
    alert_triggered = bool(result_df["alert_triggered"].iloc[0])
    top_features = result_df["top_features"].iloc[0]

    should_send = alert_triggered or body.force
    if not should_send:
        return {
            "sent": False,
            "reason": f"Model probability {prob*100:.1f}% is below threshold "
                      f"{model_wrapper.production_threshold*100:.0f}%. "
                      "Pass force=true to send anyway.",
            "risk_probability_pct": round(prob * 100, 1),
            "risk_level": _risk_level(prob),
        }

    db = get_db()
    recipients = await db.recipients.find(
        {"$or": [{"district": body.district}, {"districts": body.district}], "active": True}
    ).to_list(length=100)

    if not recipients:
        raise HTTPException(
            status_code=404,
            detail=f"No active recipients found for district '{body.district}'.",
        )

    # Look up the highest-risk slope unit for this district to get real GPS coordinates
    from datetime import date as _date
    today = _date.today().isoformat()
    top_unit = await db.predictions.find_one(
        {"district": body.district, "date": today},
        sort=[("risk_probability", -1)],
    )
    centroid_lat = centroid_lon = None
    unit_id = 0
    sector = ""
    if top_unit:
        unit_id = top_unit.get("slope_unit_id", 0)
        sector  = top_unit.get("sector", "")
        unit_doc = await db.slope_units.find_one({"unit_id": unit_id})
        if unit_doc:
            centroid_lat = unit_doc.get("centroid_lat")
            centroid_lon = unit_doc.get("centroid_lon")

    sent_to = []
    for recipient in recipients:
        alert_id = await send_alert(
            phone=recipient["phone"],
            recipient_id=recipient["recipient_id"],
            prediction_id="manual",
            district=body.district,
            sector=sector,
            unit_id=unit_id,
            risk_probability=prob,
            top_features=top_features,
            centroid_lat=centroid_lat,
            centroid_lon=centroid_lon,
        )
        sent_to.append({"name": recipient["name"], "phone": recipient["phone"], "alert_id": alert_id})

    return {
        "sent": True,
        "district": body.district,
        "sms_count": len(sent_to),
        "recipients": sent_to,
        "risk_probability_pct": round(prob * 100, 1),
        "risk_level": _risk_level(prob),
        "forced": body.force and not alert_triggered,
    }
