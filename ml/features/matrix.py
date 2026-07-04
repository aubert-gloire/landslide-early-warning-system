"""
Feature matrix builder — the architectural core of the pipeline.

Join logic:
  slope_unit_id is the shared key across all data sources.
  Static features (terrain + NDVI + soil) attach once per unit.
  Dynamic features (rainfall) attach per unit per day.
  Labels attach by point-in-polygon + date proximity (training only).

For training: produces a flat Parquet with one row per (unit_id, date).
For inference: produces one row per unit_id for today.

Feature columns (12 total):
  Static:  slope_angle, aspect, twi, drainage_density, ndvi, soil_class, landuse_class
  Dynamic: daily_mm, antecedent_3day_mm, antecedent_5day_mm,
           antecedent_10day_mm, rainfall_intensity_ratio
"""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

STATIC_FEATURES = [
    "slope_angle", "aspect", "twi", "drainage_density",
    "ndvi", "soil_class", "landuse_class",
]
DYNAMIC_FEATURES = [
    "daily_mm", "antecedent_3day_mm", "antecedent_5day_mm",
    "antecedent_10day_mm", "rainfall_intensity_ratio",
]
FEATURE_COLS = STATIC_FEATURES + DYNAMIC_FEATURES
LABEL_COL = "label"


class FeatureMatrixBuilder:
    def __init__(self, processed_dir: Path | str):
        self.processed_dir = Path(processed_dir)

    def _load_static(self, slope_units_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
        """Load static terrain + NDVI + soil features joined on unit_id."""
        base = slope_units_gdf[["unit_id", "district", "centroid_lat", "centroid_lon"]].copy()

        # Terrain features — computed by DEMProcessor and stored per-unit
        terrain_path = self.processed_dir / "terrain_per_unit.parquet"
        if terrain_path.exists():
            terrain = pd.read_parquet(terrain_path)
            base = base.merge(terrain, on="unit_id", how="left")
        else:
            logger.warning(
                "terrain_per_unit.parquet not found — terrain features will be NaN. "
                "Run scripts/setup_db.py to derive terrain features from DEM."
            )
            for col in ["slope_angle", "aspect", "twi", "drainage_density"]:
                base[col] = np.nan

        # NDVI
        ndvi_files = sorted(self.processed_dir.glob("ndvi_*.parquet"), reverse=True)
        if ndvi_files:
            ndvi = pd.read_parquet(ndvi_files[0])
            base = base.merge(ndvi, on="unit_id", how="left")
        else:
            logger.warning("No NDVI Parquet found — ndvi will be NaN")
            base["ndvi"] = np.nan

        # Soil class (modal integer code)
        soil_path = self.processed_dir / "soil_per_unit.parquet"
        if soil_path.exists():
            soil = pd.read_parquet(soil_path)[["unit_id", "soil_class"]]
            base = base.merge(soil, on="unit_id", how="left")
        else:
            logger.warning("No soil Parquet found — soil_class will default to 4 (loam)")
            base["soil_class"] = 4

        base["soil_class"] = base["soil_class"].fillna(4).astype(int)

        # ESA WorldCover 2021 land use class (run scripts/fetch_worldcover.py first)
        landuse_path = self.processed_dir / "landuse_per_unit.parquet"
        if landuse_path.exists():
            landuse = pd.read_parquet(landuse_path)[["unit_id", "landuse_class"]]
            base = base.merge(landuse, on="unit_id", how="left")
        else:
            logger.warning(
                "landuse_per_unit.parquet not found — landuse_class will be NaN. "
                "Run scripts/fetch_worldcover.py to extract ESA WorldCover 2021."
            )
            base["landuse_class"] = np.nan
        base["landuse_class"] = pd.to_numeric(base["landuse_class"], errors="coerce")

        return base

    def build_training_matrix(
        self,
        slope_units_gdf: gpd.GeoDataFrame,
        labels_df: pd.DataFrame,
        negative_ratio: int = 10,
        random_seed: int = 42,
    ) -> pd.DataFrame:
        """
        Build full training feature matrix with labels.

        Positive rows: all (unit_id, date) pairs from labels_df.
        Negative rows: randomly sampled unit-day pairs at negative_ratio:1.

        Returns DataFrame with FEATURE_COLS + [label, unit_id, date, district].
        """
        static = self._load_static(slope_units_gdf)
        chirps_path = self.processed_dir / "chirps_historical.parquet"
        if not chirps_path.exists():
            raise FileNotFoundError(
                "chirps_historical.parquet not found. "
                "Run CHIRPSDownloader.build_historical_series() first."
            )
        rainfall = pd.read_parquet(chirps_path)
        rainfall["date"] = pd.to_datetime(rainfall["date"])

        # --- Positive samples ---
        labels_df = labels_df.copy()
        labels_df["date"] = pd.to_datetime(labels_df["date"])
        pos = labels_df[["unit_id", "date", "label"]].copy()
        pos = pos.merge(rainfall, on=["unit_id", "date"], how="left")
        pos = pos.merge(static, on="unit_id", how="left")

        # --- Negative samples ---
        # Bias toward high-rainfall days (top 25% antecedent_5day_mm) so the model
        # must use terrain features to discriminate, not just rainfall magnitude.
        # A dry-day negative is trivially easy; a rainy-day-no-event negative is
        # the informative case that makes terrain features meaningful.
        n_neg = len(pos) * negative_ratio
        rng = np.random.default_rng(random_seed)
        all_unit_ids = slope_units_gdf["unit_id"].values

        rain_threshold = rainfall["antecedent_5day_mm"].quantile(0.75)
        rainy_dates = rainfall.loc[
            rainfall["antecedent_5day_mm"] >= rain_threshold, "date"
        ].unique()
        # Fall back to all dates if too few rainy dates
        candidate_dates = rainy_dates if len(rainy_dates) >= n_neg else rainfall["date"].unique()
        logger.info(
            "Negative sampling from %d high-rainfall dates (antecedent_5day ≥ %.1fmm)",
            len(candidate_dates), rain_threshold,
        )

        # Positive (unit_id, date) set — exclude from negatives
        pos_set = set(zip(pos["unit_id"].tolist(), pos["date"].tolist()))

        neg_unit_ids = rng.choice(all_unit_ids, size=n_neg * 3, replace=True)
        neg_dates = rng.choice(candidate_dates, size=n_neg * 3, replace=True)
        neg_pairs = [
            (u, d) for u, d in zip(neg_unit_ids, neg_dates) if (u, d) not in pos_set
        ][:n_neg]

        neg_df = pd.DataFrame(neg_pairs, columns=["unit_id", "date"])
        neg_df["label"] = 0
        neg_df = neg_df.merge(rainfall, on=["unit_id", "date"], how="left")
        neg_df = neg_df.merge(static, on="unit_id", how="left")

        matrix = pd.concat([pos, neg_df], ignore_index=True).sample(
            frac=1, random_state=random_seed
        ).reset_index(drop=True)

        # Fill remaining NaNs with column medians
        for col in FEATURE_COLS:
            if col in matrix.columns:
                matrix[col] = matrix[col].fillna(matrix[col].median())

        out = self.processed_dir / "training_matrix.parquet"
        matrix.to_parquet(out, index=False)
        logger.info(
            "Training matrix: %d rows (%d positive, %d negative) → %s",
            len(matrix), len(pos), len(neg_df), out
        )
        return matrix

    def build_inference_row(
        self,
        slope_units_gdf: gpd.GeoDataFrame,
        rainfall_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Build one-row-per-unit inference DataFrame for today's prediction run.
        rainfall_df: output of CHIRPSDownloader.fetch_latest()
        """
        static = self._load_static(slope_units_gdf)
        rain_cols = ["unit_id"] + [c for c in DYNAMIC_FEATURES if c in rainfall_df.columns]
        merged = static.merge(rainfall_df[rain_cols], on="unit_id", how="left")

        for col in FEATURE_COLS:
            if col not in merged.columns:
                merged[col] = np.nan
            merged[col] = merged[col].fillna(merged[col].median())

        logger.info("Inference matrix built: %d units", len(merged))
        return merged

    def get_feature_cols(self) -> list[str]:
        return FEATURE_COLS
