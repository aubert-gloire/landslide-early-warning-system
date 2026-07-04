"""
scripts/assign_sectors.py

Downloads Rwanda admin boundaries (level 3 = sectors) from GADM via HDX,
spatial-joins them onto slope unit grid cells, then updates MongoDB so every
unit carries district, sector, and cell labels.

After this runs, SMS alerts and map popups show:
  "Burera / Cyanika sector" instead of just "Burera"

Usage:
    python scripts/assign_sectors.py
"""
import asyncio
import io
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.app.database import get_db

PROCESSED = Path(__file__).parent.parent / "data/processed"

# Rwanda admin level-3 (sectors) — GADM 4.1 GeoJSON via GitHub mirror
GADM_URL = (
    "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_RWA_3.json.zip"
)

NORTHERN_PROVINCE_DISTRICTS = {"Burera", "Gakenke", "Gicumbi", "Musanze", "Rulindo"}


def download_gadm() -> gpd.GeoDataFrame:
    cache = PROCESSED / "gadm41_RWA_3.gpkg"
    if cache.exists():
        print("  Loading cached Rwanda admin L3…")
        return gpd.read_file(cache)

    print("  Downloading Rwanda admin L3 from GADM…")
    r = requests.get(GADM_URL, timeout=120, stream=True)
    r.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        json_name = next(n for n in z.namelist() if n.endswith(".json"))
        with z.open(json_name) as f:
            gdf = gpd.read_file(f)

    gdf.to_file(cache, driver="GPKG")
    print(f"  Cached -> {cache}")
    return gdf


def prepare_admin(gadm: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Filter to Northern Province and normalise column names."""
    # GADM column names: NAME_1=Province, NAME_2=District, NAME_3=Sector
    # GADM uses Kinyarwanda province names — filter by known district names instead
    TARGET_DISTRICTS = {"Burera", "Gakenke", "Gicumbi", "Musanze", "Rulindo"}
    northern = gadm[gadm["NAME_2"].isin(TARGET_DISTRICTS)].copy()
    northern = northern.rename(columns={
        "NAME_2": "district",
        "NAME_3": "sector",
    })[["district", "sector", "geometry"]].reset_index(drop=True)
    northern = northern.to_crs("EPSG:4326")
    print(f"  Northern Province: {len(northern)} sectors across "
          f"{northern['district'].nunique()} districts")
    return northern


def assign_to_units(units: gpd.GeoDataFrame, admin: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Spatial join: each slope unit gets the sector whose centroid overlaps it,
    or the sector with the largest overlap area as fallback.
    """
    units = units.to_crs("EPSG:4326").copy()
    units = units.drop(columns=["district", "sector"], errors="ignore")
    units["centroid"] = units.geometry.centroid

    centroids = units.copy()
    centroids["geometry"] = centroids["centroid"]

    joined = gpd.sjoin(
        centroids[["unit_id", "geometry"]],
        admin[["district", "sector", "geometry"]],
        how="left",
        predicate="within",
    ).drop_duplicates("unit_id")

    units = units.merge(
        joined[["unit_id", "district", "sector"]],
        on="unit_id",
        how="left",
    )

    # Fallback: units whose centroid missed (border cells) — use nearest sector
    missing = units["sector"].isna()
    if missing.any():
        miss_gdf = units[missing].copy()
        miss_gdf["geometry"] = miss_gdf["centroid"]
        nearest = gpd.sjoin_nearest(
            miss_gdf[["unit_id", "geometry"]],
            admin[["district", "sector", "geometry"]],
            how="left",
        ).drop_duplicates("unit_id")
        units.loc[missing, "district"] = units.loc[missing, "unit_id"].map(
            nearest.set_index("unit_id")["district"]
        )
        units.loc[missing, "sector"] = units.loc[missing, "unit_id"].map(
            nearest.set_index("unit_id")["sector"]
        )
        print(f"  {missing.sum()} border units assigned by nearest-sector fallback")

    return units


async def update_mongo(units: gpd.GeoDataFrame):
    db = get_db()
    updated = 0
    for _, row in units.iterrows():
        district = row.get("district") or "Unknown"
        sector = row.get("sector") or "Unknown"
        await db.slope_units.update_one(
            {"unit_id": int(row["unit_id"])},
            {"$set": {"district": district, "sector": sector}},
        )
        updated += 1

    print(f"  MongoDB slope_units updated: {updated} units")

    # Propagate district + sector to predictions
    unit_map = {
        int(r["unit_id"]): {"district": r.get("district", "Unknown"),
                             "sector": r.get("sector", "Unknown")}
        for _, r in units.iterrows()
    }
    pred_cursor = db.predictions.find({}, {"_id": 1, "slope_unit_id": 1})
    pred_updated = 0
    async for pred in pred_cursor:
        info = unit_map.get(pred["slope_unit_id"], {})
        await db.predictions.update_one(
            {"_id": pred["_id"]},
            {"$set": {
                "district": info.get("district", "Unknown"),
                "sector":   info.get("sector", "Unknown"),
            }},
        )
        pred_updated += 1

    print(f"  MongoDB predictions updated: {pred_updated} predictions")


async def main():
    print("=" * 55)
    print("  Sector Assignment for Slope Units")
    print("=" * 55)

    gadm = download_gadm()
    admin = prepare_admin(gadm)

    units = gpd.read_file(PROCESSED / "slope_units.gpkg")
    print(f"\n  Slope units: {len(units)}")

    units = assign_to_units(units, admin)

    assigned = units["sector"].notna().sum()
    print(f"\n  Assigned: {assigned}/{len(units)} units have sector labels")
    print(f"  District breakdown:\n{units['district'].value_counts().to_string()}")
    print(f"\n  Sample sectors:\n{units[['unit_id','district','sector']].head(8).to_string(index=False)}")

    # Save enriched GPKG
    out = PROCESSED / "slope_units.gpkg"
    units.drop(columns=["centroid"], errors="ignore").to_file(out, driver="GPKG")
    print(f"\n  Saved enriched GPKG -> {out}")

    print("\n  Updating MongoDB…")
    await update_mongo(units)

    print("\n" + "=" * 55)
    print("  Done — map popups and SMS will now show sector names")
    print("=" * 55)


if __name__ == "__main__":
    asyncio.run(main())
