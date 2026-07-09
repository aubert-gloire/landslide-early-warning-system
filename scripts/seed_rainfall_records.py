"""
One-time script: seed MongoDB rainfall_records with recent CHIRPS data.

Run this locally once. After it completes, Render will always use the
MongoDB cache and never need to download CHIRPS from UCSB again.

Usage:
    cd landslide-ews
    python scripts/seed_rainfall_records.py
"""

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

# Make ml/ importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import geopandas as gpd
import motor.motor_asyncio
from dotenv import load_dotenv
import os

load_dotenv("backend/.env")

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB  = os.getenv("MONGODB_DB_NAME", "landslide_ews")
DAYS_BACK   = 15  # how many days of history to seed


async def seed():
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
    db = client[MONGODB_DB]

    print("Loading slope units…")
    slope_units = gpd.read_file("data/processed/slope_units.gpkg")
    print(f"  {len(slope_units)} units loaded")

    from ml.pipeline.chirps import CHIRPSDownloader
    downloader = CHIRPSDownloader(
        raw_dir=Path("data/raw"),
        processed_dir=Path("data/processed"),
    )

    print("Clearing existing rainfall_records…")
    result = await db.rainfall_records.delete_many({})
    print(f"  Deleted {result.deleted_count} stale records")

    today = date.today()
    from pymongo import UpdateOne

    for i in range(DAYS_BACK, 0, -1):
        target = today - timedelta(days=i)
        date_str = target.isoformat()

        existing = await db.rainfall_records.count_documents({"date": date_str})
        if existing >= 300:
            print(f"  {date_str} — already in MongoDB ({existing} records), skipping")
            continue

        print(f"  {date_str} — extracting per-unit rainfall…", end=" ", flush=True)
        df = downloader.extract_per_unit_rainfall(target, slope_units)
        print(f"{len(df)} units")

        upserts = [
            UpdateOne(
                {"slope_unit_id": int(row["unit_id"]), "date": date_str},
                {"$set": {
                    "slope_unit_id": int(row["unit_id"]),
                    "date": date_str,
                    "daily_mm": 0.0 if (v := row.get("daily_mm")) is None or v != v else float(v),
                }},
                upsert=True,
            )
            for _, row in df.iterrows()
        ]
        if upserts:
            await db.rainfall_records.bulk_write(upserts, ordered=False)

    total = await db.rainfall_records.count_documents({})
    print(f"\nDone — {total} total rainfall_records in MongoDB")
    print("Render will now use cache on every pipeline run.")
    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
