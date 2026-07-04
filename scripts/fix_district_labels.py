"""
scripts/fix_district_labels.py

Assigns district labels to slope units in MongoDB using nearest-centroid
assignment across the four Northern Province districts.

Run once after load step:
    python scripts/fix_district_labels.py
"""
import asyncio
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.database import get_db

DISTRICT_CENTROIDS = {
    "Musanze": (-1.4996, 29.6346),
    "Burera":  (-1.3990, 29.8435),
    "Gakenke": (-1.6995, 29.7855),
    "Gicumbi": (-1.5750, 30.0600),
}


def nearest_district(lat: float, lon: float) -> str:
    best, best_d = "Musanze", float("inf")
    for name, (clat, clon) in DISTRICT_CENTROIDS.items():
        d = math.sqrt((lat - clat) ** 2 + (lon - clon) ** 2)
        if d < best_d:
            best, best_d = name, d
    return best


async def main():
    db = get_db()
    units = await db.slope_units.find({}, {"unit_id": 1, "centroid_lat": 1, "centroid_lon": 1}).to_list(length=10000)
    print(f"Updating {len(units)} slope units…")

    counts = {d: 0 for d in DISTRICT_CENTROIDS}
    for u in units:
        lat = u.get("centroid_lat")
        lon = u.get("centroid_lon")
        if lat is None or lon is None:
            continue
        district = nearest_district(lat, lon)
        counts[district] += 1
        await db.slope_units.update_one(
            {"unit_id": u["unit_id"]},
            {"$set": {"district": district}}
        )

    # Also update predictions to carry the district label
    print("Updating predictions with district labels…")
    units_refreshed = await db.slope_units.find({}, {"unit_id": 1, "district": 1}).to_list(length=10000)
    uid_to_district = {u["unit_id"]: u["district"] for u in units_refreshed}

    pred_cursor = db.predictions.find({}, {"_id": 1, "slope_unit_id": 1})
    updated = 0
    async for pred in pred_cursor:
        district = uid_to_district.get(pred["slope_unit_id"], "Unknown")
        await db.predictions.update_one(
            {"_id": pred["_id"]},
            {"$set": {"district": district}}
        )
        updated += 1

    print(f"\nDone.")
    print(f"  District assignment: {counts}")
    print(f"  Predictions updated: {updated}")


if __name__ == "__main__":
    asyncio.run(main())
