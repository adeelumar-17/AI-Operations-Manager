'''
This module defines the FollowupRepository class, which provides methods for managing FollowupTask entities in the database. It handles creating scheduled follow-up tasks, querying due tasks for background execution, listing tasks, and transitioning execution statuses (in-progress, completed, failed).
Classes:
    FollowupRepository: A repository class that handles database CRUD operations and query logic for FollowupTask models.
Methods:
    create: Creates and commits a new scheduled follow-up task.
    get_by_id: Retrieves a follow-up task by its unique identifier.
    get_due_tasks: Fetches all pending tasks whose scheduled execution time is at or before a specified timestamp.
    list_all: Fetches all follow-up tasks ordered by scheduled execution time descending.
    mark_in_progress: Marks a task as in-progress and increments its execution attempt counter.
    mark_completed: Marks a task as completed and records the completion timestamp.
    mark_failed: Marks a task as failed and records the corresponding error message.
'''

from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID, uuid4
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, update, or_

from backend.app.db.models.followup_task import FollowupTask


class FollowupRepository:
    """Repository handling database operations for follow-up tasks."""

    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        task_type: str,
        scheduled_at: datetime,
        customer_id: Optional[UUID] = None,
        quote_id: Optional[UUID] = None,
        status: str = "pending",
    ) -> FollowupTask:
        """Create a new follow-up task."""
        task = FollowupTask(
            id=uuid4(),
            task_type=task_type,
            scheduled_at=scheduled_at,
            customer_id=customer_id,
            quote_id=quote_id,
            status=status,
            attempt_count=1 if status == "in_progress" else 0,
            started_at=datetime.now(timezone.utc) if status == "in_progress" else None,
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    def get_by_id(self, task_id: UUID | str) -> Optional[FollowupTask]:
        """Fetch a task by ID."""
        if isinstance(task_id, str):
            try:
                task_id = UUID(task_id)
            except ValueError:
                return None
        return self.session.get(FollowupTask, task_id)

    def get_due_tasks(self, as_of: Optional[datetime] = None) -> list[FollowupTask]:
        """Fetch all pending tasks scheduled at or before `as_of`."""
        now_dt = as_of or datetime.now(timezone.utc)
        # Never automatically replay work whose side effects may have happened.
        # Stale claims are failed for explicit review instead of being requeued.
        self.session.execute(update(FollowupTask).where(
            FollowupTask.status == "in_progress",
            or_(FollowupTask.started_at.is_(None), FollowupTask.started_at < now_dt - timedelta(minutes=30)),
        ).values(status="failed", last_error="Worker did not finish within 30 minutes; review recorded communications before retrying."))
        self.session.commit()
        stmt = (
            select(FollowupTask)
            .where(
                FollowupTask.status == "pending",
                FollowupTask.scheduled_at <= now_dt,
            )
            .order_by(FollowupTask.scheduled_at.asc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def list_all(self, limit: int = 50) -> list[FollowupTask]:
        """Fetch all tasks ordered by scheduled_at desc."""
        stmt = (
            select(FollowupTask)
            .order_by(FollowupTask.scheduled_at.desc())
            .options(joinedload(FollowupTask.customer))
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())

    def mark_in_progress(self, task_id: UUID | str) -> Optional[FollowupTask]:
        """Mark task as currently in progress."""
        task = self.session.scalars(update(FollowupTask).where(
            FollowupTask.id == UUID(str(task_id)), FollowupTask.status == "pending"
        ).values(status="in_progress", attempt_count=FollowupTask.attempt_count + 1, started_at=datetime.now(timezone.utc))
          .returning(FollowupTask)).one_or_none()
        self.session.commit()
        if task is None:
            return None
        self.session.refresh(task)
        return task

    def mark_completed(self, task_id: UUID | str) -> Optional[FollowupTask]:
        """Mark task as completed."""
        task = self.get_by_id(task_id)
        if not task:
            return None
        task.status = "completed"
        task.completed_at = datetime.now(timezone.utc)
        self.session.commit()
        self.session.refresh(task)
        return task

    def mark_failed(self, task_id: UUID | str, error: str) -> Optional[FollowupTask]:
        """Mark task as failed with an error message."""
        task = self.get_by_id(task_id)
        if not task:
            return None
        task.status = "failed"
        task.last_error = error
        self.session.commit()
        self.session.refresh(task)
        return task
