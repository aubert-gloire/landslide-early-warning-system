"""
scripts/enrich_chirps.py

One-time script — adds three new rainfall features to the existing
chirps_historical.parquet WITHOUT redownloading any data.

New columns:
  antecedent_3day_mm       — 3-day rolling sum (shallow soil saturation)
  antecedent_10day_mm      — 10-day rolling sum (deep clay soil saturation)
  rainfall_intensity_ratio — daily_mm / (antecedent_5day_mm + 1)
                             captures sudden burst vs gradual accumulation

Why these matter:
  - Different soil depths respond to different accumulation windows.
    Shallow volcanic soils (dominant in Northern Province) saturate
    in 3 days; deeper clay soils need 10+ days.
  - The intensity ratio distinguishes two failure mechanisms:
    (a) a sudden storm onto dry soil (high ratio)
    (b) the final increment onto already-saturated ground (low ratio)
    Both trigger landslides but via different pore-pressure dynamics.

Usage:
    python scripts/enrich_chirps.py

Safe to re-run — skips if columns already exist.
"""

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

PROCESSED = REPO_ROOT / "data/processed"
CHIRPS_PATH = PROCESSED / "chirps_historical.parquet"


def main():
    print("=" * 60)
    print("  CHIRPS Feature Enrichment")
    print("=" * 60)

    if not CHIRPS_PATH.exists():
        print(f"\n[ERROR] {CHIRPS_PATH} not found.")
        print("  Run: python scripts/setup_db.py chirps")
        return

    df = pd.read_parquet(CHIRPS_PATH)
    df["date"] = pd.to_datetime(df["date"])

    print(f"\nLoaded: {len(df):,} rows  |  {df['unit_id'].nunique()} units  "
          f"|  {df['date'].nunique()} days")
    print(f"Existing columns: {list(df.columns)}")

    already = all(c in df.columns for c in
                  ("antecedent_3day_mm", "antecedent_10day_mm", "rainfall_intensity_ratio"))
    if already:
        print("\nAll new columns already present — nothing to do.")
        return

    df = df.sort_values(["unit_id", "date"])

    if "antecedent_3day_mm" not in df.columns:
        print("\nComputing antecedent_3day_mm  (3-day rolling sum per unit)...")
        df["antecedent_3day_mm"] = (
            df.groupby("unit_id")["daily_mm"]
            .transform(lambda s: s.rolling(3, min_periods=1).sum())
        )

    if "antecedent_10day_mm" not in df.columns:
        print("Computing antecedent_10day_mm (10-day rolling sum per unit)...")
        df["antecedent_10day_mm"] = (
            df.groupby("unit_id")["daily_mm"]
            .transform(lambda s: s.rolling(10, min_periods=1).sum())
        )

    if "rainfall_intensity_ratio" not in df.columns:
        print("Computing rainfall_intensity_ratio (daily / (5day + 1))...")
        df["rainfall_intensity_ratio"] = (
            df["daily_mm"] / (df["antecedent_5day_mm"] + 1.0)
        ).round(4)

    df.to_parquet(CHIRPS_PATH, index=False)

    print(f"\n{'='*60}")
    print(f"  Done. Enriched {len(df):,} rows.")
    print(f"  New columns:")
    print(f"    antecedent_3day_mm        "
          f"mean={df['antecedent_3day_mm'].mean():.2f}  "
          f"max={df['antecedent_3day_mm'].max():.2f}")
    print(f"    antecedent_10day_mm       "
          f"mean={df['antecedent_10day_mm'].mean():.2f}  "
          f"max={df['antecedent_10day_mm'].max():.2f}")
    print(f"    rainfall_intensity_ratio  "
          f"mean={df['rainfall_intensity_ratio'].mean():.3f}  "
          f"max={df['rainfall_intensity_ratio'].max():.3f}")
    print(f"  Saved -> {CHIRPS_PATH}")
    print(f"\n  Next steps:")
    print(f"    python scripts/fetch_worldcover.py   (add land use feature)")
    print(f"    Kernel -> Restart & Run All in ModelNotebook.ipynb")
    print("=" * 60)


if __name__ == "__main__":
    main()
