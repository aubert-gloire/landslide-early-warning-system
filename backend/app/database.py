from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from .config import get_settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncIOMotorClient(settings.mongodb_uri)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    settings = get_settings()
    return get_client()[settings.mongodb_db_name]


async def close_client():
    global _client
    if _client is not None:
        _client.close()
        _client = None


async def ensure_indexes():
    """Create indexes on startup — idempotent."""
    db = get_db()
    await db.slope_units.create_index("unit_id", unique=True)
    await db.rainfall_records.create_index([("slope_unit_id", 1), ("date", 1)], unique=True)
    await db.predictions.create_index([("slope_unit_id", 1), ("date", -1)])
    await db.predictions.create_index("date")
    await db.alert_records.create_index("prediction_id")
    await db.alert_records.create_index("sent_at")
    await db.recipients.create_index("phone")
    await db.recipients.create_index("district")
    # Enforces the daily-run claim at the database level, not just in-memory —
    # see services/pipeline.py's atomic claim/complete/fail flow. Without this,
    # two processes (e.g. GitHub Actions' cron + the APScheduler fallback,
    # racing across a Render restart) can both pass a plain find-then-insert
    # check before either finishes writing its result.
    await db.pipeline_runs.create_index("run_date", unique=True)
