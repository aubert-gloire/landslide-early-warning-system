"""
Sentinel-2 NDVI extraction via Google Earth Engine Python API.

Requires: earthengine-api, a GEE account, and authentication.
Run `earthengine authenticate` once before using this module.

NDVI = (NIR - Red) / (NIR + Red) using Sentinel-2 SR bands B8 (NIR) and B4 (Red).
Annual composite (median) per slope unit, updated once per year.
"""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Northern Province bbox for GEE filtering
BBOX_COORDS = [
    [29.40, -1.85], [30.45, -1.85],
    [30.45, -1.00], [29.40, -1.00],
    [29.40, -1.85],
]


class NDVIExtractor:
    def __init__(self, processed_dir: Path | str):
        self.processed_dir = Path(processed_dir)

    def _init_gee(self):
        """Initialize GEE with service account credentials from env."""
        try:
            import ee
            import os
            sa = os.getenv("GEE_SERVICE_ACCOUNT")
            key_file = os.getenv("GEE_KEY_FILE")
            if sa and key_file:
                from pathlib import Path as _Path
                key_path = _Path(key_file) if _Path(key_file).is_absolute() else _Path(__file__).parents[2] / key_file
                credentials = ee.ServiceAccountCredentials(sa, str(key_path))
                ee.Initialize(credentials)
            else:
                try:
                    ee.Initialize()
                except Exception:
                    ee.Authenticate()
                    ee.Initialize()
            return ee
        except ImportError:
            raise ImportError(
                "earthengine-api not installed. Run: pip install earthengine-api"
            )

    def extract_annual_ndvi(
        self,
        slope_units_gdf: gpd.GeoDataFrame,
        year: int = 2023,
    ) -> pd.DataFrame:
        """
        Compute mean NDVI per slope unit for a full calendar year.
        Uses Sentinel-2 SR median composite, cloud-masked.
        Returns DataFrame with columns: unit_id, ndvi
        """
        ee = self._init_gee()

        aoi = ee.Geometry.Polygon(BBOX_COORDS)
        start = f"{year}-01-01"
        end = f"{year}-12-31"

        s2 = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(aoi)
            .filterDate(start, end)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
        )

        def add_ndvi(img):
            ndvi = img.normalizedDifference(["B8", "B4"]).rename("NDVI")
            return img.addBands(ndvi)

        ndvi_collection = s2.map(add_ndvi)
        ndvi_composite = ndvi_collection.select("NDVI").median()

        # Build a GEE FeatureCollection from all slope units (one batch call)
        features = []
        for _, unit in slope_units_gdf.iterrows():
            coords = list(unit.geometry.exterior.coords)
            geom = ee.Geometry.Polygon([[c[0], c[1]] for c in coords])
            feat = ee.Feature(geom, {"unit_id": int(unit["unit_id"])})
            features.append(feat)
        fc = ee.FeatureCollection(features)

        logger.info("Extracting NDVI for %d units via reduceRegions (scale=30m)...", len(features))
        try:
            reduced = ndvi_composite.reduceRegions(
                collection=fc,
                reducer=ee.Reducer.mean(),
                scale=30,
            )
            result_list = reduced.getInfo()["features"]
            rows = [
                {"unit_id": f["properties"]["unit_id"], "ndvi": f["properties"].get("mean")}
                for f in result_list
            ]
        except Exception as e:
            logger.warning("reduceRegions failed: %s — falling back to per-unit calls", e)
            rows = []
            for _, unit in slope_units_gdf.iterrows():
                coords = list(unit.geometry.exterior.coords)
                geom = ee.Geometry.Polygon([[c[0], c[1]] for c in coords])
                try:
                    result = ndvi_composite.reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=geom,
                        scale=30,
                        maxPixels=1e7,
                    ).getInfo()
                    ndvi_val = result.get("NDVI", None)
                except Exception as ex:
                    logger.warning("GEE error for unit %s: %s", unit["unit_id"], ex)
                    ndvi_val = None
                rows.append({"unit_id": unit["unit_id"], "ndvi": ndvi_val})

        df = pd.DataFrame(rows)
        df["ndvi"] = pd.to_numeric(df["ndvi"], errors="coerce")

        # Fill missing with district median (deforestation proxy should not be NaN)
        district_map = slope_units_gdf.set_index("unit_id")["district"].to_dict()
        df["district"] = df["unit_id"].map(district_map)
        district_medians = df.groupby("district")["ndvi"].transform("median")
        df["ndvi"] = df["ndvi"].fillna(district_medians)
        df["ndvi"] = df["ndvi"].fillna(df["ndvi"].median())

        out = self.processed_dir / f"ndvi_{year}.parquet"
        df[["unit_id", "ndvi"]].to_parquet(out, index=False)
        logger.info("Saved NDVI for %d units → %s", len(df), out)
        return df[["unit_id", "ndvi"]]

    def load_latest(self) -> pd.DataFrame | None:
        """Load the most recent annual NDVI Parquet file."""
        files = sorted(self.processed_dir.glob("ndvi_*.parquet"), reverse=True)
        if not files:
            logger.warning("No NDVI Parquet files found in %s", self.processed_dir)
            return None
        logger.info("Loading NDVI from %s", files[0])
        return pd.read_parquet(files[0])
