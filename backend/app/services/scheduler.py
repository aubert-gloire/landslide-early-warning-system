"""
APScheduler setup — daily pipeline fallback job at 16:00 UTC (18:00 Africa/Kigali).

The GitHub Actions workflow (.github/workflows/daily_pipeline.yml) is the
primary scheduler, firing at 15:00 UTC — after GPM IMERG's ~14h latency
window so rainfall data is actually available (see that file's comment for
the full reasoning). This job fires an hour later as a backup in case the
GitHub Actions run failed to fire; pipeline.running (shared via
app.state.pipeline) prevents the two from ever running concurrently.

NOTE: Render's "starter" plan does not sleep on inactivity, so on Render
this job genuinely runs daily alongside GitHub Actions, not just locally.
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

    # 16:00 UTC = 18:00 Africa/Kigali — one hour after the GitHub Actions run
    scheduler.add_job(_job, CronTrigger(hour=16, minute=0), id="daily_pipeline", replace_existing=True)
    logger.info("Daily pipeline fallback scheduled at 16:00 UTC (18:00 Kigali)")
