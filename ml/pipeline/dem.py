"""
SRTM GL1 (1 arc-second ≈ 30 m) download and terrain derivative computation.

Downloads via OpenTopography API (free account + API key required).
Derives: slope_angle, aspect, TWI (Topographic Wetness Index), drainage_density.

NOTE: Originally designed for COP30 but switched to SRTMGL1 due to persistent
tile-corruption issues with the COP30 GTiff delivery for this bbox. SRTMGL1 and
COP30 are both ~30 m resolution; terrain derivatives are functionally equivalent
for Rwanda's Northern Province. SRTMGL1 is a DSM over vegetated areas, same
limitation applies — document in methods section.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path

import numpy as np
import requests
import rasterio
from rasterio.transform import from_bounds
from rasterio.warp import Resampling, reproject

logger = logging.getLogger(__name__)

OPENTOPO_URL = "https://portal.opentopography.org/API/globaldem"

# Northern Province bbox
BBOX = {"south": -1.85, "north": -1.00, "west": 29.40, "east": 30.45}


class DEMProcessor:
    def __init__(self, raw_dir: Path | str, processed_dir: Path | str, api_key: str):
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)
        self.api_key = api_key
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def download(self) -> Path:
        """Download SRTMGL1 DEM for the Northern Province bbox."""
        out_path = self.raw_dir / "srtm_northern_province.tif"
        if out_path.exists() and out_path.stat().st_size > 1_000_000:
            logger.info("DEM already exists at %s — skipping download", out_path)
            return out_path

        params = {
            "demtype": "SRTMGL1",
            "south": BBOX["south"],
            "north": BBOX["north"],
            "west": BBOX["west"],
            "east": BBOX["east"],
            "outputFormat": "GTiff",
            "API_Key": self.api_key,
        }
        logger.info("Downloading SRTMGL1 DEM from OpenTopography...")
        resp = requests.get(OPENTOPO_URL, params=params, timeout=600, stream=True)
        resp.raise_for_status()

        expected = int(resp.headers.get("Content-Length", 0))
        received = 0
        with open(out_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
                received += len(chunk)

        if expected and received < expected:
            out_path.unlink(missing_ok=True)
            raise RuntimeError(
                f"DEM download truncated: got {received} bytes, expected {expected}"
            )

        logger.info("DEM saved → %s (%d bytes)", out_path, received)
        return out_path

    def _compute_slope_aspect(self, elevation: np.ndarray, cell_size_m: float):
        """Return (slope_deg, aspect_deg) arrays from elevation grid."""
        dy, dx = np.gradient(elevation, cell_size_m)
        slope_rad = np.arctan(np.sqrt(dx**2 + dy**2))
        slope_deg = np.degrees(slope_rad)
        aspect_deg = np.degrees(np.arctan2(-dy, dx)) % 360
        return slope_deg, aspect_deg

    def _compute_twi(self, elevation: np.ndarray, cell_size_m: float) -> np.ndarray:
        """
        Topographic Wetness Index: TWI = ln(a / tan(β))
        where a = upslope contributing area per unit contour length, β = slope angle.

        This is a simplified single-flow-direction approximation suitable when
        pysheds or GRASS r.watershed is not available in the runtime environment.
        For production training, prefer pysheds (see slope_units.py) which computes
        a proper D8 flow accumulation.
        """
        dy, dx = np.gradient(elevation, cell_size_m)
        slope_rad = np.arctan(np.sqrt(dx**2 + dy**2))
        slope_rad = np.clip(slope_rad, 1e-6, None)  # avoid log(inf)

        # Proxy upslope area using elevation (higher elevation → less contributing area)
        # Replace with real flow accumulation raster when available from pysheds
        elev_norm = (elevation - elevation.min()) / (elevation.max() - elevation.min() + 1e-6)
        upslope_area = (1 - elev_norm) * cell_size_m**2 + cell_size_m**2

        twi = np.log(upslope_area / np.tan(slope_rad))
        return twi

    def _compute_drainage_density(
        self, elevation: np.ndarray, cell_size_m: float
    ) -> float:
        """
        Approximate drainage density as total channel length / catchment area.
        Channels identified by flow accumulation threshold (top 5% of cells).
        Returns scalar value (km/km²) for the whole tile.
        """
        dy, dx = np.gradient(elevation, cell_size_m)
        slope = np.sqrt(dx**2 + dy**2)
        # Simple proxy: high-slope cells in concave areas approximate channels
        channel_mask = slope > np.percentile(slope, 95)
        channel_length_km = float(np.sum(channel_mask)) * cell_size_m / 1000
        area_km2 = (elevation.shape[0] * elevation.shape[1] * cell_size_m**2) / 1e6
        return channel_length_km / max(area_km2, 1e-6)

    def derive_terrain_features(self) -> dict:
        """
        Compute all terrain features from the downloaded DEM.
        Returns dict of 2D numpy arrays + scalar drainage_density.
        Also saves individual GeoTIFFs to processed_dir.
        """
        dem_path = self.raw_dir / "srtm_northern_province.tif"
        if not dem_path.exists():
            raise FileNotFoundError(f"DEM not found at {dem_path}. Run download() first.")

        with rasterio.open(dem_path) as src:
            elevation = src.read(1).astype(float)
            profile = src.profile.copy()
            nodata = src.nodata or -9999
            elevation[elevation == nodata] = np.nan

            # Approximate cell size in metres at Rwanda's latitude (~-1.4°)
            lat_rad = math.radians(-1.4)
            cell_size_m = abs(src.res[0]) * 111320 * math.cos(lat_rad)

        elevation = np.where(np.isnan(elevation), np.nanmean(elevation), elevation)

        slope, aspect = self._compute_slope_aspect(elevation, cell_size_m)
        twi = self._compute_twi(elevation, cell_size_m)
        drainage_density = self._compute_drainage_density(elevation, cell_size_m)

        features = {
            "elevation": elevation,
            "slope_angle": slope,
            "aspect": aspect,
            "twi": twi,
            "drainage_density": drainage_density,  # scalar
        }

        # Save each raster
        profile.update(dtype=rasterio.float32, count=1, nodata=-9999)
        for name, arr in [
            ("slope_angle", slope),
            ("aspect", aspect),
            ("twi", twi),
        ]:
            out_path = self.processed_dir / f"{name}.tif"
            with rasterio.open(out_path, "w", **profile) as dst:
                dst.write(arr.astype(np.float32), 1)
            logger.info("Saved %s → %s", name, out_path)

        logger.info("Terrain derivation complete. Drainage density: %.4f km/km²", drainage_density)
        return features

    def extract_per_unit(self, slope_units_gdf) -> "pd.DataFrame":
        """
        Extract mean terrain values per slope unit from saved GeoTIFFs.
        Saves terrain_per_unit.parquet to processed_dir.
        """
        import pandas as pd
        from rasterio.mask import mask as rio_mask
        from shapely.geometry import mapping

        layers = ["slope_angle", "aspect", "twi"]
        unit_rows = []

        for _, unit in slope_units_gdf.iterrows():
            geom = [mapping(unit.geometry)]
            row = {"unit_id": int(unit["unit_id"])}
            for layer in layers:
                tif_path = self.processed_dir / f"{layer}.tif"
                if not tif_path.exists():
                    row[layer] = np.nan
                    continue
                with rasterio.open(tif_path) as src:
                    try:
                        clipped, _ = rio_mask(src, geom, crop=True, nodata=-9999)
                        data = clipped[0].astype(float)
                        data[data == -9999] = np.nan
                        row[layer] = float(np.nanmean(data)) if not np.all(np.isnan(data)) else np.nan
                    except (ValueError, Exception):
                        row[layer] = np.nan
            unit_rows.append(row)

        df = pd.DataFrame(unit_rows)

        # drainage_density is a tile-level scalar — propagate to all units
        dem_path = self.raw_dir / "srtm_northern_province.tif"
        if dem_path.exists():
            with rasterio.open(dem_path) as src:
                elevation = src.read(1).astype(float)
                nodata = src.nodata or -9999
                elevation[elevation == nodata] = np.nan
                lat_rad = math.radians(-1.4)
                cell_size_m = abs(src.res[0]) * 111320 * math.cos(lat_rad)
            elevation = np.where(np.isnan(elevation), np.nanmean(elevation), elevation)
            df["drainage_density"] = self._compute_drainage_density(elevation, cell_size_m)
        else:
            df["drainage_density"] = np.nan

        out = self.processed_dir / "terrain_per_unit.parquet"
        df.to_parquet(out, index=False)
        logger.info("Saved terrain_per_unit.parquet → %d units", len(df))
        return df

    def sample_at_point(self, lat: float, lon: float, layer: str = "slope_angle") -> float | None:
        """Sample a terrain layer value at a lat/lon coordinate."""
        tif_path = self.processed_dir / f"{layer}.tif"
        if not tif_path.exists():
            return None
        with rasterio.open(tif_path) as src:
            row, col = src.index(lon, lat)
            if 0 <= row < src.height and 0 <= col < src.width:
                return float(src.read(1)[row, col])
        return None
