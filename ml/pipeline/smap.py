"""
SMAP Enhanced L3 Passive Soil Moisture downloader.

Product: SPL3SMP_E v006 — daily surface (0-5cm) soil moisture in m³/m³.
Resolution: 9km EASE-Grid 2.0. Latency: ~2-3 days.
Auth: NASA Earthdata bearer token or basic auth (same account as IMERG).

Outputs per slope unit centroid:
  soil_moisture_am  — morning overpass (m³/m³), typically more reliable
  soil_moisture_pm  — afternoon overpass (m³/m³)
  soil_moisture     — AM if available, else PM

Interpretation for Rwanda:
  < 0.10  dry          (very low landslide pre-conditioning)
  0.10–0.25  moderate  (normal seasonal range)
  0.25–0.35  moist     (elevated pre-conditioning)
  > 0.35  saturated    (critical pre-conditioning — even moderate rain is dangerous)
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
_SHORT_NAME  = "SPL3SMP_E"
_VERSION     = "006"
_FILL_VALUE  = -9999.0

# SMAP soil moisture thresholds (m³/m³) for Rwanda's clay-loam soils
SMAP_THRESHOLDS = {
    "dry":       0.10,
    "moderate":  0.25,
    "moist":     0.35,
    # above 0.35 → saturated
}


def soil_moisture_label(sm: float | None) -> str:
    """Human-readable saturation state for display."""
    if sm is None or sm < 0:
        return "no data"
    if sm < SMAP_THRESHOLDS["dry"]:
        return "dry"
    if sm < SMAP_THRESHOLDS["moderate"]:
        return "moderate"
    if sm < SMAP_THRESHOLDS["moist"]:
        return "moist"
    return "saturated"


def soil_moisture_pct(sm: float | None) -> float | None:
    """
    Convert m³/m³ to a 0-100 'fullness' percentage calibrated to Rwanda's
    soil porosity range (0 = completely dry, 100 = fully saturated at ~0.45).
    """
    if sm is None or sm < 0:
        return None
    return round(min(sm / 0.45 * 100, 100), 1)


class SMAPDownloader:
    """
    Downloads and extracts SMAP Enhanced L3 daily soil moisture per district centroid.

    Usage:
        dl = SMAPDownloader(cache_dir=Path("data/raw"), token="<edl_bearer_token>")
        df = dl.extract_per_district(date(2026, 7, 7), district_centroids)
        # returns: district | date | soil_moisture_am | soil_moisture_pm | soil_moisture | label | pct
    """

    def __init__(self, cache_dir: Path, token: str, username: str = "", password: str = ""):
        self.cache_dir = Path(cache_dir) / "smap"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._token    = token
        self._username = username
        self._password = password
        self._headers  = {"Authorization": f"Bearer {token}"} if token else {}

    # ------------------------------------------------------------------
    # CMR search
    # ------------------------------------------------------------------

    def _search_granule_url(self, target_date: date) -> str | None:
        date_str = target_date.strftime("%Y-%m-%d")
        params = {
            "short_name": _SHORT_NAME,
            "version":    _VERSION,
            "temporal":   f"{date_str}T00:00:00Z,{date_str}T23:59:59Z",
            "page_size":  "1",
        }
        try:
            resp = httpx.get(_CMR_SEARCH, params=params, headers=self._headers, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("SMAP CMR search failed: %s", exc)
            return None

        entries = resp.json().get("feed", {}).get("entry", [])
        if not entries:
            logger.info("SMAP: no granule found for %s", date_str)
            return None

        _DATA_EXTS = (".h5", ".HDF5", ".nc4", ".nc")
        for link in entries[0].get("links", []):
            href = link.get("href", "")
            if href.startswith("https://") and any(href.endswith(e) for e in _DATA_EXTS):
                if "browse" not in href and "metadata" not in href.lower():
                    return href

        logger.warning("SMAP: granule found but no HTTPS data link for %s", date_str)
        return None

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def _stream(self, client: httpx.Client, url: str, dest: Path) -> bool:
        try:
            with client.stream("GET", url, timeout=180, follow_redirects=True) as resp:
                if resp.status_code != 200:
                    logger.warning("SMAP HTTP %s", resp.status_code)
                    return False
                with open(dest, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=65536):
                        f.write(chunk)
            logger.info("SMAP downloaded: %s (%.1f MB)", dest.name, dest.stat().st_size / 1e6)
            return True
        except Exception as exc:
            logger.error("SMAP stream error: %s", exc)
            if dest.exists():
                dest.unlink()
            return False

    def _download(self, url: str, dest: Path) -> bool:
        with httpx.Client(headers=self._headers) as c:
            if self._stream(c, url, dest):
                return True
        if self._username and self._password:
            logger.info("Bearer failed — retrying SMAP with basic auth")
            with httpx.Client(auth=(self._username, self._password)) as c:
                return self._stream(c, url, dest)
        logger.error(
            "SMAP download failed. Accept 'NSIDC DAAC' EULA at urs.earthdata.nasa.gov → EULAs"
        )
        return False

    # ------------------------------------------------------------------
    # HDF5 extraction
    # ------------------------------------------------------------------

    def _extract_hdf5(self, hdf_path: Path, centroids: dict[str, tuple[float, float]]) -> pd.DataFrame:
        """
        Extract soil moisture at district centroids from SMAP Enhanced HDF5.

        SMAP SPL3SMP_E structure:
          /Soil_Moisture_Retrieval_Data_AM/soil_moisture   — AM overpass (float32, m³/m³)
          /Soil_Moisture_Retrieval_Data_AM/latitude        — per-pixel lat
          /Soil_Moisture_Retrieval_Data_AM/longitude       — per-pixel lon
          /Soil_Moisture_Retrieval_Data_PM/soil_moisture_pm_err  (some versions)
        """
        rows = []
        try:
            with h5py.File(hdf_path, "r") as f:
                root_keys = list(f.keys())
                logger.debug("SMAP root keys: %s", root_keys)

                am_key = next((k for k in root_keys if "AM" in k), None)
                pm_key = next((k for k in root_keys if "PM" in k), None)

                def read_group(group_key, sm_varname="soil_moisture"):
                    if group_key is None or group_key not in f:
                        return None, None, None
                    g = f[group_key]
                    sm_key = next((k for k in g.keys() if k.startswith(sm_varname)), None)
                    if sm_key is None:
                        return None, None, None
                    sm  = np.array(g[sm_key], dtype=float)
                    lat = np.array(g["latitude"],  dtype=float)
                    lon = np.array(g["longitude"], dtype=float)
                    sm[np.isclose(sm, _FILL_VALUE, atol=1.0)] = np.nan
                    sm[sm < 0] = np.nan
                    return sm, lat, lon

                sm_am, lat_am, lon_am = read_group(am_key, "soil_moisture")
                sm_pm, lat_pm, lon_pm = read_group(pm_key, "soil_moisture_pm")
                if sm_pm is None:
                    sm_pm, lat_pm, lon_pm = read_group(pm_key, "soil_moisture")

        except Exception as exc:
            logger.error("SMAP HDF5 read error (%s): %s", hdf_path.name, exc)
            return pd.DataFrame()

        for district, (lat, lon) in centroids.items():
            am_val = pm_val = None

            if sm_am is not None and lat_am is not None:
                dist = np.sqrt((lat_am - lat) ** 2 + (lon_am - lon) ** 2)
                idx = int(np.nanargmin(dist.ravel()))
                v = sm_am.ravel()[idx]
                am_val = round(float(v), 4) if not np.isnan(v) else None

            if sm_pm is not None and lat_pm is not None:
                dist = np.sqrt((lat_pm - lat) ** 2 + (lon_pm - lon) ** 2)
                idx = int(np.nanargmin(dist.ravel()))
                v = sm_pm.ravel()[idx]
                pm_val = round(float(v), 4) if not np.isnan(v) else None

            best = am_val if am_val is not None else pm_val
            rows.append({
                "district":        district,
                "soil_moisture_am": am_val,
                "soil_moisture_pm": pm_val,
                "soil_moisture":    best,
                "label":            soil_moisture_label(best),
                "pct":              soil_moisture_pct(best),
            })

        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    # Rwanda Northern Province district centroids
    DISTRICT_CENTROIDS: dict[str, tuple[float, float]] = {
        "Musanze": (-1.50, 29.63),
        "Gakenke": (-1.70, 29.78),
        "Burera":  (-1.46, 29.85),
        "Gicumbi": (-1.57, 30.07),
    }

    def extract_per_district(
        self,
        target_date: date,
        centroids: dict[str, tuple[float, float]] | None = None,
    ) -> pd.DataFrame:
        """
        Main entry point. Returns DataFrame:
          district | date | soil_moisture_am | soil_moisture_pm | soil_moisture | label | pct
        Returns empty DataFrame if download or extraction fails.
        """
        centroids = centroids or self.DISTRICT_CENTROIDS

        url = self._search_granule_url(target_date)
        if url is None:
            return pd.DataFrame()

        ext = Path(url).suffix
        cache_path = self.cache_dir / f"smap_{target_date.isoformat()}{ext}"

        if not cache_path.exists():
            if not self._download(url, cache_path):
                return pd.DataFrame()

        df = self._extract_hdf5(cache_path, centroids)
        if df.empty:
            return df

        df["date"] = target_date.isoformat()
        logger.info(
            "SMAP extraction complete — %d districts, moisture range %.3f–%.3f m³/m³",
            len(df),
            df["soil_moisture"].dropna().min() if df["soil_moisture"].notna().any() else 0,
            df["soil_moisture"].dropna().max() if df["soil_moisture"].notna().any() else 0,
        )
        return df[["district", "date", "soil_moisture_am", "soil_moisture_pm", "soil_moisture", "label", "pct"]]
