"""Individual conversational follow-up creation."""
import logging
from langchain_core.tools import tool
from backend.app.db.database import SessionLocal
from backend.app.services.followup_service import create_followup

logger = logging.getLogger(__name__)


@tool
def create_followup_task(customer_id: str, scheduled_at: str, task_type: str = "manual_reminder", quote_id: str = "") -> str:
    """Schedule one future follow-up for a verified customer UUID.

    scheduled_at must be ISO 8601 including time and timezone offset. If the
    user's time or timezone is unknown, ask for it rather than assuming now.
    Resolve a customer name with search_customer before calling this tool.
    This schedules a reminder; it does not send an email.
    """
    with SessionLocal() as db:
        try:
            task = create_followup(db, task_type, scheduled_at, customer_id, quote_id or None)
            return f"Follow-up task created: {task.id}; customer: {task.customer_id}; scheduled_at: {task.scheduled_at.isoformat()}"
        except Exception as exc:
            db.rollback()
            logger.exception("Follow-up creation failed")
            return f"Error creating follow-up task: {exc}"
