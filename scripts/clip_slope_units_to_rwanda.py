"""
One-off migration: clip slope_units geometries to Rwanda's national border.

SlopeUnitGenerator._grid_fallback() draws a plain rectangular grid over the
DEM raster's bounding box with no clipping to any real boundary, so ~37% of
the 396 seeded units ended up entirely outside Rwanda (DRC, Uganda) and
another ~47% straddled the border. This script:

  1. Removes units with (near-)zero overlap with Rwanda — they were never
     real monitored terrain.
  2. Clips the geometry of units that straddle the border to the
     Rwanda-contained portion, recomputing centroid_lat/centroid_lon.
  3. Leaves fully-interior units untouched.

Applies the same fix to both the live MongoDB `slope_units` collection and
the local data/processed/slope_units.gpkg used by the daily pipeline, so the
two stay consistent. Historical predictions/rainfall_records for removed
unit_ids are left in place (orphaned, harmless — every read path already
guards against a missing slope_unit).

Run once: python scripts/clip_slope_units_to_rwanda.py
"""

import os
import sys
from pathlib import Path

import geopandas as gpd
from dotenv import load_dotenv
from pymongo import MongoClient
from shapely.geometry import mapping, shape

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

FULLY_OUT_THRESHOLD = 0.001  # overlap ratio below this = drop entirely
FULLY_IN_THRESHOLD = 0.999   # overlap ratio above this = leave untouched


def main():
    boundary_path = ROOT / "data/processed/gadm41_RWA_3.gpkg"
    gpkg_path = ROOT / "data/processed/slope_units.gpkg"

    boundary_gdf = gpd.read_file(boundary_path)
    boundary = boundary_gdf.dissolve().geometry.iloc[0]

    client = MongoClient(os.environ["MONGODB_URI"], serverSelectionTimeoutMS=8000)
    db = client[os.environ.get("MONGODB_DB_NAME", "landslide_ews")]

    docs = list(db.slope_units.find({}))
    print(f"Loaded {len(docs)} slope units from MongoDB")

    to_remove_ids = []
    to_clip = []  # (unit_id, new_geometry_geojson, new_lat, new_lon)
    unchanged = 0

    for d in docs:
        poly = shape(d["geometry"])
        if poly.area == 0:
            continue
        inter = poly.intersection(boundary)
        ratio = inter.area / poly.area

        if ratio < FULLY_OUT_THRESHOLD:
            to_remove_ids.append(d["unit_id"])
        elif ratio > FULLY_IN_THRESHOLD:
            unchanged += 1
        else:
            centroid = inter.centroid
            to_clip.append((d["unit_id"], mapping(inter), centroid.y, centroid.x))

    print(f"Removing {len(to_remove_ids)} units fully outside Rwanda")
    print(f"Clipping {len(to_clip)} units that straddle the border")
    print(f"Leaving {unchanged} units unchanged (fully inside Rwanda)")

    # --- MongoDB ---
    if to_remove_ids:
        result = db.slope_units.delete_many({"unit_id": {"$in": to_remove_ids}})
        print(f"MongoDB: deleted {result.deleted_count} slope_units docs")

    for unit_id, geom, lat, lon in to_clip:
        db.slope_units.update_one(
            {"unit_id": unit_id},
            {"$set": {"geometry": geom, "centroid_lat": lat, "centroid_lon": lon}},
        )
    print(f"MongoDB: clipped {len(to_clip)} slope_units docs")

    # --- local slope_units.gpkg (used by the live pipeline) ---
    if gpkg_path.exists():
        gdf = gpd.read_file(gpkg_path)
        clip_map = {uid: (geom, lat, lon) for uid, geom, lat, lon in to_clip}

        gdf = gdf[~gdf["unit_id"].isin(to_remove_ids)].copy()

        def _apply_clip(row):
            if row["unit_id"] in clip_map:
                geom, lat, lon = clip_map[row["unit_id"]]
                row["geometry"] = shape(geom)
                row["centroid_lat"] = lat
                row["centroid_lon"] = lon
            return row

        gdf = gdf.apply(_apply_clip, axis=1)
        gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs="EPSG:4326")
        gdf.to_file(gpkg_path, driver="GPKG")
        print(f"Local slope_units.gpkg: {len(gdf)} units remain (was {len(docs)})")
    else:
        print(f"WARNING: {gpkg_path} not found locally — MongoDB updated only")

    print("Done.")


if __name__ == "__main__":
    sys.exit(main())
