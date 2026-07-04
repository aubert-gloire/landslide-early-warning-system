"""
scripts/rebuild_training_matrix.py

Joins new feature columns into the existing training_matrix.parquet.
Run this whenever new feature sources are added — faster than rebuilding
from scratch because it preserves existing rows and labels.

Adds:
  antecedent_3day_mm       — from chirps_historical.parquet (unit_id + date)
  antecedent_10day_mm      — from chirps_historical.parquet (unit_id + date)
  rainfall_intensity_ratio — from chirps_historical.parquet (unit_id + date)
  landuse_class            — from landuse_per_unit.parquet  (unit_id)

Usage:
    python scripts/rebuild_training_matrix.py
"""
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

PROCESSED = REPO_ROOT / "data/processed"


def main():
    print("=" * 60)
    print("  Training Matrix — Feature Rebuild")
    print("=" * 60)

    matrix = pd.read_parquet(PROCESSED / "training_matrix.parquet")
    matrix["date"] = pd.to_datetime(matrix["date"])

    print(f"\nExisting matrix: {len(matrix)} rows | cols: {list(matrix.columns)}")

    # ── Join new CHIRPS columns ───────────────────────────────────────────────
    chirps_path = PROCESSED / "chirps_historical.parquet"
    new_chirps_cols = ["antecedent_3day_mm", "antecedent_10day_mm", "rainfall_intensity_ratio"]
    missing_chirps = [c for c in new_chirps_cols if c not in matrix.columns]

    if missing_chirps and chirps_path.exists():
        print(f"\nJoining from CHIRPS: {missing_chirps}")
        chirps = pd.read_parquet(chirps_path)
        chirps["date"] = pd.to_datetime(chirps["date"])

        available = [c for c in new_chirps_cols if c in chirps.columns]
        if available:
            chirps_sub = chirps[["unit_id", "date"] + available]
            matrix = matrix.merge(chirps_sub, on=["unit_id", "date"], how="left")
            for col in available:
                null_count = matrix[col].isna().sum()
                print(f"  {col}: joined  ({null_count} NaN — filled with median)")
                matrix[col] = matrix[col].fillna(matrix[col].median())
        else:
            print(f"  [WARN] New columns not found in CHIRPS yet — run enrich_chirps.py first")
    elif not missing_chirps:
        print("\nNew CHIRPS columns already present — skipping join")

    # ── Join WorldCover land use ──────────────────────────────────────────────
    landuse_path = PROCESSED / "landuse_per_unit.parquet"
    if "landuse_class" not in matrix.columns and landuse_path.exists():
        print("\nJoining from WorldCover: landuse_class")
        landuse = pd.read_parquet(landuse_path)[["unit_id", "landuse_class"]]
        matrix = matrix.merge(landuse, on="unit_id", how="left")
        null_count = matrix["landuse_class"].isna().sum()
        # Fill missing with mode (most common class = tree cover = 10)
        mode_val = matrix["landuse_class"].mode().iloc[0] if not matrix["landuse_class"].mode().empty else 10
        matrix["landuse_class"] = matrix["landuse_class"].fillna(mode_val)
        print(f"  landuse_class: joined  ({null_count} NaN — filled with mode={int(mode_val)})")
    elif "landuse_class" in matrix.columns:
        print("\nlanduse_class already present — skipping join")
    else:
        print("\n[WARN] landuse_per_unit.parquet not found — run fetch_worldcover.py first")

    matrix.to_parquet(PROCESSED / "training_matrix.parquet", index=False)

    print(f"\n{'='*60}")
    print(f"  Done.")
    print(f"  Rows    : {len(matrix)}")
    print(f"  Columns : {list(matrix.columns)}")
    print(f"  Positive: {(matrix['label']==1).sum()}")
    print(f"  Negative: {(matrix['label']==0).sum()}")
    print(f"  Saved -> data/processed/training_matrix.parquet")
    print(f"\n  Ready: Kernel -> Restart & Run All in ModelNotebook.ipynb")
    print("=" * 60)


if __name__ == "__main__":
    main()
