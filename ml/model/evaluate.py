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
    {
        "name": "May 2018 Northern Province (Gakenke)",
        "date": "2018-05-08",
        "district": "Gakenke",
        "lat": -1.7100,
        "lon": 29.7700,
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
        processed_dir: Path | str,
        slope_units_gdf,
        output_path: Path | str | None = None,
    ) -> pd.DataFrame:
        """
        For each documented event, check whether the model would have produced
        a probability >= alert_threshold on the event date (or the two days before).

        Static terrain/soil/NDVI/landuse features are sourced the same way the
        live inference path does (FeatureMatrixBuilder._load_static, covering
        every unit) — NOT from training_matrix.parquet, which only contains the
        ~184/396 units actually sampled into the training set. Sourcing from the
        training matrix previously meant any backtest event landing on an
        unsampled unit silently produced no prediction at all (status='no_data'
        counted as a miss), rather than a genuine model failure. Rainfall comes
        from chirps_historical.parquet directly for the same reason — it has
        full history for every unit, unlike the sparse training matrix.

        Returns a report DataFrame with one row per event.
        """
        from shapely.geometry import Point

        from ml.features.matrix import DYNAMIC_FEATURES, FeatureMatrixBuilder

        processed_dir = Path(processed_dir)
        static = FeatureMatrixBuilder(processed_dir)._load_static(slope_units_gdf)

        chirps = pd.read_parquet(processed_dir / "chirps_historical.parquet")
        chirps["date"] = pd.to_datetime(chirps["date"])

        results = []
        for event in BACKTEST_EVENTS:
            event_date = pd.Timestamp(event["date"])
            check_dates = [event_date, event_date - pd.Timedelta(days=1), event_date - pd.Timedelta(days=2)]

            # Find the slope unit containing this event point (fall back to
            # nearest centroid if the point doesn't land inside any polygon).
            pt = Point(event["lon"], event["lat"])
            matching = slope_units_gdf[slope_units_gdf.geometry.contains(pt)]
            if matching.empty:
                dists = slope_units_gdf.geometry.centroid.distance(pt)
                matching = slope_units_gdf.iloc[[dists.idxmin()]]
            unit_id = int(matching.iloc[0]["unit_id"])

            static_row = static[static["unit_id"] == unit_id]
            if static_row.empty:
                logger.warning("No static features for unit %d (event %s)", unit_id, event["name"])
                results.append({**event, "unit_id": unit_id, "max_probability": None, "alert_triggered": False, "status": "no_static_features"})
                continue
            static_vals = static_row.iloc[0].to_dict()

            rain_rows = chirps[(chirps["unit_id"] == unit_id) & (chirps["date"].isin(check_dates))]
            if rain_rows.empty:
                logger.warning("No CHIRPS rainfall for unit %d on backtest dates (event %s)", unit_id, event["name"])
                results.append({**event, "unit_id": unit_id, "max_probability": None, "alert_triggered": False, "status": "no_rainfall_data"})
                continue

            feature_rows = []
            for _, rain_row in rain_rows.iterrows():
                row = {c: static_vals.get(c) for c in self.feature_cols if c not in DYNAMIC_FEATURES}
                for c in DYNAMIC_FEATURES:
                    if c in rain_row:
                        row[c] = rain_row[c]
                feature_rows.append(row)

            X = pd.DataFrame(feature_rows)[self.feature_cols].values
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
