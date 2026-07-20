"""
GET /api/weather — live current conditions per district, from Open-Meteo
(free, no API key required).

This is a display-only supplement to the ML pipeline's satellite rainfall
(CHIRPS/IMERG) — it never feeds model features. It exists so officers see
"here's what's actually happening right now" alongside the risk assessment,
especially on days the satellite rainfall pipeline has no data for that unit.
"""

import logging

import httpx
from fastapi import APIRouter

router = APIRouter()
logger = logging.getLogger(__name__)

# District centroids — averaged from slope_units.centroid_lat/lon in MongoDB.
DISTRICT_COORDS = {
    "Gakenke": (-1.7294, 29.6828),
    "Burera":  (-1.2152, 29.8106),
    "Musanze": (-1.3718, 29.5164),
    "Gicumbi": (-1.3917, 30.2610),
}

# WMO weather codes returned by Open-Meteo — subset relevant to this region.
_WMO_LABELS = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Light rain", 63: "Moderate rain", 65: "Heavy rain",
    80: "Light rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
}


@router.get("/weather")
async def get_current_weather():
    """Current conditions for all four districts in one batched Open-Meteo call."""
    districts = list(DISTRICT_COORDS.keys())
    lats = ",".join(str(DISTRICT_COORDS[d][0]) for d in districts)
    lons = ",".join(str(DISTRICT_COORDS[d][1]) for d in districts)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lats,
                    "longitude": lons,
                    "current": "temperature_2m,precipitation,weather_code,relative_humidity_2m",
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                    "timezone": "Africa/Kigali",
                },
            )
        resp.raise_for_status()
        results = resp.json()
    except Exception as exc:
        logger.warning("Open-Meteo fetch failed: %s", exc)
        return {"available": False, "districts": {}}

    out = {}
    for district, r in zip(districts, results):
        cur = r.get("current", {})
        daily = r.get("daily", {})
        code = cur.get("weather_code")
        out[district] = {
            "temperature_c":       cur.get("temperature_2m"),
            "temperature_min_c":   (daily.get("temperature_2m_min") or [None])[0],
            "temperature_max_c":   (daily.get("temperature_2m_max") or [None])[0],
            "precipitation_mm":    cur.get("precipitation"),
            "precip_chance_pct":   (daily.get("precipitation_probability_max") or [None])[0],
            "humidity_pct":        cur.get("relative_humidity_2m"),
            "condition":           _WMO_LABELS.get(code, "Unknown"),
            "weather_code":        code,
            "observed_at":         cur.get("time"),
        }

    return {"available": True, "districts": out}
