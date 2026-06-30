"""
Backtesting against documented Northern Province landslide events.

Primary benchmark: May 2023 Northern Province event.
Secondary benchmark: May 2018 event (Habimana et al. 2020 dataset).

A successful backtest means the model would have issued alerts for the
documented event slope units in the 0–2 days prior to the event date,
given the actual CHIRPS rainfall data for that period.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

BACKTEST_EVENTS = [
    {
        "name": "May 2023 Northern Province",
        "date": "2023-05-02",
        "district": "Musanze",
        "lat": -1.4996,
        "lon": 29.6346,
        "is_primary": True,
    },
    {
        "name": "May 2023 Northern Province (Gakenke)",
        "date": "2023-05-04",
        "district": "Gakenke",
        "lat": -1.6995,
        "lon": 29.7855,
        "is_primary": True,
    },
    {
        "name": "May 2018 Northern Province",
        "date": "2018-05-06",
        "district": "Burera",
        "lat": -1.3990,
        "lon": 29.8435,
        "is_primary": False,
    },
]


class Backtester:
    def __init__(self, model, feature_cols: list[str], alert_threshold: float = 0.80):
        self.model = model
        self.feature_cols = feature_cols
        self.alert_threshold = alert_threshold

    def run(
        self,
        matrix_path: Path | str,
        slope_units_gdf,
        output_path: Path | str | None = None,
    ) -> pd.DataFrame:
        """
        For each documented event, check whether the model would have produced
        a probability ≥ alert_threshold on the event date (or the day before).

        Returns a report DataFrame with one row per event.
        """
        matrix = pd.read_parquet(matrix_path)
        matrix["date"] = pd.to_datetime(matrix["date"])

        from shapely.geometry import Point
        import geopandas as gpd

        results = []
        for event in BACKTEST_EVENTS:
            event_date = pd.Timestamp(event["date"])
            check_dates = [event_date, event_date - pd.Timedelta(days=1), event_date - pd.Timedelta(days=2)]

            # Find the slope unit containing this event point
            pt = Point(event["lon"], event["lat"])
            matching = slope_units_gdf[slope_units_gdf.geometry.contains(pt)]
            if matching.empty:
                logger.warning("Event %s does not match any slope unit", event["name"])
                results.append({**event, "max_probability": None, "alert_triggered": False, "status": "unit_not_found"})
                continue

            unit_id = matching.iloc[0]["unit_id"]

            # Find highest probability in check window
            rows = matrix[
                (matrix["unit_id"] == unit_id) & (matrix["date"].isin(check_dates))
            ]

            if rows.empty:
                logger.warning("No matrix rows for unit %d on backtest dates", unit_id)
                results.append({**event, "unit_id": unit_id, "max_probability": None, "alert_triggered": False, "status": "no_data"})
                continue

            X = rows[self.feature_cols].fillna(rows[self.feature_cols].median()).values
            probs = self.model.predict_proba(X)[:, 1]
            max_prob = float(probs.max())
            alert = bool(max_prob >= self.alert_threshold)

            results.append({
                **event,
                "unit_id": unit_id,
                "max_probability": round(max_prob, 4),
                "alert_triggered": alert,
                "status": "detected" if alert else "missed",
            })

            logger.info(
                "[%s] %s | unit=%d | max_prob=%.4f | alert=%s",
                "PRIMARY" if event["is_primary"] else "secondary",
                event["name"], unit_id, max_prob,
                "YES" if alert else "NO (MISSED)"
            )

        report = pd.DataFrame(results)

        primary = report[report["is_primary"]]
        primary_detected = primary["alert_triggered"].sum()
        logger.info(
            "Backtest summary: %d/%d primary events detected at threshold %.2f",
            primary_detected, len(primary), self.alert_threshold
        )

        if output_path:
            report.to_csv(output_path, index=False)
            logger.info("Backtest report saved → %s", output_path)

        return report
