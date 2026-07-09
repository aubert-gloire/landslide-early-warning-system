"""Remove duplicate predictions — keeps only the most recent per (unit_id, date)."""
import asyncio, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")
from motor.motor_asyncio import AsyncIOMotorClient

async def run():
    client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
    db = client[os.getenv("MONGODB_DB_NAME", "landslide_ews")]

    total_before = await db.predictions.count_documents({})
    print(f"Predictions before: {total_before}")

    # Find all distinct (slope_unit_id, date) combos with more than one doc
    pipeline = [
        {"$group": {"_id": {"uid": "$slope_unit_id", "date": "$date"}, "ids": {"$push": "$_id"}, "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}},
    ]
    duplicates = await db.predictions.aggregate(pipeline).to_list(length=100000)
    print(f"Duplicate groups found: {len(duplicates)}")

    deleted = 0
    for group in duplicates:
        ids = group["ids"]
        # Keep the last inserted (_id is ObjectId, higher = newer), delete the rest
        ids_sorted = sorted(ids, key=lambda x: str(x))
        to_delete = ids_sorted[:-1]
        result = await db.predictions.delete_many({"_id": {"$in": to_delete}})
        deleted += result.deleted_count

    total_after = await db.predictions.count_documents({})
    print(f"Deleted {deleted} duplicates — predictions after: {total_after}")

    # Show what today looks like now
    from datetime import date
    today = date.today().isoformat()
    today_count = await db.predictions.count_documents({"date": today})
    top = await db.predictions.find_one({"date": today}, sort=[("risk_probability", -1)])
    print(f"Today ({today}): {today_count} predictions, highest risk: {top['risk_probability']*100:.1f}% unit={top['slope_unit_id']}" if top else f"Today: {today_count} predictions")
    client.close()

asyncio.run(run())
