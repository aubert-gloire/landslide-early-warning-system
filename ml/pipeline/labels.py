"""
Landslide label loader — merges COOLR catalog with MINEMA supplement.

COOLR coverage risk: Rwanda is likely underrepresented in COOLR (media-report-based).
This loader logs positive event counts per district and merges a hand-populated
MINEMA CSV so the training set is not purely dependent on COOLR coverage.

Both sources must share the schema: date, district, lat, lon, label (always 1).
Negative labels (label=0) are generated synthetically at a 1:10 ratio during
feature matrix construction — not here.
"""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

logger = logging.getLogger(__name__)

TARGET_DISTRICTS = {"Gakenke", "Burera", "Musanze", "Gicumbi"}

REQUIRED_COLS = {"date", "district", "lat", "lon", "label"}


class LabelLoader:
    def __init__(self, labels_dir: Path | str, slope_units_gdf: gpd.GeoDataFrame):
        self.labels_dir = Path(labels_dir)
        self.slope_units = slope_units_gdf

    def _validate(self, df: pd.DataFrame, source: str) -> pd.DataFrame:
        missing = REQUIRED_COLS - set(df.columns)
        if missing:
            raise ValueError(f"{source} is missing columns: {missing}")
        df["date"] = pd.to_datetime(df["date"])
        df["label"] = df["label"].astype(int)
        return df

    def load_coolr(self, coolr_csv: Path | str | None = None) -> pd.DataFrame:
        """
        Load COOLR catalog. If no path given, looks for coolr_rwanda.csv in labels_dir.

        To obtain: landslides.nasa.gov → Landslide Viewer → Download Landslide Catalog
        Filter to Rwanda after download. The static data.nasa.gov CSV export cuts off
        at March 7, 2016 — use COOLR Viewer for events through 2024.
        """
        path = Path(coolr_csv) if coolr_csv else self.labels_dir / "coolr_rwanda.csv"
        if not path.exists():
            logger.warning(
                "COOLR CSV not found at %s. Skipping COOLR source. "
                "Download from landslides.nasa.gov → Landslide Viewer.",
                path,
            )
            return pd.DataFrame(columns=list(REQUIRED_COLS))

        raw = pd.read_csv(path, low_memory=False)

        # COOLR column mapping (field names from the Viewer export)
        col_map = {
            "event_date": "date",
            "admin_division_name": "district",
            "latitude": "lat",
            "longitude": "lon",
        }
        raw = raw.rename(columns={k: v for k, v in col_map.items() if k in raw.columns})
        raw["label"] = 1

        # Filter to Northern Province districts
        if "district" in raw.columns:
            raw["district"] = raw["district"].str.strip()
            filtered = raw[raw["district"].isin(TARGET_DISTRICTS)].copy()
        else:
            logger.warning("No district column in COOLR data — cannot filter by district")
            filtered = raw.copy()

        filtered = filtered[list(REQUIRED_COLS)].dropna(subset=["lat", "lon", "date"])
        filtered = self._validate(filtered, "COOLR")

        logger.info(
            "COOLR events per district:\n%s",
            filtered.groupby("district").size().to_string()
        )

        count = len(filtered)
        if count < 20:
            logger.warning(
                "Only %d COOLR positive events found for the 4 districts. "
                "This is expected — COOLR has thin Rwanda coverage. "
                "The MINEMA supplement will carry significant weight in training.",
                count,
            )
        return filtered

    def load_minema(self) -> pd.DataFrame:
        """Load hand-populated MINEMA supplement CSV."""
        path = self.labels_dir / "minema_supplement.csv"
        if not path.exists():
            logger.info("No MINEMA supplement found at %s — using COOLR only", path)
            return pd.DataFrame(columns=list(REQUIRED_COLS))

        df = pd.read_csv(path)
        df = df[list(REQUIRED_COLS)].dropna(subset=["lat", "lon", "date"])
        df = self._validate(df, "MINEMA supplement")
        logger.info("Loaded %d events from MINEMA supplement", len(df))
        return df

    def merge(self) -> pd.DataFrame:
        """Merge COOLR + MINEMA, deduplicate by (date, lat, lon)."""
        coolr = self.load_coolr()
        minema = self.load_minema()
        combined = pd.concat([coolr, minema], ignore_index=True)
        before = len(combined)
        combined = combined.drop_duplicates(subset=["date", "lat", "lon"]).reset_index(drop=True)
        logger.info("Merged labels: %d total (%d dropped as duplicates)", len(combined), before - len(combined))
        return combined

    def assign_slope_units(self, labels_df: pd.DataFrame) -> pd.DataFrame:
        """
        Spatial join: match each label point to its containing slope unit.
        Returns labels_df with added column unit_id.
        Points that fall outside any slope unit are dropped with a warning.
        """
        label_gdf = gpd.GeoDataFrame(
            labels_df,
            geometry=gpd.points_from_xy(labels_df["lon"], labels_df["lat"]),
            crs="EPSG:4326",
        )
        joined = gpd.sjoin(label_gdf, self.slope_units[["unit_id", "geometry"]], how="left", predicate="within")
        unmatched = joined["unit_id"].isna().sum()
        if unmatched > 0:
            logger.warning("%d label points did not match any slope unit — dropped", unmatched)
        result = joined.dropna(subset=["unit_id"]).copy()
        result["unit_id"] = result["unit_id"].astype(int)
        return result[["date", "district", "lat", "lon", "label", "unit_id"]]
