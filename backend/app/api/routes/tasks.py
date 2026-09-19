'''
This module defines the API routes for scheduled follow-up operations and background task management. It provides endpoints for listing scheduled tasks, queueing new follow-ups, and triggering immediate execution of due background tasks.
Classes:
    None (FastAPI router module).
Methods:
    list_tasks: GET endpoint returning all queued, in-progress, or completed follow-up tasks.
    create_task: POST endpoint to schedule a new follow-up task for a customer or quote.
    trigger_due_tasks: POST endpoint that manually triggers the execution of all currently due background follow-up tasks.
'''

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_db, get_current_user
from backend.app.schemas.task import CreateTaskRequest, TaskResponse
from backend.app.db.repositories.followup_repository import FollowupRepository
from backend.app.scheduler.jobs import process_due_followups

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("", response_model=list[TaskResponse])
def list_tasks(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List follow-up tasks, with customer names if available."""
    repo = FollowupRepository(db)
    tasks = repo.list_all()
    results = []
    for t in tasks:
        results.append(
            TaskResponse(
                id=t.id,
                task_type=t.task_type,
                scheduled_at=t.scheduled_at,
                status=t.status,
                customer_id=t.customer_id,
                customer_name=t.customer.name if t.customer else None,
                quote_id=t.quote_id,
                attempt_count=t.attempt_count,
                last_error=t.last_error,
                completed_at=t.completed_at,
                created_at=t.created_at,
            )
        )
    return results


@router.post("", response_model=TaskResponse)
def create_task(
    req: CreateTaskRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new follow-up task scheduled for a future time."""
    repo = FollowupRepository(db)

    cust_id = None
    if req.customer_id:
        try:
            cust_id = UUID(str(req.customer_id))
        except ValueError:
            from backend.app.db.models.customer import Customer
            first_c = db.query(Customer).first()
            if first_c:
                cust_id = first_c.id

    quote_id = None
    if req.quote_id:
        try:
            quote_id = UUID(str(req.quote_id))
        except ValueError:
            pass

    task = repo.create(
        task_type=req.task_type,
        scheduled_at=req.scheduled_at,
        customer_id=cust_id,
        quote_id=quote_id,
    )
    return TaskResponse(
        id=task.id,
        task_type=task.task_type,
        scheduled_at=task.scheduled_at,
        status=task.status,
        customer_id=task.customer_id,
        customer_name=task.customer.name if task.customer else None,
        quote_id=task.quote_id,
        attempt_count=task.attempt_count,
        last_error=task.last_error,
        completed_at=task.completed_at,
        created_at=task.created_at,
    )


@router.post("/trigger")
def trigger_due_tasks(
    current_user: dict = Depends(get_current_user),
):
    """Manually trigger immediate execution of all currently due follow-up tasks."""
    processed = process_due_followups()
    return {"message": f"Processed {processed} due follow-up tasks."}
