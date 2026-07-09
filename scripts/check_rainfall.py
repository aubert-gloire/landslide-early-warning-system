import asyncio, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")
from motor.motor_asyncio import AsyncIOMotorClient

async def run():
    client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
    db = client[os.getenv("MONGODB_DB_NAME", "landslide_ews")]

    total = await db.rainfall_records.count_documents({})
    print(f"Total rainfall records: {total}")

    latest   = await db.rainfall_records.find_one(sort=[("date", -1)])
    earliest = await db.rainfall_records.find_one(sort=[("date",  1)])
    print(f"Date range: {earliest['date']} to {latest['date']}")

    high = await db.rainfall_records.find_one(
        {"daily_mm": {"$gt": 0}}, sort=[("daily_mm", -1)]
    )
    print(f"Highest daily_mm: {high['daily_mm']}mm on {high['date']} unit {high['slope_unit_id']}")

    may23 = await db.rainfall_records.find_one(
        {"date": {"$gte": "2023-05-01", "$lte": "2023-05-10"}}
    )
    print(f"May 2023 sample: {may23}")

    # Find top 5 dates by avg rainfall
    pipeline = [
        {"$group": {"_id": "$date", "avg_mm": {"$avg": "$daily_mm"}, "max_mm": {"$max": "$daily_mm"}}},
        {"$sort": {"avg_mm": -1}},
        {"$limit": 5},
    ]
    top = await db.rainfall_records.aggregate(pipeline).to_list(length=5)
    print("\nTop 5 highest-rainfall dates:")
    for t in top:
        print(f"  {t['_id']}  avg={t['avg_mm']:.2f}mm  max={t['max_mm']:.2f}mm")

    client.close()

asyncio.run(run())
