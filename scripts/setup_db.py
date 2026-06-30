"""
One-time setup script — Sprint 1 data layer bootstrap.

Run order:
  1. python scripts/setup_db.py dem       — download COP30 DEM + derive terrain
  2. python scripts/setup_db.py units     — generate slope units from DEM
  3. python scripts/setup_db.py ndvi      — pull Sentinel-2 NDVI via GEE
  4. python scripts/setup_db.py soil      — download ISRIC soil raster
  5. python scripts/setup_db.py chirps    — download historical CHIRPS 2000-2024
  6. python scripts/setup_db.py load      — load all static data into MongoDB
  7. python scripts/setup_db.py all       — run steps 1-6 in sequence

Usage:
  python scripts/setup_db.py <step>
"""

import asyncio
import logging
import sys
from pathlib import Path

# Resolve repo root
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def step_dem():
    from ml.pipeline.dem import DEMProcessor
    from ml.pipeline.slope_units import SlopeUnitGenerator
    import os
    api_key = os.getenv("OPENTOPO_API_KEY", "")
    if not api_key:
        logger.warning("OPENTOPO_API_KEY not set — DEM download will fail. Set it in .env")
    processor = DEMProcessor(ROOT / "data/raw", ROOT / "data/processed", api_key)
    processor.download()
    processor.derive_terrain_features()
    gen = SlopeUnitGenerator(ROOT / "data/raw", ROOT / "data/processed")
    gdf = gen.load()
    processor.extract_per_unit(gdf)
    logger.info("DEM step complete")


def step_units():
    from ml.pipeline.slope_units import SlopeUnitGenerator
    gen = SlopeUnitGenerator(ROOT / "data/raw", ROOT / "data/processed")
    gdf = gen.generate()
    logger.info("Generated %d slope units", len(gdf))


def step_ndvi():
    from ml.pipeline.ndvi import NDVIExtractor
    from ml.pipeline.slope_units import SlopeUnitGenerator
    gen = SlopeUnitGenerator(ROOT / "data/raw", ROOT / "data/processed")
    gdf = gen.load()
    extractor = NDVIExtractor(ROOT / "data/processed")
    extractor.extract_annual_ndvi(gdf, year=2023)
    logger.info("NDVI extraction complete")


def step_soil():
    from ml.pipeline.soil import SoilDownloader
    from ml.pipeline.slope_units import SlopeUnitGenerator
    gen = SlopeUnitGenerator(ROOT / "data/raw", ROOT / "data/processed")
    gdf = gen.load()
    downloader = SoilDownloader(ROOT / "data/raw", ROOT / "data/processed")
    downloader.download()
    downloader.extract_per_unit(gdf)
    logger.info("Soil step complete")


def step_chirps():
    from datetime import date
    from ml.pipeline.chirps import CHIRPSDownloader
    from ml.pipeline.slope_units import SlopeUnitGenerator
    gen = SlopeUnitGenerator(ROOT / "data/raw", ROOT / "data/processed")
    gdf = gen.load()
    downloader = CHIRPSDownloader(ROOT / "data/raw", ROOT / "data/processed")
    downloader.build_historical_series(gdf, start=date(2010, 1, 1), end=date(2024, 12, 31))
    logger.info("CHIRPS historical series complete")


async def step_load():
    """Load all static data (slope units + terrain) into MongoDB."""
    import geopandas as gpd
    import json
    from motor.motor_asyncio import AsyncIOMotorClient
    import os

    gdf = gpd.read_file(ROOT / "data/processed/slope_units.gpkg")
    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGODB_DB_NAME", "landslide_ews")
    client = AsyncIOMotorClient(uri)
    db = client[db_name]

    # Terrain per unit
    terrain_path = ROOT / "data/processed/terrain_per_unit.parquet"
    import pandas as pd
    terrain_df = pd.read_parquet(terrain_path) if terrain_path.exists() else pd.DataFrame()
    ndvi_files = sorted((ROOT / "data/processed").glob("ndvi_*.parquet"), reverse=True)
    ndvi_df = pd.read_parquet(ndvi_files[0]) if ndvi_files else pd.DataFrame()
    soil_path = ROOT / "data/processed/soil_per_unit.parquet"
    soil_df = pd.read_parquet(soil_path) if soil_path.exists() else pd.DataFrame()

    docs = []
    for _, row in gdf.iterrows():
        unit_id = int(row["unit_id"])
        geom = json.loads(row.geometry.to_json()) if hasattr(row.geometry, "to_json") else {}

        doc = {
            "unit_id": unit_id,
            "district": str(row.get("district", "")),
            "geometry": geom,
            "centroid_lat": float(row.get("centroid_lat", 0)),
            "centroid_lon": float(row.get("centroid_lon", 0)),
        }

        if not terrain_df.empty and unit_id in terrain_df["unit_id"].values:
            tr = terrain_df[terrain_df["unit_id"] == unit_id].iloc[0]
            for col in ["slope_angle", "aspect", "twi", "drainage_density"]:
                doc[col] = float(tr[col]) if col in tr else None

        if not ndvi_df.empty and unit_id in ndvi_df["unit_id"].values:
            doc["ndvi"] = float(ndvi_df[ndvi_df["unit_id"] == unit_id]["ndvi"].iloc[0])

        if not soil_df.empty and unit_id in soil_df["unit_id"].values:
            doc["soil_class"] = int(soil_df[soil_df["unit_id"] == unit_id]["soil_class"].iloc[0])
        else:
            doc["soil_class"] = 4

        docs.append(doc)

    if docs:
        await db.slope_units.delete_many({})
        await db.slope_units.insert_many(docs)
        logger.info("Loaded %d slope units into MongoDB", len(docs))

    client.close()


def main():
    step = sys.argv[1] if len(sys.argv) > 1 else "help"
    steps = {
        "dem": step_dem,
        "units": step_units,
        "ndvi": step_ndvi,
        "soil": step_soil,
        "chirps": step_chirps,
    }
    if step == "load":
        asyncio.run(step_load())
    elif step == "all":
        for name, fn in steps.items():
            logger.info("=== Running step: %s ===", name)
            fn()
        asyncio.run(step_load())
    elif step in steps:
        steps[step]()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
