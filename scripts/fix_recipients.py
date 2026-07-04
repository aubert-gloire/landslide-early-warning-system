import asyncio, os, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

PLACEHOLDERS = ["+250788000001", "+250788000002", "+250788000003", "+250788000004"]

async def fix():
    client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
    db = client[os.getenv("MONGODB_DB_NAME", "landslide_ews")]

    r = await db.recipients.update_many(
        {"phone": {"$in": PLACEHOLDERS}},
        {"$set": {"active": False}},
    )
    print(f"Deactivated {r.modified_count} placeholder recipients")

    active = await db.recipients.find({"active": True}).to_list(length=100)
    print(f"\nActive recipients ({len(active)}):")
    for a in active:
        print(f"  {a['name']} | {a['phone']} | {a['district']}")

    client.close()

asyncio.run(fix())
