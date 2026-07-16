"""
GPM IMERG Late Daily downloader.

Product: GPM_3IMERGDL v07 — daily accumulated precipitation in mm/day.
Latency: ~2 days (Late Run). Resolution: 0.1° × 0.1°.
Auth: NASA Earthdata bearer token required for every request.

Every HTTP call carries:  Authorization: Bearer <EARTHDATA_TOKEN>
Redirects through Earthdata Login are followed automatically by httpx.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import h5py
import httpx
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_CMR_SEARCH  = "https://cmr.earthdata.nasa.gov/search/granules.json"
_SHORT_NAME  = "GPM_3IMERGDL"
_VERSION     = "07"
_FILL_VALUES = {-9999.9, -9999.0, 29999.99}  # IMERG sentinel values

# Northern Province Rwanda bounding box, with margin — used to window the
# HDF5 read to a tiny sub-array instead of materializing IMERG's full global
# 3600x1800 grid (which costs 50MB+ on a memory-constrained deployment).
_NP_LAT_MIN, _NP_LAT_MAX = -2.2, -1.0
_NP_LON_MIN, _NP_LON_MAX = 29.0, 30.4


class GPMIMERGDownloader:
    """
    Downloads and extracts GPM IMERG Late Daily rainfall per slope unit centroid.

    Usage:
        dl = GPMIMERGDownloader(cache_dir=Path("data/raw/imerg"), token="<edl_bearer_token>")
        df = dl.extract_per_unit(date(2026, 7, 7), slope_units_gdf)
        # returns: unit_id | date | daily_mm
    """

    def __init__(self, cache_dir: Path, token: str, username: str = "", password: str = ""):
        self.cache_dir = Path(cache_dir) / "imerg"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._token    = token
        self._username = username
        self._password = password
        self._headers  = {"Authorization": f"Bearer {token}"}

    # ------------------------------------------------------------------
    # CMR granule search
    # ------------------------------------------------------------------

    def _search_granule_url(self, target_date: date) -> str | None:
        """Return the HTTPS data download URL for the given date, or None."""
        date_str = target_date.strftime("%Y-%m-%d")
        params = {
            "short_name": _SHORT_NAME,
            "version":    _VERSION,
            "temporal":   f"{date_str}T00:00:00Z,{date_str}T23:59:59Z",
            "page_size":  "1",
        }
        try:
            resp = httpx.get(
                _CMR_SEARCH,
                params=params,
                headers=self._headers,
                timeout=20,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("CMR search failed for %s: %s", date_str, exc)
            return None

        entries = resp.json().get("feed", {}).get("entry", [])
        if not entries:
            logger.info("IMERG: no granule found in CMR for %s", date_str)
            return None

        links = entries[0].get("links", [])
        _DATA_EXTS = (".nc4", ".HDF5", ".h5", ".nc")
        # Prefer direct GES DISC data download link
        for link in links:
            href = link.get("href", "")
            if href.startswith("https://data.") and any(href.endswith(e) for e in _DATA_EXTS):
                return href
        # Fallback: any HTTPS data link
        for link in links:
            href = link.get("href", "")
            if href.startswith("https://") and any(href.endswith(e) for e in _DATA_EXTS):
                return href

        logger.warning("IMERG: granule found but no HTTPS data link for %s", date_str)
        return None

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def _stream_to_file(self, client: httpx.Client, url: str, dest: Path) -> bool:
        """Stream a single authenticated GET to dest. Returns True on success."""
        try:
            with client.stream("GET", url, timeout=180, follow_redirects=True) as resp:
                if resp.status_code != 200:
                    logger.warning("IMERG HTTP %s for %s", resp.status_code, url)
                    return False
                with open(dest, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=65536):
                        f.write(chunk)
            logger.info("IMERG downloaded: %s (%.1f MB)", dest.name, dest.stat().st_size / 1e6)
            return True
        except Exception as exc:
            logger.error("IMERG stream error: %s", exc)
            if dest.exists():
                dest.unlink()
            return False

    def _download(self, url: str, dest: Path) -> bool:
        """
        Download with bearer token first; if 403, retry with basic auth.
        GES DISC requires EULA acceptance — 403 usually means EULA not yet accepted
        or the bearer token isn't propagated through the redirect chain.
        """
        # Attempt 1: bearer token
        with httpx.Client(headers=self._headers) as client:
            ok = self._stream_to_file(client, url, dest)
        if ok:
            return True

        # Attempt 2: basic auth (username + password via .netrc-style)
        if self._username and self._password:
            logger.info("Bearer token attempt failed — retrying with basic auth")
            auth = (self._username, self._password)
            with httpx.Client(auth=auth) as client:
                ok = self._stream_to_file(client, url, dest)
            if ok:
                return True

        logger.error(
            "IMERG download failed for %s. "
            "Make sure you have accepted the NASA GESDISC DATA ARCHIVE EULA at "
            "urs.earthdata.nasa.gov → EULAs, and that EARTHDATA_USERNAME / "
            "EARTHDATA_PASSWORD are set in .env.",
            dest.name,
        )
        return False

    # ------------------------------------------------------------------
    # HDF5 extraction
    # ------------------------------------------------------------------

    def _extract_hdf5(self, hdf_path: Path, slope_units_gdf) -> pd.DataFrame | None:
        """
        Read precipitation from the nc4 file and sample at each slope unit centroid.

        V07C flat nc4 layout (no /Grid/ group):
          precipitation  shape (1, 3600, 1800) — [time, lon, lat]
          lon  (3600,)  -179.95 … 179.95  step 0.1 deg
          lat  (1800,)   -89.95 …  89.95  step 0.1 deg
          Units: mm/day (daily accumulated).
        """
        try:
            with h5py.File(hdf_path, "r") as f:
                root_keys = list(f.keys())
                precip_var = next(
                    (k for k in root_keys if k in ("precipitation", "precipitationCal")), None
                )
                if precip_var is None:
                    logger.error("IMERG: no precipitation variable in %s. Keys: %s", hdf_path.name, root_keys)
                    return None

                # Load only the small 1-D coordinate arrays first, then window
                # the read to the Northern Province bbox — the full grid is
                # never pulled into memory.
                full_lats = f["lat"][:]
                full_lons = f["lon"][:]
                lat_idx = np.where((full_lats >= _NP_LAT_MIN) & (full_lats <= _NP_LAT_MAX))[0]
                lon_idx = np.where((full_lons >= _NP_LON_MIN) & (full_lons <= _NP_LON_MAX))[0]
                if len(lat_idx) == 0 or len(lon_idx) == 0:
                    logger.error("IMERG: Northern Province bbox not found in %s coordinate grid", hdf_path.name)
                    return None
                lat_lo, lat_hi = int(lat_idx.min()), int(lat_idx.max()) + 1
                lon_lo, lon_hi = int(lon_idx.min()), int(lon_idx.max()) + 1

                dset = f[precip_var]
                raw = dset[:, lon_lo:lon_hi, lat_lo:lat_hi] if dset.ndim == 3 else dset[lon_lo:lon_hi, lat_lo:lat_hi]
                lats = full_lats[lat_lo:lat_hi]
                lons = full_lons[lon_lo:lon_hi]
        except Exception as exc:
            logger.error("IMERG nc4 read failed (%s): %s", hdf_path.name, exc)
            return None

        # shape (1, lon_window, lat_window) -> [time, lon, lat]
        precip = np.array(raw[0] if raw.ndim == 3 else raw, dtype=float)
        precip[precip < 0] = 0.0  # fill values (-9999 etc) -> 0

        rows = []
        for _, unit in slope_units_gdf.iterrows():
            if "centroid_lat" in unit and unit["centroid_lat"] is not None:
                lat = float(unit["centroid_lat"])
                lon = float(unit["centroid_lon"])
            else:
                centroid = unit.geometry.centroid
                lat, lon = centroid.y, centroid.x

            lon_idx = int(np.argmin(np.abs(lons - lon)))
            lat_idx = int(np.argmin(np.abs(lats - lat)))
            val = precip[lon_idx, lat_idx]
            rows.append({
                "unit_id":  int(unit["unit_id"]),
                "daily_mm": round(float(val), 2),
            })

        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def extract_per_unit(self, target_date: date, slope_units_gdf) -> pd.DataFrame:
        """
        Main entry point. Returns DataFrame with columns: unit_id, date, daily_mm.
        Returns empty DataFrame if download or extraction fails.
        """
        url = self._search_granule_url(target_date)
        if url is None:
            return pd.DataFrame()
        ext = Path(url).suffix  # .nc4 or .HDF5
        cache_path = self.cache_dir / f"imerg_{target_date.isoformat()}{ext}"

        if not cache_path.exists():
            ok = self._download(url, cache_path)
            if not ok:
                return pd.DataFrame()

        df = self._extract_hdf5(cache_path, slope_units_gdf)
        if df is None or df.empty:
            return pd.DataFrame()

        df["date"] = target_date.isoformat()
        logger.info(
            "IMERG extraction complete — %d units, median %.1f mm/day, max %.1f mm/day",
            len(df), df["daily_mm"].median(), df["daily_mm"].max(),
        )
        return df[["unit_id", "date", "daily_mm"]]
