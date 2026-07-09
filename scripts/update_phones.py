import asyncio, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")
from motor.motor_asyncio import AsyncIOMotorClient

async def run():
    client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
    db = client[os.getenv("MONGODB_DB_NAME", "landslide_ews")]

    # Drop unique phone index so we can share one number across demo recipients
    try:
        await db.recipients.drop_index("phone_1")
        print("Dropped unique phone index")
    except Exception as e:
        print(f"Index drop skipped: {e}")

    placeholders = ["+250788000002", "+250788000003", "+250788000004"]
    for phone in placeholders:
        r = await db.recipients.update_one(
            {"phone": phone},
            {"$set": {"phone": "+250788268061"}}
        )
        print(f"  {phone} -> updated={r.modified_count}")

    active = await db.recipients.find({"active": True}).to_list(length=100)
    print(f"\nAll active recipients ({len(active)}):")
    for a in active:
        print(f"  {a['name']} | {a['phone']} | {a['district']}")
    client.close()

asyncio.run(run())
