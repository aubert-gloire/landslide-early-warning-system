import asyncio, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")
from motor.motor_asyncio import AsyncIOMotorClient

async def run():
    client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
    db = client[os.getenv("MONGODB_DB_NAME", "landslide_ews")]

    latest = await db.predictions.find_one(sort=[("date", -1)])
    if not latest:
        print("No predictions in DB")
        client.close()
        return

    latest_date = latest["date"]
    count = await db.predictions.count_documents({"date": latest_date})
    total = await db.predictions.count_documents({})
    print(f"Latest prediction date : {latest_date}")
    print(f"Units on that date     : {count}")
    print(f"Total predictions in DB: {total}")

    # Show risk distribution for latest date
    pipeline = [
        {"$match": {"date": latest_date}},
        {"$bucket": {
            "groupBy": "$risk_probability",
            "boundaries": [0, 0.05, 0.40, 0.60, 0.80, 1.01],
            "default": "other",
            "output": {"count": {"$sum": 1}}
        }}
    ]
    buckets = await db.predictions.aggregate(pipeline).to_list(length=10)
    print("\nRisk distribution:")
    labels = ["<5% (no alert)", "5-40% (low)", "40-60% (medium)", "60-80% (high)", "80%+ (critical)"]
    for b, label in zip(buckets, labels):
        print(f"  {label}: {b['count']} units")

    client.close()

asyncio.run(run())
