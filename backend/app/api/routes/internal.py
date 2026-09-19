'''
What the file does?
Exposes a POST /internal/run-followups endpoint used by EventBridge Scheduler
to trigger the due-followup sweep on Lambda (where APScheduler cannot run as a
persistent background process). The endpoint is protected by a shared secret
header (X-Scheduler-Secret) so it cannot be hit by arbitrary callers.

Classes:
    None (FastAPI router module)

Methods:
    trigger_followups: Validates the scheduler secret, then calls
        process_due_followups() and returns how many tasks were processed.
'''


import logging
from fastapi import APIRouter, Header, HTTPException, status

from backend.app.scheduler.jobs import process_due_followups
from backend.app.core.config import settings
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["Internal"])




@router.post("/run-followups", status_code=200)
def trigger_followups(
    x_scheduler_secret: str = Header(default="", alias="X-Scheduler-Secret"),
) -> dict:
    """EventBridge-triggered endpoint that runs the due-followup sweep.

    Requires the ``X-Scheduler-Secret`` header to match the ``SCHEDULER_SECRET``
    environment variable. Returns the number of tasks processed.
    """
    if not settings.SCHEDULER_SECRET or x_scheduler_secret != settings.SCHEDULER_SECRET:
        logger.warning("Rejected /internal/run-followups — bad or missing secret.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing scheduler secret.",
        )

    logger.info("EventBridge trigger received — running process_due_followups().")
    processed = process_due_followups()
    return {"status": "ok", "tasks_processed": processed}
