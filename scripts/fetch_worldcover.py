"""
scripts/fetch_worldcover.py

Extracts ESA WorldCover 2021 (10m land use classification) per slope unit
via Google Earth Engine and saves to data/processed/landuse_per_unit.parquet.

Why this matters:
  Land use is a proxy for root cohesion — the resistance plant roots provide
  to slope failure. Deforested or cultivated slopes fail far more easily than
  forested ones under the same rainfall load. NDVI captures current greenness
  but a discrete land-use class (forest vs cropland vs bare) is a stronger,
  less noisy signal for structural soil reinforcement.

ESA WorldCover 2021 classes (the ones relevant to landslide risk):
  10  — Tree cover (forest)           LOW risk contribution
  20  — Shrubland                     LOW-MEDIUM
  30  — Grassland                     MEDIUM
  40  — Cropland                      MEDIUM-HIGH  (seasonal root loss)
  50  — Built-up                      HIGH (impervious, fast runoff)
  60  — Bare / sparse vegetation      HIGH (no cohesion)
  80  — Permanent water bodies        N/A
  90  — Herbaceous wetland            HIGH (already saturated)
  95  — Mangroves                     N/A for Rwanda

The dominant class per slope unit is extracted (mode aggregation).

Usage:
    python scripts/fetch_worldcover.py

Requires:
    - Google Earth Engine authenticated (gee_key.json in secrets/)
    - slope_units.gpkg in data/processed/

Output:
    data/processed/landuse_per_unit.parquet
      columns: unit_id, landuse_class (int), landuse_label (str)
"""

import json
import os
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / ".env")

PROCESSED = REPO_ROOT / "data/processed"

WORLDCOVER_CLASSES = {
    10: "Tree cover",
    20: "Shrubland",
    30: "Grassland",
    40: "Cropland",
    50: "Built-up",
    60: "Bare / sparse vegetation",
    70: "Snow and ice",
    80: "Permanent water bodies",
    90: "Herbaceous wetland",
    95: "Mangroves",
    100: "Moss and lichen",
}

# Risk contribution of each land use class for context
LANDUSE_RISK = {
    10: "low",      # Tree cover — strong root cohesion
    20: "low",      # Shrubland
    30: "medium",   # Grassland — seasonal cohesion
    40: "medium",   # Cropland — tilled, seasonal roots
    50: "high",     # Built-up — impervious, fast runoff
    60: "high",     # Bare — no cohesion
    90: "high",     # Wetland — perpetually saturated
    95: "low",      # Mangroves (not present in Rwanda)
}


def init_gee() -> bool:
    """Initialise GEE using service account key or interactive auth."""
    try:
        import ee
    except ImportError:
        print("[ERROR] earthengine-api not installed.")
        print("  Run: pip install earthengine-api")
        return False

    key_file = REPO_ROOT / os.getenv("GEE_KEY_FILE", "secrets/gee_key.json")
    svc_account = os.getenv("GEE_SERVICE_ACCOUNT", "")

    if key_file.exists() and svc_account:
        try:
            credentials = ee.ServiceAccountCredentials(svc_account, str(key_file))
            ee.Initialize(credentials)
            print(f"[GEE] Authenticated via service account: {svc_account}")
            return True
        except Exception as e:
            print(f"[GEE] Service account auth failed: {e}")

    # Fallback — interactive auth (opens browser)
    try:
        ee.Authenticate()
        ee.Initialize()
        print("[GEE] Authenticated interactively")
        return True
    except Exception as e:
        print(f"[GEE] Authentication failed: {e}")
        return False


def extract_worldcover_per_unit(slope_units: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    For each slope unit, extract the dominant ESA WorldCover 2021 class
    using GEE reduceRegion (mode aggregation over the unit polygon).
    """
    import ee

    print("[GEE] Loading ESA WorldCover 2021...")
    worldcover = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map")

    results = []
    total = len(slope_units)
    batch_size = 50  # GEE rate limit: ~50 feature requests per batch

    for start in range(0, total, batch_size):
        batch = slope_units.iloc[start:start + batch_size]
        print(f"  Processing units {start + 1}–{min(start + batch_size, total)} / {total}...")

        for _, row in batch.iterrows():
            uid = int(row["unit_id"])
            geom = row.geometry

            try:
                # Convert shapely geometry to GEE geometry
                geojson = json.loads(gpd.GeoSeries([geom], crs="EPSG:4326").to_json())
                ee_geom = ee.Geometry(geojson["features"][0]["geometry"])

                # Mode (most common class) aggregation
                result = worldcover.reduceRegion(
                    reducer=ee.Reducer.mode(),
                    geometry=ee_geom,
                    scale=10,
                    maxPixels=1e8,
                ).getInfo()

                lc = result.get("Map")
                if lc is None:
                    lc = 30  # default: grassland if no data
                lc = int(lc)

            except Exception as e:
                print(f"    [WARN] Unit {uid}: {e} — using default class 30")
                lc = 30

            results.append({
                "unit_id":       uid,
                "landuse_class": lc,
                "landuse_label": WORLDCOVER_CLASSES.get(lc, f"Class {lc}"),
                "landuse_risk":  LANDUSE_RISK.get(lc, "medium"),
            })

        # Respect GEE rate limits
        if start + batch_size < total:
            time.sleep(1)

    return pd.DataFrame(results)


def extract_worldcover_export(slope_units: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    Alternative extraction using GEE batch export to Google Drive.
    Use this if the per-unit reduceRegion approach hits quota limits.
    Prints instructions for manual download.
    """
    import ee

    print("[GEE] Preparing batch export to Google Drive...")
    worldcover = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map")

    # Convert slope units to GEE FeatureCollection
    features = []
    for _, row in slope_units.iterrows():
        geojson = json.loads(gpd.GeoSeries([row.geometry], crs="EPSG:4326").to_json())
        ee_geom = ee.Geometry(geojson["features"][0]["geometry"])
        feat    = ee.Feature(ee_geom, {"unit_id": int(row["unit_id"])})
        features.append(feat)

    fc = ee.FeatureCollection(features)

    # Zonal statistics: dominant land class per unit
    result_fc = worldcover.reduceRegions(
        collection=fc,
        reducer=ee.Reducer.mode().setOutputs(["landuse_class"]),
        scale=10,
    )

    task = ee.batch.Export.table.toDrive(
        collection=result_fc,
        description="worldcover_per_unit",
        fileFormat="CSV",
        selectors=["unit_id", "landuse_class"],
    )
    task.start()

    print("\n  Export task started on GEE.")
    print("  Go to https://code.earthengine.google.com/tasks to monitor progress.")
    print("  When done, download 'worldcover_per_unit.csv' from Google Drive.")
    print(f"  Then copy it to: {PROCESSED / 'worldcover_per_unit_raw.csv'}")
    print("  And re-run this script — it will detect and parse the file automatically.")
    return pd.DataFrame()


def load_from_export() -> pd.DataFrame | None:
    """If the GEE batch export CSV was downloaded manually, parse it."""
    export_path = PROCESSED / "worldcover_per_unit_raw.csv"
    if not export_path.exists():
        return None

    print(f"[LOCAL] Found GEE export file: {export_path}")
    raw = pd.read_csv(export_path)
    raw.columns = [c.lower().strip() for c in raw.columns]

    lc_col = next((c for c in raw.columns if "landuse" in c or "mode" in c or "map" in c), None)
    if not lc_col or "unit_id" not in raw.columns:
        print(f"  [WARN] Unexpected columns: {list(raw.columns)} — cannot parse")
        return None

    raw = raw.rename(columns={lc_col: "landuse_class"})
    raw["landuse_class"] = pd.to_numeric(raw["landuse_class"], errors="coerce").fillna(30).astype(int)
    raw["landuse_label"] = raw["landuse_class"].map(WORLDCOVER_CLASSES).fillna("Unknown")
    raw["landuse_risk"]  = raw["landuse_class"].map(LANDUSE_RISK).fillna("medium")
    return raw[["unit_id", "landuse_class", "landuse_label", "landuse_risk"]]


def main():
    print("=" * 60)
    print("  ESA WorldCover 2021 — Land Use per Slope Unit")
    print("=" * 60)

    out_path = PROCESSED / "landuse_per_unit.parquet"
    if out_path.exists():
        existing = pd.read_parquet(out_path)
        print(f"\nExisting file found: {out_path}  ({len(existing)} units)")
        ans = input("Re-extract? This will overwrite. [y/N]: ").strip().lower()
        if ans != "y":
            print("Skipped.")
            return

    slope_units = gpd.read_file(PROCESSED / "slope_units.gpkg")
    print(f"\nSlope units: {len(slope_units)}")

    # Check for manually downloaded GEE export first
    df = load_from_export()

    if df is None:
        # Try live GEE extraction
        if not init_gee():
            print("\n[ERROR] GEE authentication failed.")
            print("  Option 1: Fix GEE credentials in secrets/gee_key.json")
            print("  Option 2: Run the GEE export manually:")
            print("    python scripts/fetch_worldcover.py --export")
            sys.exit(1)

        print("\nExtracting land use class per unit via GEE (mode aggregation)...")
        df = extract_worldcover_per_unit(slope_units)

    if df.empty:
        print("\nNo data extracted. Check GEE logs above.")
        return

    df["unit_id"] = df["unit_id"].astype(int)
    df = df.sort_values("unit_id").reset_index(drop=True)
    df.to_parquet(out_path, index=False)

    print(f"\n{'='*60}")
    print(f"  Done. {len(df)} units extracted.")
    print(f"  Saved -> {out_path}")
    print(f"\n  Land use distribution:")
    for lc, grp in df.groupby("landuse_class"):
        label = WORLDCOVER_CLASSES.get(lc, f"Class {lc}")
        risk  = LANDUSE_RISK.get(lc, "medium")
        print(f"    {lc:>4}  {label:<30}  n={len(grp):>4}  risk={risk}")
    print(f"\n  Next: add 'landuse_class' to FEATURE_COLS in ModelNotebook.ipynb")
    print("=" * 60)


if __name__ == "__main__":
    if "--export" in sys.argv:
        slope_units = gpd.read_file(PROCESSED / "slope_units.gpkg")
        if not init_gee():
            sys.exit(1)
        extract_worldcover_export(slope_units)
    else:
        main()
