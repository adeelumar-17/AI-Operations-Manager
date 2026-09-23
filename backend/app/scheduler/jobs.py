"""Claim due tasks once and verify follow-up records before completion."""
import logging
from backend.app.db.database import SessionLocal
from backend.app.db.repositories.followup_repository import FollowupRepository
from backend.app.services.execution_service import require_logged_communication
from agents.agent_service import run_agent

logger = logging.getLogger(__name__)


def process_due_followups() -> int:
    processed = 0
    try:
        with SessionLocal() as db:
            task_ids = [task.id for task in FollowupRepository(db).get_due_tasks()]
        for task_id in task_ids:
            try:
                with SessionLocal() as db:
                    task = FollowupRepository(db).mark_in_progress(task_id)
                    if task is None:
                        continue  # another worker already claimed it
                    customer_id, quote_id, task_type = task.customer_id, task.quote_id, task.task_type
                prompt = (f'Scheduled follow-up now due: {task_type}. Customer UUID: {customer_id}. '
                          f'Quote UUID: {quote_id or "none"}. Check the referenced business facts and log an outbound '
                          'note or email draft. Link the quote UUID when supplied. Do not schedule another task and do not claim email delivery.')
                result = run_agent(user_input=prompt)
                with SessionLocal() as db:
                    require_logged_communication(result, db, customer_id, 'quote' if quote_id else None, quote_id)
                    FollowupRepository(db).mark_completed(task_id)
                processed += 1
            except Exception as exc:
                logger.exception('Follow-up task %s failed', task_id)
                try:
                    with SessionLocal() as db:
                        FollowupRepository(db).mark_failed(task_id, str(exc))
                except Exception:
                    logger.exception('Could not mark follow-up task %s failed; manual review needed', task_id)
    except Exception:
        logger.exception('Due-task sweep failed')
    return processed
