'''
This module configures and manages the APScheduler background scheduler instance. It registers recurring interval jobs that process due follow-up tasks and controls the scheduler lifecycle during application startup and shutdown.
Classes:
    None (Service lifecycle configuration module).
Methods:
    start_scheduler: Initializes and starts the background job scheduler polling for due follow-up tasks.
    stop_scheduler: Safely shuts down the running background scheduler instance.
'''

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from backend.app.scheduler.jobs import process_due_followups

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def start_scheduler(interval_seconds: int = 60) -> None:
    """Start the background scheduler."""
    if not scheduler.running:
        scheduler.add_job(
            process_due_followups,
            "interval",
            seconds=interval_seconds,
            id="process_due_followups",
            replace_existing=True,
        )
        scheduler.start()
        logger.info(f"APScheduler started. Polling every {interval_seconds} seconds.")


def stop_scheduler() -> None:
    """Stop the background scheduler cleanly."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped.")
