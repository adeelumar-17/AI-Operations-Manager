"""Task schemas for scheduled operations."""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class CreateTaskRequest(BaseModel):
    task_type: str = Field(..., description="Type of follow-up task, e.g. 'quote_followup' or 'overdue_invoice'")
    scheduled_at: datetime = Field(..., description="Target execution timestamp (ISO 8601)")
    customer_id: Optional[str] = Field(None, description="Target customer ID")
    quote_id: Optional[str] = Field(None, description="Target quote ID")


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_type: str
    scheduled_at: datetime
    status: str
    customer_id: Optional[UUID] = None
    customer_name: Optional[str] = None
    quote_id: Optional[UUID] = None
    attempt_count: int
    last_error: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
