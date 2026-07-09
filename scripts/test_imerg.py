"""
Quick IMERG integration test.
1. CMR search — confirms auth + granule exists
2. Downloads the HDF5 file for a recent date
3. Extracts Northern Province rainfall values
4. Prints a summary

Usage:  python scripts/test_imerg.py
"""

import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

token    = os.getenv("EARTHDATA_TOKEN", "")
username = os.getenv("EARTHDATA_USERNAME", "")
password = os.getenv("EARTHDATA_PASSWORD", "")
if not token and not (username and password):
    print("ERROR: set EARTHDATA_TOKEN (or EARTHDATA_USERNAME + EARTHDATA_PASSWORD) in .env")
    sys.exit(1)

# Try yesterday first; if IMERG Late Daily isn't up yet fall back 2 days
target = date.today() - timedelta(days=2)

print(f"\nTarget date: {target}")
print(f"Token present:    {'yes' if token else 'no'} ({len(token)} chars)")
print(f"Username present: {'yes' if username else 'no'}\n")

# --- Step 1: CMR granule search ---
import httpx

CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
headers = {"Authorization": f"Bearer {token}"}
params = {
    "short_name": "GPM_3IMERGDL",
    "version":    "07",
    "temporal":   f"{target}T00:00:00Z,{target}T23:59:59Z",
    "page_size":  "1",
}

print("Step 1 — CMR search...")
resp = httpx.get(CMR, params=params, headers=headers, timeout=20)
print(f"  HTTP {resp.status_code}")
if resp.status_code != 200:
    print("  FAILED:", resp.text[:300])
    sys.exit(1)

entries = resp.json().get("feed", {}).get("entry", [])
if not entries:
    print(f"  No granule found for {target} — trying one day earlier")
    target = target - timedelta(days=1)
    params["temporal"] = f"{target}T00:00:00Z,{target}T23:59:59Z"
    resp = httpx.get(CMR, params=params, headers=headers, timeout=20)
    entries = resp.json().get("feed", {}).get("entry", [])

if not entries:
    print("  Still no granule — IMERG Late Daily may not be available for recent dates yet")
    sys.exit(1)

entry = entries[0]
print(f"  Granule: {entry.get('title', 'N/A')}")

# Find HTTPS HDF5 download link
dl_url = None
DATA_EXTS = (".nc4", ".HDF5", ".h5", ".nc")
for link in entry.get("links", []):
    href = link.get("href", "")
    if href.startswith("https://data.") and any(href.endswith(e) for e in DATA_EXTS):
        dl_url = href
        break

if not dl_url:
    print("  No HTTPS data link found. Links found:")
    for l in entry.get("links", []):
        print("   ", l.get("href", ""))
    sys.exit(1)

print(f"  Download URL: {dl_url}")

# --- Step 2: Download ---
cache_dir = ROOT / "data" / "raw" / "imerg"
cache_dir.mkdir(parents=True, exist_ok=True)
ext = Path(dl_url).suffix  # .nc4 or .HDF5
cache_file = cache_dir / f"imerg_{target.isoformat()}{ext}"

if cache_file.exists():
    print(f"\nStep 2 — Already cached ({cache_file.stat().st_size / 1e6:.1f} MB), skipping download")
else:
    print(f"\nStep 2 — Downloading (~30-100 MB)...")

    def try_download(url, dest, hdrs, auth=None):
        with httpx.stream("GET", url, headers=hdrs, auth=auth, timeout=180, follow_redirects=True) as r:
            print(f"  HTTP {r.status_code}")
            if r.status_code != 200:
                return False, 0
            with open(dest, "wb") as f:
                n = 0
                for chunk in r.iter_bytes(chunk_size=65536):
                    f.write(chunk); n += len(chunk)
            return True, n

    ok, n_bytes = try_download(dl_url, cache_file, headers)
    if not ok and username and password:
        print("  Bearer token got 403 — retrying with basic auth...")
        if cache_file.exists(): cache_file.unlink()
        ok, n_bytes = try_download(dl_url, cache_file, {}, auth=(username, password))

    if not ok:
        print("\n  Download FAILED (403 Forbidden).")
        print("  Fix: go to urs.earthdata.nasa.gov → EULAs → accept 'NASA GESDISC DATA ARCHIVE'")
        print("  Then add EARTHDATA_USERNAME and EARTHDATA_PASSWORD to .env and retry.")
        sys.exit(1)

    print(f"  Downloaded {n_bytes / 1e6:.1f} MB -> {cache_file.name}")

# --- Step 3: Extract Rwanda Northern Province values ---
import h5py
import numpy as np

print("\nStep 3 - Reading nc4 and extracting Northern Province rainfall...")
with h5py.File(cache_file, "r") as f:
    root_keys = list(f.keys())
    print(f"  Root keys: {root_keys}")

    # V07C flat nc4: 'precipitation' at root (no /Grid/ group)
    precip_var = next((k for k in root_keys if k in ("precipitation", "precipitationCal")), None)
    if precip_var is None:
        print("  ERROR: no precipitation variable found in", root_keys)
        sys.exit(1)

    raw  = f[precip_var][:]
    lats = f["lat"][:]
    lons = f["lon"][:]

print(f"  Variable '{precip_var}' shape: {raw.shape}")
print(f"  Lat: {lats.min():.2f} to {lats.max():.2f}  ({len(lats)} pts)")
print(f"  Lon: {lons.min():.2f} to {lons.max():.2f}  ({len(lons)} pts)")

# Determine axis layout from dimension sizes
if raw.ndim == 3:
    _, d1, d2 = raw.shape
    if d1 == len(lats) and d2 == len(lons):
        precip = raw[0]              # [time, lat, lon]
        def lookup(la, lo):
            return precip[int(np.argmin(np.abs(lats - la))), int(np.argmin(np.abs(lons - lo)))]
        print("  Axis order: time, lat, lon")
    else:
        precip = raw[0]              # [time, lon, lat]
        def lookup(la, lo):
            return precip[int(np.argmin(np.abs(lons - lo))), int(np.argmin(np.abs(lats - la)))]
        print("  Axis order: time, lon, lat")
else:
    precip = raw
    def lookup(la, lo):
        return precip[int(np.argmin(np.abs(lats - la))), int(np.argmin(np.abs(lons - lo)))]
    print(f"  Axis order: 2D {raw.shape}")

precip_arr = np.array(precip, dtype=float)
precip_arr[precip_arr < 0] = 0

DISTRICTS = {
    "Musanze": (-1.50, 29.63),
    "Gakenke": (-1.70, 29.78),
    "Burera":  (-1.46, 29.85),
    "Gicumbi": (-1.57, 30.07),
}

print(f"\n  District rainfall for {target}:")
for district, (lat, lon) in DISTRICTS.items():
    val = float(lookup(lat, lon))
    print(f"    {district:10s}  ({lat:.2f}, {lon:.2f})  {val:.1f} mm/day")

print("\nIMERG integration test PASSED")
