"""
APScheduler setup — daily pipeline job at 06:00 Africa/Kigali (UTC+2 = 04:00 UTC).

NOTE: On Render free tier, the process sleeps after 15 min of inactivity.
The GitHub Actions workflow (.github/workflows/daily_pipeline.yml) calls
POST /api/trigger as the primary scheduler, making this APScheduler a
fallback for local/self-hosted deployments only.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")


def setup_scheduler(pipeline):
    """Register the daily pipeline job. Call once at app startup."""

    async def _job():
        try:
            await pipeline.run_daily()
        except Exception as e:
            logger.error("Daily pipeline failed: %s", e, exc_info=True)

    # 04:00 UTC = 06:00 Africa/Kigali
    scheduler.add_job(_job, CronTrigger(hour=4, minute=0), id="daily_pipeline", replace_existing=True)
    logger.info("Daily pipeline scheduled at 04:00 UTC (06:00 Kigali)")
