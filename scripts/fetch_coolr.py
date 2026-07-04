"""
scripts/fetch_coolr.py

Downloads confirmed landslide events from two public APIs:
  1. NASA COOLR (Global Landslide Catalog) — ArcGIS FeatureServer
  2. UN OCHA HDX (Humanitarian Data Exchange) — CKAN REST API

Both are filtered to Rwanda Northern Province (+ optionally Western Province),
mapped to slope units, matched against CHIRPS rainfall, and merged into
training_matrix.parquet as new positive labels.

What gets reviewed:
  A summary table is printed showing every candidate event with its
  coordinates, date, rainfall match, and source before anything is saved.
  Run with --dry-run to inspect without writing to disk.

Usage:
    python scripts/fetch_coolr.py              # Northern Province only
    python scripts/fetch_coolr.py --western    # include Western Province too
    python scripts/fetch_coolr.py --dry-run    # print candidates, do not save

Outputs:
    data/labels/coolr_ocha_raw.csv       raw download from both APIs
    data/processed/training_matrix.parquet  updated with new positive rows
"""

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

PROCESSED = REPO_ROOT / "data/processed"
LABELS    = REPO_ROOT / "data/labels"
LABELS.mkdir(parents=True, exist_ok=True)

# ── Bounding boxes ─────────────────────────────────────────────────────────────
# (lat_min, lat_max, lon_min, lon_max)
BBOX_NORTHERN = (-2.0, -1.2, 29.4, 30.4)
BBOX_WESTERN  = (-2.8, -1.0, 28.8, 29.6)

DATE_START = pd.Timestamp("2010-01-01")
DATE_END   = pd.Timestamp("2024-12-31")

FEATURE_COLS = [
    "slope_angle", "aspect", "twi", "drainage_density",
    "ndvi", "soil_class", "daily_mm", "antecedent_5day_mm",
]

# ── NASA COOLR ─────────────────────────────────────────────────────────────────
# Primary endpoint (new NASA EarthData GIS)
COOLR_URL = (
    "https://gis.earthdata.nasa.gov/gis05/rest/services"
    "/Landslides/COOLR_Events_Points/FeatureServer/0/query"
)
# Fallback endpoint (legacy NASA NCCS — often more reliable)
COOLR_URL_FALLBACK = (
    "https://maps.nccs.nasa.gov/arcgis/rest/services"
    "/disaster/landslide_viewer/MapServer/0/query"
)
# Direct CSV download — no pagination, fastest option
COOLR_CSV_URL = (
    "https://catalog.data.gov/dataset/global-landslide-catalog-export"
)

# ── OCHA HDX ───────────────────────────────────────────────────────────────────
# CKAN REST API — searches for Rwanda disaster datasets tagged 'landslide'
OCHA_SEARCH_URL = "https://data.humdata.org/api/3/action/package_search"
OCHA_RESOURCE_URL = "https://data.humdata.org/api/3/action/resource_show"


# ── Fetchers ───────────────────────────────────────────────────────────────────

def _query_arcgis(url: str, timeout: int = 45) -> list:
    """Query an ArcGIS FeatureServer for Rwanda landslide records."""
    all_features, offset, page = [], 0, 1000
    while True:
        try:
            r = requests.get(url, params={
                "where": "country_name='Rwanda'",
                "outFields": "*",
                "f": "geojson",
                "resultRecordCount": page,
                "resultOffset": offset,
            }, timeout=timeout)
            r.raise_for_status()
        except Exception as e:
            print(f"    Request failed: {e}")
            return []
        features = r.json().get("features", [])
        if not features:
            break
        all_features.extend(features)
        print(f"    {len(all_features)} records fetched...")
        if len(features) < page:
            break
        offset += page
    return all_features


def fetch_coolr() -> pd.DataFrame:
    """
    Download Rwanda entries from NASA COOLR.
    Tries primary endpoint, falls back to legacy endpoint on timeout.
    """
    import time

    print("\n[COOLR] Querying NASA Global Landslide Catalog...")

    all_features = []
    for attempt, (url, label) in enumerate([
        (COOLR_URL, "primary (EarthData GIS)"),
        (COOLR_URL_FALLBACK, "fallback (NASA NCCS)"),
    ], 1):
        print(f"  Attempt {attempt}: {label}")
        all_features = _query_arcgis(url, timeout=45)
        if all_features:
            break
        if attempt == 1:
            print("  Retrying with fallback endpoint in 3s...")
            time.sleep(3)

    if not all_features:
        print("  [WARN] Both COOLR endpoints timed out.")
        print("  The NASA GIS servers are sometimes slow — try again in a few minutes.")
        print("  Continuing with OCHA HDX only...")
        return pd.DataFrame()

    print(f"  Total COOLR Rwanda records: {len(all_features)}")

    rows = []
    for feat in all_features:
        props = feat.get("properties", {})
        coords = feat.get("geometry", {}).get("coordinates", [None, None])
        props["longitude"] = coords[0]
        props["latitude"]  = coords[1]
        props["_source"]   = "coolr"
        rows.append(props)

    return pd.DataFrame(rows)


def fetch_ocha() -> pd.DataFrame:
    """
    Query OCHA HDX for Rwanda landslide event records.
    HDX uses the CKAN REST API — returns dataset metadata; we then
    download the actual CSV/GeoJSON resource if available.
    """
    print("\n[OCHA]  Querying UN OCHA Humanitarian Data Exchange...")
    try:
        r = requests.get(OCHA_SEARCH_URL, params={
            "q": "landslide rwanda",
            "fq": "vocab_Topics:landslides",
            "rows": 50,
        }, timeout=30)
        r.raise_for_status()
        results = r.json().get("result", {}).get("results", [])
    except Exception as e:
        print(f"  [WARN] OCHA search failed: {e}")
        return pd.DataFrame()

    print(f"  Found {len(results)} HDX dataset(s) matching 'landslide rwanda'")

    rows = []
    for dataset in results:
        for resource in dataset.get("resources", []):
            fmt = resource.get("format", "").lower()
            url = resource.get("url", "")
            if fmt not in ("csv", "geojson", "json") or not url:
                continue
            try:
                print(f"  Downloading: {resource.get('name', url)[:60]}")
                if fmt == "csv":
                    df = pd.read_csv(url)
                else:
                    df = pd.read_json(url)

                # Normalise column names
                df.columns = [c.lower().strip().replace(" ", "_") for c in df.columns]

                # Try to identify lat/lon columns
                lat_col = next((c for c in df.columns if c in ("latitude", "lat", "y")), None)
                lon_col = next((c for c in df.columns if c in ("longitude", "lon", "long", "x")), None)
                date_col = next((c for c in df.columns if "date" in c), None)

                if not lat_col or not lon_col or not date_col:
                    print(f"    [SKIP] Missing lat/lon/date columns: {list(df.columns[:8])}")
                    continue

                df = df.rename(columns={lat_col: "latitude", lon_col: "longitude", date_col: "event_date_raw"})
                df["_source"] = f"ocha:{dataset.get('name','')}"
                rows.append(df)

            except Exception as ex:
                print(f"    [SKIP] Could not parse {url[:60]}: {ex}")

    if not rows:
        print("  No usable tabular resources found in HDX results.")
        return pd.DataFrame()

    combined = pd.concat(rows, ignore_index=True)
    print(f"  OCHA records loaded: {len(combined)}")
    return combined


# ── Parsing & filtering ────────────────────────────────────────────────────────

def parse_and_filter(raw: pd.DataFrame, bbox) -> pd.DataFrame:
    """Normalise dates, drop rows without coordinates, apply bounding box."""
    df = raw.copy()
    df.columns = [c.lower().strip() for c in df.columns]

    # Latitude / longitude
    for col in ("latitude", "longitude"):
        df[col] = pd.to_numeric(df.get(col, float("nan")), errors="coerce")
    df = df.dropna(subset=["latitude", "longitude"])

    # Date — COOLR uses Unix milliseconds; OCHA uses ISO strings
    date_col = next((c for c in df.columns if "event_date" in c or c == "date"), None)
    if date_col is None:
        print("  [WARN] No date column found — skipping this batch")
        return pd.DataFrame()

    numeric_dates = pd.to_numeric(df[date_col], errors="coerce")
    # Values > 1e10 are milliseconds since epoch
    parsed_ms = pd.to_datetime(
        numeric_dates.where(numeric_dates < 1e10, numeric_dates / 1000),
        unit="s", errors="coerce",
    )
    parsed_iso = pd.to_datetime(df[date_col], errors="coerce", utc=True).dt.tz_localize(None)
    df["event_date"] = parsed_ms.combine_first(parsed_iso)
    df = df.dropna(subset=["event_date"])
    df["event_date"] = df["event_date"].dt.normalize()

    # Bounding box + date range
    lat_min, lat_max, lon_min, lon_max = bbox
    df = df[
        (df["latitude"]  >= lat_min) & (df["latitude"]  <= lat_max) &
        (df["longitude"] >= lon_min) & (df["longitude"] <= lon_max) &
        (df["event_date"] >= DATE_START) & (df["event_date"] <= DATE_END)
    ]
    return df.reset_index(drop=True)


# ── Spatial join ───────────────────────────────────────────────────────────────

def map_to_units(events: pd.DataFrame, slope_units: gpd.GeoDataFrame) -> pd.DataFrame:
    """Snap each event point to the slope unit it falls in (or nearest within 25 km)."""
    gdf = gpd.GeoDataFrame(
        events,
        geometry=[Point(r.longitude, r.latitude) for _, r in events.iterrows()],
        crs="EPSG:4326",
    )
    units = slope_units[["unit_id", "district", "geometry"]].copy()
    joined = gpd.sjoin(gdf, units, how="left", predicate="within")

    missing = joined["unit_id"].isna()
    if missing.any():
        centroids = units.copy()
        centroids["geometry"] = centroids.geometry.centroid
        for idx in joined[missing].index:
            pt = gdf.loc[idx, "geometry"]
            dists = centroids.geometry.distance(pt)
            nearest = dists.idxmin()
            if dists.min() < 0.25:
                joined.loc[idx, "unit_id"] = centroids.loc[nearest, "unit_id"]
                joined.loc[idx, "district"] = centroids.loc[nearest, "district"]

    joined = joined.dropna(subset=["unit_id"])
    joined["unit_id"] = joined["unit_id"].astype(int)
    return joined


# ── CHIRPS match ───────────────────────────────────────────────────────────────

def build_positive_rows(
    events: pd.DataFrame,
    chirps: pd.DataFrame,
    existing_matrix: pd.DataFrame,
) -> pd.DataFrame:
    chirps = chirps.copy()
    chirps["date"] = pd.to_datetime(chirps["date"])

    static_cols = [c for c in FEATURE_COLS if c not in ("daily_mm", "antecedent_5day_mm")]
    static_per_unit = (
        existing_matrix[["unit_id"] + [c for c in static_cols if c in existing_matrix.columns]]
        .drop_duplicates("unit_id")
    )

    new_rows, skipped = [], 0
    for _, ev in events.iterrows():
        uid   = int(ev["unit_id"])
        edate = pd.Timestamp(ev["event_date"]).normalize()

        matched = False
        for delta in (0, -1, 1):
            cdate = edate + pd.Timedelta(days=delta)
            rain  = chirps[(chirps["unit_id"] == uid) & (chirps["date"] == cdate)]
            if not rain.empty:
                r = rain.iloc[0]
                new_rows.append({
                    "unit_id":            uid,
                    "date":               edate,
                    "daily_mm":           float(r["daily_mm"]),
                    "antecedent_5day_mm": float(r["antecedent_5day_mm"]),
                    "label":              1,
                    "source":             str(ev.get("_source", "api")),
                    "district":           str(ev.get("district", "")),
                })
                matched = True
                break

        if not matched:
            skipped += 1

    print(f"  CHIRPS match: {len(new_rows)} matched, {skipped} skipped (no rainfall data)")

    if not new_rows:
        return pd.DataFrame()

    new_df = pd.DataFrame(new_rows)
    if not static_per_unit.empty:
        new_df = new_df.merge(static_per_unit, on="unit_id", how="left")
    return new_df


def deduplicate(existing: pd.DataFrame, new_rows: pd.DataFrame) -> pd.DataFrame:
    existing = existing.copy()
    existing["date"] = pd.to_datetime(existing["date"])
    pos_keys = set(
        zip(
            existing[existing["label"] == 1]["unit_id"].astype(int),
            existing[existing["label"] == 1]["date"].dt.normalize(),
        )
    )
    new_rows["date"] = pd.to_datetime(new_rows["date"])
    filtered = new_rows[
        ~new_rows.apply(
            lambda r: (int(r["unit_id"]), r["date"].normalize()) in pos_keys,
            axis=1,
        )
    ]
    print(f"  New unique rows (not already in matrix): {len(filtered)}")
    return pd.concat([existing, filtered], ignore_index=True)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--western", action="store_true",
                        help="Include Western Province in the bounding box")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print candidates and exit without saving")
    args = parser.parse_args()

    bbox = BBOX_WESTERN if args.western else BBOX_NORTHERN
    region = "Northern + Western Province" if args.western else "Northern Province"

    print("=" * 64)
    print(f"  COOLR + OCHA Label Fetch  [{region}]")
    print("=" * 64)

    slope_units    = gpd.read_file(PROCESSED / "slope_units.gpkg")
    chirps         = pd.read_parquet(PROCESSED / "chirps_historical.parquet")
    existing_matrix = pd.read_parquet(PROCESSED / "training_matrix.parquet")

    print(f"\nExisting matrix: {len(existing_matrix)} rows  "
          f"({(existing_matrix['label']==1).sum()} pos, "
          f"{(existing_matrix['label']==0).sum()} neg)")

    # ── Fetch from both APIs ──────────────────────────────────────────────────
    coolr_raw = fetch_coolr()
    ocha_raw  = fetch_ocha()

    frames = []
    for raw, name in [(coolr_raw, "COOLR"), (ocha_raw, "OCHA")]:
        if raw.empty:
            continue
        filtered = parse_and_filter(raw, bbox)
        print(f"\n[{name}] After bbox + date filter: {len(filtered)} candidate events")
        if not filtered.empty:
            frames.append(filtered)

    if not frames:
        print("\nNo candidate events found from either API.")
        raw_path = LABELS / "coolr_ocha_raw.csv"
        for raw in (coolr_raw, ocha_raw):
            if not raw.empty:
                raw.to_csv(raw_path, index=False)
                print(f"Raw download saved -> {raw_path}")
        return

    all_events = pd.concat(frames, ignore_index=True)

    # Save raw download for your own inspection
    raw_save = pd.concat(
        [df for df in (coolr_raw, ocha_raw) if not df.empty], ignore_index=True
    ) if any(not df.empty for df in (coolr_raw, ocha_raw)) else pd.DataFrame()
    if not raw_save.empty:
        raw_path = LABELS / "coolr_ocha_raw.csv"
        raw_save.to_csv(raw_path, index=False)
        print(f"\nRaw API download -> {raw_path}  ({len(raw_save)} total rows before filtering)")

    # ── Spatial join + CHIRPS match ───────────────────────────────────────────
    print(f"\n-- Mapping {len(all_events)} events to slope units --")
    mapped = map_to_units(all_events, slope_units)

    print(f"\n-- Matching to CHIRPS rainfall --")
    new_rows = build_positive_rows(mapped, chirps, existing_matrix)

    if new_rows.empty:
        print("\nNo usable rows after CHIRPS matching. Training matrix unchanged.")
        return

    # ── Preview table ─────────────────────────────────────────────────────────
    print(f"\n{'─'*80}")
    print(f"  CANDIDATE EVENTS TO ADD  (review before saving)")
    print(f"{'─'*80}")
    print(f"  {'Unit':>5}  {'District':<12}  {'Date':<12}  "
          f"{'Rain mm':>8}  {'5-day mm':>9}  Source")
    print(f"  {'─'*5}  {'─'*12}  {'─'*12}  {'─'*8}  {'─'*9}  {'─'*15}")
    for _, r in new_rows.iterrows():
        print(f"  {int(r['unit_id']):>5}  {str(r.get('district','')):<12}  "
              f"{str(r['date'])[:10]:<12}  {r['daily_mm']:>8.1f}  "
              f"{r['antecedent_5day_mm']:>9.1f}  {r.get('source','')}")
    print(f"{'─'*80}")
    print(f"  Total: {len(new_rows)} candidate positive rows")

    if args.dry_run:
        print("\n[DRY RUN] No changes saved.")
        return

    # ── Merge into training matrix ─────────────────────────────────────────────
    print(f"\n-- Merging into training matrix --")
    augmented = deduplicate(existing_matrix, new_rows)
    augmented.to_parquet(PROCESSED / "training_matrix.parquet", index=False)

    old_pos = (existing_matrix["label"] == 1).sum()
    new_pos = (augmented["label"] == 1).sum()

    print(f"\n{'='*64}")
    print(f"  Done.")
    print(f"  Positive labels : {old_pos} -> {new_pos}  (+{new_pos - old_pos})")
    print(f"  Total rows      : {len(existing_matrix)} -> {len(augmented)}")
    print(f"  Saved -> data/processed/training_matrix.parquet")
    print(f"\n  Next: Kernel -> Restart & Run All in ModelNotebook.ipynb")
    print("=" * 64)


if __name__ == "__main__":
    main()
