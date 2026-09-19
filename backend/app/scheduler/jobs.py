'''
This module defines the background job worker routines executed periodically by APScheduler. It processes due follow-up tasks by synthesizing context-aware agent prompts, invoking the operations agent to execute the follow-ups, and recording completion or failure results.
Classes:
    None (Background job execution module).
Methods:
    process_due_followups: Queries due follow-up tasks from the database and runs the agent to execute automated collections reminders and quote follow-ups.
'''

import logging
from datetime import datetime, timezone
from typing import Optional

from backend.app.db.database import SessionLocal
from backend.app.db.repositories.followup_repository import FollowupRepository
from agents.agent_service import run_agent

logger = logging.getLogger(__name__)


def process_due_followups() -> int:
    """Check for due follow-up tasks and execute them via the operations agent.

    Returns the number of tasks processed.
    """
    logger.info("Running process_due_followups job...")
    processed_count = 0

    try:
        with SessionLocal() as db:
            repo = FollowupRepository(db)
            due_tasks = repo.get_due_tasks()

            if not due_tasks:
                logger.debug("No due follow-up tasks found.")
                return 0

            logger.info(f"Found {len(due_tasks)} due follow-up task(s). Processing...")

            for task in due_tasks:
                task_id = task.id
                repo.mark_in_progress(task_id)

                # Formulate synthesized agent prompt
                customer_info = f"customer {task.customer_id}" if task.customer_id else "customer"
                quote_info = f"quote {task.quote_id}" if task.quote_id else ""
                prompt = (
                    f"Scheduled automated follow-up: Check status and log follow-up communication "
                    f"for {customer_info} regarding {task.task_type} {quote_info}."
                )

                try:
                    res = run_agent(user_input=prompt)
                    repo.mark_completed(task_id)
                    processed_count += 1
                    logger.info(
                        f"Completed follow-up task {task_id}: {res.get('workflow')} - {res.get('response')[:80]}..."
                    )
                except Exception as exc:
                    error_msg = str(exc)
                    repo.mark_failed(task_id, error=error_msg)
                    logger.error(f"Failed executing follow-up task {task_id}: {error_msg}")

    except Exception as exc:
        logger.warning(f"Database unavailable or error in process_due_followups: {exc}")

    return processed_count
