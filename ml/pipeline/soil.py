"""
ISRIC SoilGrids soil class download for Northern Province, Rwanda.

Downloads soil texture class (USDA) at 250m resolution from SoilGrids REST API.
No account required — public domain data.

Derived feature: soil_class (one-hot encoded for model input).
"""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping, box

logger = logging.getLogger(__name__)

# SoilGrids v2.0 REST API — USDA soil texture class (0-5cm depth)
SOILGRIDS_URL = (
    "https://maps.isric.org/mapserv?map=/map/wrb.map"
    "&SERVICE=WCS&VERSION=2.0.1&REQUEST=GetCoverage"
    "&COVERAGEID=MostProbable&FORMAT=image/tiff"
    "&SUBSET=X({west},{east})&SUBSET=Y({south},{north})"
    "&SUBSETTINGCRS=http://www.opengis.net/def/crs/EPSG/0/4326"
)

BBOX = {"south": -1.85, "north": -1.00, "west": 29.40, "east": 30.45}

# USDA texture class integer codes → descriptive names
TEXTURE_CLASSES = {
    1: "sand", 2: "loamy_sand", 3: "sandy_loam", 4: "loam",
    5: "silt_loam", 6: "silt", 7: "sandy_clay_loam", 8: "clay_loam",
    9: "silty_clay_loam", 10: "sandy_clay", 11: "silty_clay", 12: "clay",
}


class SoilDownloader:
    def __init__(self, raw_dir: Path | str, processed_dir: Path | str):
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)

    def download(self) -> Path:
        """Download SoilGrids WRB soil class raster for the Northern Province bbox."""
        out_path = self.raw_dir / "soil_class_northern_province.tif"
        if out_path.exists():
            logger.info("Soil raster already exists — skipping download")
            return out_path

        url = SOILGRIDS_URL.format(**BBOX)
        logger.info("Downloading SoilGrids texture class from ISRIC...")
        try:
            resp = requests.get(url, timeout=120, stream=True)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error("SoilGrids download failed: %s", e)
            raise

        with open(out_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info("Soil raster saved → %s", out_path)
        return out_path

    def extract_per_unit(self, slope_units_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
        """
        Extract modal soil class per slope unit.
        Returns DataFrame: unit_id, soil_class (int), soil_class_name (str).
        """
        soil_path = self.raw_dir / "soil_class_northern_province.tif"
        if not soil_path.exists():
            logger.warning("Soil raster not found — assigning default class (loam)")
            return pd.DataFrame({
                "unit_id": slope_units_gdf["unit_id"],
                "soil_class": 4,
                "soil_class_name": "loam",
            })

        rows = []
        with rasterio.open(soil_path) as src:
            for _, unit in slope_units_gdf.iterrows():
                geom = [mapping(unit.geometry)]
                try:
                    clipped, _ = mask(src, geom, crop=True, nodata=0)
                    values = clipped[0].flatten()
                    values = values[values > 0]
                    modal = int(np.bincount(values).argmax()) if len(values) > 0 else 4
                except (ValueError, rasterio.errors.WindowError):
                    modal = 4
                rows.append({
                    "unit_id": unit["unit_id"],
                    "soil_class": modal,
                    "soil_class_name": TEXTURE_CLASSES.get(modal, "unknown"),
                })

        df = pd.DataFrame(rows)
        out = self.processed_dir / "soil_per_unit.parquet"
        df.to_parquet(out, index=False)
        logger.info("Saved soil classes for %d units → %s", len(df), out)
        return df

    def one_hot_encode(self, soil_df: pd.DataFrame) -> pd.DataFrame:
        """One-hot encode soil_class column for model input."""
        dummies = pd.get_dummies(soil_df["soil_class"], prefix="soil").astype(int)
        return pd.concat([soil_df[["unit_id"]], dummies], axis=1)
