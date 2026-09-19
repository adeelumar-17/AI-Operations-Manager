"""Approval schemas for human-in-the-loop workflows."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ApprovalDecisionRequest(BaseModel):
    comment: str = Field("", description="Optional comment or notes explaining the decision")
    approved_by: Optional[str] = Field(None, description="User ID of the approving manager")


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    action_type: str
    action_payload: dict[str, Any]
    reason: str
    status: str
    requested_by: str
    approved_by: Optional[UUID] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
