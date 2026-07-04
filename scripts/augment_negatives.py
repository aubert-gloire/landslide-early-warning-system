"""
scripts/augment_negatives.py

Augments training_matrix.parquet with stratified negative samples drawn from
CHIRPS historical data + static terrain features.

Sampling strategy:
  - 60% from MAM (March-April-May) and ON (October-November) rainy seasons
    — these are hard negatives (high rainfall, no landslide — harder to learn)
  - 40% from dry-season days for contrast
  - Exclude ±30 days around known positive events (label contamination prevention)
  - Stratify by district: ~65 samples per district (Gakenke, Burera, Musanze, Gicumbi)
  - Total target: ~260 new negatives

Why more negatives?
  Current ratio: 3.3:1 (40 neg / 12 pos) — too easy, model learns a trivial boundary.
  Target ratio : ~22:1 (260 neg / 12 pos) — realistic for daily operational prediction.
  class_weight='balanced' in each model will compensate for the imbalance during training.

Usage:
    python scripts/augment_negatives.py
"""
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

PROCESSED = REPO_ROOT / "data/processed"

TARGET_NEG_PER_DISTRICT = 65   # 4 districts x 65 = 260 negatives
WET_MONTHS = {3, 4, 5, 10, 11} # MAM + ON rainy seasons
WET_FRACTION = 0.60             # 60% from wet season (harder negatives)
EXCL_DAYS = 30                  # exclude ±30 days around any known positive event
SEED = 42


def main():
    print("=" * 62)
    print("  Training Matrix — Stratified Negative Augmentation")
    print("=" * 62)

    # Load all data files
    matrix  = pd.read_parquet(PROCESSED / "training_matrix.parquet")
    chirps  = pd.read_parquet(PROCESSED / "chirps_historical.parquet")
    terrain = pd.read_parquet(PROCESSED / "terrain_per_unit.parquet")
    soil    = pd.read_parquet(PROCESSED / "soil_per_unit.parquet")
    units   = gpd.read_file(PROCESSED / "slope_units.gpkg")

    ndvi_file = next(PROCESSED.glob("ndvi_*.parquet"), None)
    ndvi = pd.read_parquet(ndvi_file) if ndvi_file else None

    matrix["date"]  = pd.to_datetime(matrix["date"])
    chirps["date"]  = pd.to_datetime(chirps["date"])

    print(f"\nCurrent matrix : {len(matrix)} rows  "
          f"({(matrix['label']==1).sum()} pos, {(matrix['label']==0).sum()} neg)")

    # Build exclusion window: ±EXCL_DAYS around every known event
    event_dates = matrix[matrix["label"] == 1]["date"].dt.normalize().tolist()
    excluded = set()
    for ed in event_dates:
        for d in range(-EXCL_DAYS, EXCL_DAYS + 1):
            excluded.add((ed + pd.Timedelta(days=d)).normalize())
    print(f"Exclusion zone : {len(excluded)} dates  (±{EXCL_DAYS} days around {len(event_dates)} events)")

    # Build static feature table per unit_id
    static = terrain.set_index("unit_id")
    if ndvi is not None:
        static = static.join(ndvi.set_index("unit_id")[["ndvi"]], how="left")
    if "soil_class" in soil.columns:
        static = static.join(soil.set_index("unit_id")[["soil_class"]], how="left")

    # District + centroid lookup from slope_units
    dist_map = units.set_index("unit_id")["district"]
    units_crs = units.copy()
    units_crs["clon"] = units_crs.geometry.centroid.x
    units_crs["clat"] = units_crs.geometry.centroid.y
    centroid_map = units_crs.set_index("unit_id")[["clat", "clon"]]

    # Existing (unit_id, date) keys to skip duplicates
    existing_keys = set(
        zip(matrix["unit_id"].astype(int), matrix["date"].dt.normalize())
    )

    districts = ["Gakenke", "Burera", "Musanze", "Gicumbi"]
    new_rows = []
    rng = np.random.default_rng(SEED)

    for district in districts:
        district_unit_ids = dist_map[dist_map == district].index.tolist()
        if not district_unit_ids:
            print(f"  [WARN] No units for {district}, skipping")
            continue

        pool = chirps[chirps["unit_id"].isin(district_unit_ids)].copy()
        pool["date_norm"] = pool["date"].dt.normalize()
        pool["month"]     = pool["date"].dt.month

        # Exclude event neighbourhood
        pool = pool[~pool["date_norm"].isin(excluded)].copy()

        wet = pool[pool["month"].isin(WET_MONTHS)]
        dry = pool[~pool["month"].isin(WET_MONTHS)]

        n_wet = int(TARGET_NEG_PER_DISTRICT * WET_FRACTION)
        n_dry = TARGET_NEG_PER_DISTRICT - n_wet

        # Handle case where one stratum is smaller than target
        actual_wet = min(n_wet, len(wet))
        actual_dry = min(n_dry + (n_wet - actual_wet), len(dry))

        sampled = pd.concat([
            wet.sample(n=actual_wet, random_state=SEED),
            dry.sample(n=actual_dry, random_state=SEED),
        ], ignore_index=True).drop_duplicates(subset=["unit_id", "date_norm"])

        added = 0
        for _, row in sampled.iterrows():
            uid  = int(row["unit_id"])
            dkey = (uid, row["date_norm"])
            if dkey in existing_keys:
                continue

            nr = {
                "unit_id"           : uid,
                "date"              : row["date_norm"],
                "label"             : 0,
                "daily_mm"          : float(row["daily_mm"]),
                "antecedent_5day_mm": float(row["antecedent_5day_mm"]),
                "district"          : district,
                "source"            : "augmented_chirps",
            }

            if uid in centroid_map.index:
                nr["centroid_lat"] = float(centroid_map.loc[uid, "clat"])
                nr["centroid_lon"] = float(centroid_map.loc[uid, "clon"])

            if uid in static.index:
                for col in ["slope_angle", "aspect", "twi", "drainage_density", "ndvi", "soil_class"]:
                    if col in static.columns:
                        val = static.loc[uid, col]
                        nr[col] = float(val) if col != "soil_class" and not isinstance(val, str) else val

            new_rows.append(nr)
            existing_keys.add(dkey)
            added += 1

        print(f"  {district:<12}  units={len(district_unit_ids)}  "
              f"pool={len(pool):,}  sampled={len(sampled)}  added={added}")

    if not new_rows:
        print("\nNo new rows produced — training matrix unchanged.")
        return

    augmented = pd.concat([matrix, pd.DataFrame(new_rows)], ignore_index=True)
    augmented.to_parquet(PROCESSED / "training_matrix.parquet", index=False)

    old_neg = (matrix["label"] == 0).sum()
    new_neg = (augmented["label"] == 0).sum()

    print(f"\n{'='*62}")
    print(f"  Done.")
    print(f"  Total rows : {len(matrix):>5} -> {len(augmented)}")
    print(f"  Positives  : {(matrix['label']==1).sum():>5} -> {(augmented['label']==1).sum()}")
    print(f"  Negatives  : {old_neg:>5} -> {new_neg}  (+{new_neg - old_neg})")
    ratio = new_neg / max((augmented['label']==1).sum(), 1)
    print(f"  Ratio neg:pos = {ratio:.1f}:1  (was {old_neg/(matrix['label']==1).sum():.1f}:1)")
    print(f"  Saved -> data/processed/training_matrix.parquet")
    print("=" * 62)


if __name__ == "__main__":
    main()
