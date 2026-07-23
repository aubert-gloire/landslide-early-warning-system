"""
APScheduler setup — daily pipeline fallback job at 23:45 UTC (01:45 Africa/Kigali).

The GitHub Actions workflow (.github/workflows/daily_pipeline.yml) is the
primary scheduler, firing at 23:00 UTC — see that file's comment for the
full reasoning on why. This job fires 45 minutes later as a backup in case
the GitHub Actions run failed to fire; pipeline.running (shared via
app.state.pipeline) plus the atomic run_date claim in pipeline.py prevent
the two from ever double-running. Deliberately kept before midnight UTC,
not just "an hour later" — run_date is computed from date.today() at
trigger time, so crossing into the next calendar day here would silently
shift which day's assessment this claims to be.

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

    # 23:45 UTC = 01:45 Africa/Kigali — 45 min after the GitHub Actions run, still same UTC day
    scheduler.add_job(_job, CronTrigger(hour=23, minute=45), id="daily_pipeline", replace_existing=True)
    logger.info("Daily pipeline fallback scheduled at 23:45 UTC (01:45 Kigali)")
