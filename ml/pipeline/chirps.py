"""
CHIRPS v2 daily rainfall downloader for Northern Province, Rwanda.

Primary method: direct download from UCSB CHC server (no account required).
Each file covers Africa at 0.05° resolution; we clip to the Northern Province bbox.

Using CHIRPS v2.0 (1981–present). CHIRPS v3 historical files for years 2000–2015
are not available on the CHC server; v2 has identical resolution and is the
standard used in Kuradusenge et al. 2020.
"""

from __future__ import annotations

import gzip
import io
import logging
import shutil
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import rasterio
from rasterio.mask import mask
from shapely.geometry import box, mapping

logger = logging.getLogger(__name__)

# Northern Province bounding box (WGS84)
BBOX = {"south": -1.85, "north": -1.00, "west": 29.40, "east": 30.45}

CHIRPS_BASE = "https://data.chc.ucsb.edu/products/CHIRPS-2.0/prelim/global_daily/tifs/p05"


class CHIRPSDownloader:
    def __init__(self, raw_dir: Path | str, processed_dir: Path | str):
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self._bbox_geom = box(BBOX["west"], BBOX["south"], BBOX["east"], BBOX["north"])

    def _filename(self, d: date) -> str:
        return f"chirps-v2.0.{d.strftime('%Y.%m.%d')}.tif"

    def _url(self, d: date) -> str:
        return f"{CHIRPS_BASE}/{d.year}/{self._filename(d)}.gz"

    def download_day(self, d: date) -> Path | None:
        """Download and decompress one day of CHIRPS v3 rainfall. Returns local path."""
        out_path = self.raw_dir / self._filename(d)
        if out_path.exists():
            return out_path

        url = self._url(d)
        try:
            # stream=False so timeout=(connect, read) covers the full body download.
            # stream=True + resp.content only timeouts headers, body can hang forever.
            resp = requests.get(url, timeout=(15, 180), stream=False)
            resp.raise_for_status()
            compressed = io.BytesIO(resp.content)
        except requests.RequestException as e:
            logger.warning("CHIRPS download failed for %s: %s", d, e)
            return None

        try:
            # Stream the decompression to disk in chunks instead of gz.read(),
            # which would materialize the entire decompressed file in memory.
            with gzip.open(compressed) as gz, open(out_path, "wb") as f:
                shutil.copyfileobj(gz, f)
        except Exception as e:
            logger.warning("CHIRPS decompress failed for %s: %s", d, e)
            out_path.unlink(missing_ok=True)
            return None

        logger.info("Downloaded CHIRPS for %s → %s", d, out_path)
        return out_path

    def extract_bbox_rainfall(self, d: date) -> float | None:
        """Extract mean rainfall (mm) over the Northern Province bbox for one day."""
        tif_path = self.download_day(d)
        if tif_path is None:
            return None

        with rasterio.open(tif_path) as src:
            geom = [mapping(self._bbox_geom)]
            try:
                clipped, _ = mask(src, geom, crop=True, nodata=-9999)
            except ValueError:
                logger.warning("Bbox outside raster extent for %s", d)
                return None

            data = clipped[0].astype(float)
            data[data == -9999] = np.nan
            data[data < 0] = np.nan
            return float(np.nanmean(data)) if not np.all(np.isnan(data)) else None

    def extract_per_unit_rainfall(
        self, d: date, slope_units_gdf
    ) -> pd.DataFrame:
        """
        Extract mean rainfall per slope unit for a single day.
        Returns DataFrame with columns: unit_id, date, daily_mm
        """
        tif_path = self.download_day(d)
        if tif_path is None:
            logger.warning("No CHIRPS data for %s — returning NaN row", d)
            return pd.DataFrame({
                "unit_id": slope_units_gdf["unit_id"],
                "date": d,
                "daily_mm": np.nan,
            })

        rows = []
        with rasterio.open(tif_path) as src:
            for _, unit in slope_units_gdf.iterrows():
                geom = [mapping(unit.geometry)]
                try:
                    clipped, _ = mask(src, geom, crop=True, nodata=-9999)
                    data = clipped[0].astype(float)
                    data[data < 0] = np.nan
                    val = float(np.nanmean(data)) if not np.all(np.isnan(data)) else 0.0
                except (ValueError, rasterio.errors.WindowError):
                    val = 0.0
                rows.append({"unit_id": unit["unit_id"], "date": d, "daily_mm": val})

        return pd.DataFrame(rows)

    def build_historical_series(
        self, slope_units_gdf, start: date, end: date
    ) -> pd.DataFrame:
        """
        Download and process CHIRPS daily rainfall for all slope units over a date range.
        Saves result as Parquet to processed_dir.
        Use this once during training data preparation — not at inference time.
        """
        all_frames = []
        current = start
        total = (end - start).days + 1
        logger.info("Building CHIRPS series %s → %s (%d days)", start, end, total)

        while current <= end:
            df = self.extract_per_unit_rainfall(current, slope_units_gdf)
            all_frames.append(df)
            if len(all_frames) % 30 == 0:
                logger.info("Progress: %d/%d days", len(all_frames), total)
            current += timedelta(days=1)

        combined = pd.concat(all_frames, ignore_index=True)
        combined["date"] = pd.to_datetime(combined["date"])
        combined = combined.sort_values(["unit_id", "date"])

        # Antecedent rainfall windows — different windows capture different soil depths
        for window, col in [(3, "antecedent_3day_mm"),
                            (5, "antecedent_5day_mm"),
                            (10, "antecedent_10day_mm")]:
            combined[col] = (
                combined.groupby("unit_id")["daily_mm"]
                .transform(lambda s, w=window: s.rolling(w, min_periods=1).sum())
            )

        # Intensity ratio: sudden burst vs gradual saturation
        combined["rainfall_intensity_ratio"] = (
            combined["daily_mm"] / (combined["antecedent_5day_mm"] + 1.0)
        ).round(4)

        out = self.processed_dir / "chirps_historical.parquet"
        combined.to_parquet(out, index=False)
        logger.info("Saved historical CHIRPS series → %s", out)
        return combined

    def fetch_latest(self, slope_units_gdf) -> pd.DataFrame:
        """Pull yesterday's rainfall and compute 5-day rolling sum from stored history."""
        yesterday = date.today() - timedelta(days=1)
        daily_df = self.extract_per_unit_rainfall(yesterday, slope_units_gdf)
        daily_df["date"] = pd.to_datetime(daily_df["date"])

        # Load last 4 days from stored Parquet to compute rolling sum
        history_path = self.processed_dir / "chirps_historical.parquet"
        if history_path.exists():
            history = pd.read_parquet(history_path)
            cutoff = pd.Timestamp(yesterday) - pd.Timedelta(days=9)  # 10 days for antecedent_10day
            recent = history[history["date"] >= cutoff][["unit_id", "date", "daily_mm"]]
            combined = pd.concat([recent, daily_df], ignore_index=True)
        else:
            combined = daily_df

        combined = combined.sort_values(["unit_id", "date"])

        for window, col in [(3, "antecedent_3day_mm"),
                            (5, "antecedent_5day_mm"),
                            (10, "antecedent_10day_mm")]:
            combined[col] = (
                combined.groupby("unit_id")["daily_mm"]
                .transform(lambda s, w=window: s.rolling(w, min_periods=1).sum())
            )
        combined["rainfall_intensity_ratio"] = (
            combined["daily_mm"] / (combined["antecedent_5day_mm"] + 1.0)
        ).round(4)

        return combined[combined["date"] == pd.Timestamp(yesterday)]
