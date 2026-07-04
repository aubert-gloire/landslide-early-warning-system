"""
scripts/integrate_manual_labels.py

Integrates landslide events you found manually in non-API sources
(MINEMA situation reports, AllAfrica news, Red Cross reports, UN OCHA PDFs)
into training_matrix.parquet.

How to use:
  1. When you find an event in a report, add a row to:
         data/labels/manual_events.csv

     The CSV must have these columns:
       date        — YYYY-MM-DD  (the event date or best estimate)
       latitude    — decimal degrees (e.g. -1.6995)
       longitude   — decimal degrees (e.g. 29.7855)
       source      — where you found it (e.g. "MINEMA 2019 annual report p.12")
       notes       — anything relevant (fatalities, district, landmark)

     Latitude and longitude can be approximate — the script snaps to the
     nearest slope unit within 25 km. If you only know the district, use
     the district centroid coordinates:
       Gakenke  : -1.70, 29.79
       Burera   : -1.40, 29.84
       Musanze  : -1.50, 29.63
       Gicumbi  : -1.57, 30.08
       (Western Province)
       Rubavu   : -1.68, 29.34
       Ngororero: -1.84, 29.57
       Nyamasheke: -2.34, 29.12

  2. Run:  python scripts/integrate_manual_labels.py
           python scripts/integrate_manual_labels.py --dry-run  (preview only)

  3. The script will:
       - Snap each row to the nearest slope unit
       - Look up CHIRPS rainfall for that date (±1 day tolerance)
       - Show you the matched rainfall values before saving
       - Skip rows that already exist in the training matrix

Outputs:
    data/processed/training_matrix.parquet  (updated)
    data/labels/manual_events_integrated.csv  (log of what was added)
"""

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

PROCESSED = REPO_ROOT / "data/processed"
LABELS    = REPO_ROOT / "data/labels"

MANUAL_CSV    = LABELS / "manual_events.csv"
INTEGRATED_LOG = LABELS / "manual_events_integrated.csv"

TEMPLATE_COLS = ["date", "latitude", "longitude", "source", "notes"]

FEATURE_COLS = [
    "slope_angle", "aspect", "twi", "drainage_density",
    "ndvi", "soil_class", "daily_mm", "antecedent_5day_mm",
]


def load_or_create_template() -> pd.DataFrame:
    if not MANUAL_CSV.exists():
        template = pd.DataFrame(columns=TEMPLATE_COLS + ["include"])
        template.to_csv(MANUAL_CSV, index=False)
        print(f"Created empty template -> {MANUAL_CSV}")
        print("Fill in event rows, then re-run this script.")
        sys.exit(0)

    df = pd.read_csv(MANUAL_CSV)
    # Optional 'include' column — if absent, treat all rows as included
    if "include" not in df.columns:
        df["include"] = "yes"

    # Only process rows explicitly marked yes (or unmarked)
    df = df[df["include"].astype(str).str.lower().isin(["yes", "y", "1", "true", ""])]
    df = df.reset_index(drop=True)
    return df


def snap_to_units(events: pd.DataFrame, slope_units: gpd.GeoDataFrame) -> pd.DataFrame:
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
            nearest_idx = dists.idxmin()
            dist_km = dists.min() * 111  # rough degree-to-km
            if dists.min() < 0.25:
                joined.loc[idx, "unit_id"]  = centroids.loc[nearest_idx, "unit_id"]
                joined.loc[idx, "district"] = centroids.loc[nearest_idx, "district"]
                print(f"    Row {idx}: snapped to unit "
                      f"{int(centroids.loc[nearest_idx, 'unit_id'])} "
                      f"({dist_km:.1f} km from input point)")
            else:
                print(f"    Row {idx}: no slope unit within 25 km — skipping")

    return joined.dropna(subset=["unit_id"]).reset_index(drop=True)


def match_chirps(
    events: pd.DataFrame,
    chirps: pd.DataFrame,
    existing: pd.DataFrame,
) -> tuple[pd.DataFrame, list[dict]]:
    chirps = chirps.copy()
    chirps["date"] = pd.to_datetime(chirps["date"])

    static_cols = [c for c in FEATURE_COLS if c not in ("daily_mm", "antecedent_5day_mm")]
    static_per_unit = (
        existing[["unit_id"] + [c for c in static_cols if c in existing.columns]]
        .drop_duplicates("unit_id")
    )

    existing["date"] = pd.to_datetime(existing["date"])
    pos_keys = set(
        zip(
            existing[existing["label"] == 1]["unit_id"].astype(int),
            existing[existing["label"] == 1]["date"].dt.normalize(),
        )
    )

    new_rows, skipped = [], []

    for _, ev in events.iterrows():
        uid   = int(ev["unit_id"])
        edate = pd.Timestamp(ev["date"]).normalize()
        src   = str(ev.get("source", "manual"))
        notes = str(ev.get("notes", ""))

        # Already in training matrix?
        if (uid, edate) in pos_keys:
            skipped.append({"reason": "already in matrix", "unit_id": uid,
                            "date": edate, "source": src})
            print(f"    Skip (duplicate): unit {uid} on {edate.date()}")
            continue

        # Find CHIRPS row (±1 day tolerance for date uncertainty)
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
                    "source":             src,
                    "district":           str(ev.get("district", "")),
                    "_notes":             notes,
                    "_input_lat":         float(ev["latitude"]),
                    "_input_lon":         float(ev["longitude"]),
                })
                matched = True
                break

        if not matched:
            skipped.append({"reason": "no CHIRPS data", "unit_id": uid,
                            "date": edate, "source": src})
            print(f"    Skip (no CHIRPS): unit {uid} on {edate.date()} ±1 day")

    if new_rows:
        new_df = pd.DataFrame(new_rows)
        if not static_per_unit.empty:
            new_df = new_df.merge(static_per_unit, on="unit_id", how="left")
    else:
        new_df = pd.DataFrame()

    return new_df, skipped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview what would be added without saving")
    args = parser.parse_args()

    print("=" * 64)
    print("  Manual Label Integration")
    print("=" * 64)
    print(f"  Input: {MANUAL_CSV}")

    events = load_or_create_template()
    if events.empty:
        print("\nNo rows marked for inclusion in manual_events.csv.")
        return

    events["date"]      = pd.to_datetime(events["date"], errors="coerce")
    events["latitude"]  = pd.to_numeric(events["latitude"],  errors="coerce")
    events["longitude"] = pd.to_numeric(events["longitude"], errors="coerce")

    bad = events[events[["date","latitude","longitude"]].isna().any(axis=1)]
    if not bad.empty:
        print(f"\n[WARN] {len(bad)} rows have invalid date/lat/lon and will be skipped:")
        print(bad[["date","latitude","longitude","source"]].to_string())
        events = events.dropna(subset=["date","latitude","longitude"])

    if events.empty:
        print("No valid rows remain after parsing.")
        return

    print(f"\n  {len(events)} rows to process")

    slope_units    = gpd.read_file(PROCESSED / "slope_units.gpkg")
    chirps         = pd.read_parquet(PROCESSED / "chirps_historical.parquet")
    existing       = pd.read_parquet(PROCESSED / "training_matrix.parquet")

    print(f"\nExisting matrix: {len(existing)} rows  "
          f"({(existing['label']==1).sum()} pos, {(existing['label']==0).sum()} neg)")

    print("\n-- Snapping events to slope units --")
    mapped = snap_to_units(events, slope_units)
    print(f"  {len(mapped)} events mapped")

    print("\n-- Matching CHIRPS rainfall --")
    new_rows, skipped = match_chirps(mapped, chirps, existing)

    if new_rows.empty:
        print("\nNo new rows to add.")
        return

    # Preview
    display_cols = ["unit_id", "district", "date", "daily_mm",
                    "antecedent_5day_mm", "source"]
    print(f"\n{'─'*76}")
    print("  EVENTS READY TO INTEGRATE")
    print(f"{'─'*76}")
    print(f"  {'Unit':>5}  {'District':<12}  {'Date':<12}  "
          f"{'Rain mm':>8}  {'5-day mm':>9}  Source")
    print(f"  {'─'*5}  {'─'*12}  {'─'*12}  {'─'*8}  {'─'*9}  {'─'*20}")
    for _, r in new_rows.iterrows():
        print(f"  {int(r['unit_id']):>5}  {str(r.get('district','')):<12}  "
              f"{str(r['date'])[:10]:<12}  {r['daily_mm']:>8.1f}  "
              f"{r['antecedent_5day_mm']:>9.1f}  {r.get('source','')[:20]}")
    print(f"{'─'*76}")
    print(f"  Total to add: {len(new_rows)}  |  Skipped: {len(skipped)}")

    if args.dry_run:
        print("\n[DRY RUN] No changes saved. Remove --dry-run to write.")
        return

    # Append to training matrix
    existing["date"] = pd.to_datetime(existing["date"])
    new_rows["date"] = pd.to_datetime(new_rows["date"])
    log_cols = [c for c in new_rows.columns if not c.startswith("_")]
    augmented = pd.concat([existing, new_rows[log_cols]], ignore_index=True)
    augmented.to_parquet(PROCESSED / "training_matrix.parquet", index=False)

    # Save integration log
    log = new_rows[["unit_id", "district", "date", "daily_mm",
                    "antecedent_5day_mm", "source",
                    "_notes", "_input_lat", "_input_lon"]].copy()
    log.columns = [c.lstrip("_") for c in log.columns]
    log.to_csv(INTEGRATED_LOG, index=False)

    old_pos = (existing["label"] == 1).sum()
    new_pos = (augmented["label"] == 1).sum()

    print(f"\n{'='*64}")
    print(f"  Done.")
    print(f"  Positive labels : {old_pos} -> {new_pos}  (+{new_pos - old_pos})")
    print(f"  Total rows      : {len(existing)} -> {len(augmented)}")
    print(f"  Saved -> data/processed/training_matrix.parquet")
    print(f"  Log  -> {INTEGRATED_LOG}")
    print(f"\n  Next: Kernel -> Restart & Run All in ModelNotebook.ipynb")
    print("=" * 64)


if __name__ == "__main__":
    main()
