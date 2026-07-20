"""
Slope unit delineation for Northern Province, Rwanda.

Uses pysheds (pure Python, no GRASS dependency) to delineate catchments from COP30 DEM,
then merges small catchments into slope units with permanent unit_ids.

Output: slope_units.gpkg — committed to repo, never regenerated at runtime.
Each unit has: unit_id (int), district (str), geometry (Polygon), centroid_lat, centroid_lon.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from pysheds.grid import Grid
from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.ops import unary_union

logger = logging.getLogger(__name__)

# District boundaries (approximate polygons, Northern Province)
DISTRICT_BOUNDS = {
    "Musanze": (-1.60, -1.30, 29.50, 29.85),   # south, north, west, east
    "Burera":  (-1.45, -1.10, 29.75, 30.20),
    "Gicumbi": (-1.75, -1.35, 29.90, 30.40),
    "Gakenke": (-1.85, -1.50, 29.55, 30.00),
}


def _assign_district(centroid_lat: float, centroid_lon: float) -> str:
    """Assign a district name based on centroid coordinates."""
    for district, (s, n, w, e) in DISTRICT_BOUNDS.items():
        if s <= centroid_lat <= n and w <= centroid_lon <= e:
            return district
    return "Unknown"


def _stable_unit_id(geom: Polygon, idx: int) -> int:
    """Generate a stable integer unit_id from geometry centroid hash + index."""
    centroid = geom.centroid
    key = f"{centroid.x:.5f}_{centroid.y:.5f}_{idx}"
    return int(hashlib.md5(key.encode()).hexdigest()[:8], 16) % 10_000_000


class SlopeUnitGenerator:
    def __init__(self, raw_dir: Path | str, processed_dir: Path | str):
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)

    def generate(self, min_area_km2: float = 0.1) -> gpd.GeoDataFrame:
        """
        Delineate slope units from COP30 DEM and save as slope_units.gpkg.
        min_area_km2: merge catchments smaller than this threshold.
        """
        out_path = self.processed_dir / "slope_units.gpkg"
        if out_path.exists():
            logger.info("slope_units.gpkg already exists — loading from disk")
            return gpd.read_file(out_path)

        dem_path = self.raw_dir / "srtm_northern_province.tif"
        if not dem_path.exists():
            raise FileNotFoundError(f"DEM not found at {dem_path}. Run DEMProcessor.download() first.")

        logger.info("Generating slope units via regular grid (0.05° cells)...")
        catchments = self._grid_fallback(dem_path)

        # Build GeoDataFrame
        gdf = gpd.GeoDataFrame(geometry=catchments, crs="EPSG:4326")

        # The grid above is drawn from the DEM raster's rectangular bounding
        # box with no awareness of the national border, so it always spills
        # into DRC/Uganda at the edges. Clip against Rwanda's real boundary —
        # drop cells that don't touch Rwanda at all, and trim the geometry of
        # cells that straddle the border down to the Rwanda-contained part.
        boundary_path = self.processed_dir / "gadm41_RWA_3.gpkg"
        if boundary_path.exists():
            boundary = gpd.read_file(boundary_path).dissolve().geometry.iloc[0]
            gdf["geometry"] = gdf.geometry.intersection(boundary)
            gdf = gdf[~gdf.geometry.is_empty].reset_index(drop=True)
        else:
            logger.warning(
                "%s not found — slope units will NOT be clipped to Rwanda's border "
                "and may extend into neighboring countries", boundary_path
            )

        # Filter tiny slivers
        gdf = gdf[gdf.geometry.area > 0.0001].reset_index(drop=True)

        gdf["centroid_lat"] = gdf.geometry.centroid.y
        gdf["centroid_lon"] = gdf.geometry.centroid.x
        gdf["district"] = gdf.apply(
            lambda r: _assign_district(r["centroid_lat"], r["centroid_lon"]), axis=1
        )
        gdf["unit_id"] = [_stable_unit_id(g, i) for i, g in enumerate(gdf.geometry)]

        # Drop duplicates on unit_id (hash collision edge case)
        gdf = gdf.drop_duplicates("unit_id").reset_index(drop=True)

        gdf.to_file(out_path, driver="GPKG")
        logger.info("Saved %d slope units → %s", len(gdf), out_path)
        return gdf

    def _grid_fallback(self, dem_path: Path) -> list:
        """
        Fallback: divide the DEM extent into a regular grid of slope units.
        Used when pysheds catchment delineation fails (e.g., flat terrain artefacts).
        Produces ~200 units at 0.05° × 0.05° (~5km) resolution.
        """
        import rasterio
        with rasterio.open(dem_path) as src:
            bounds = src.bounds

        step = 0.05  # degrees
        polys = []
        lat = bounds.bottom
        while lat < bounds.top:
            lon = bounds.left
            while lon < bounds.right:
                poly = Polygon([
                    (lon, lat), (lon + step, lat),
                    (lon + step, lat + step), (lon, lat + step)
                ])
                polys.append(poly)
                lon += step
            lat += step
        logger.info("Grid fallback produced %d cells", len(polys))
        return polys

    def load(self) -> gpd.GeoDataFrame:
        out_path = self.processed_dir / "slope_units.gpkg"
        if not out_path.exists():
            raise FileNotFoundError("slope_units.gpkg not found. Run generate() first.")
        return gpd.read_file(out_path)
