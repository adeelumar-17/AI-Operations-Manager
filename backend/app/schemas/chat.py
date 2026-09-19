"""Chat schemas for agent communication."""

from typing import Any, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="User message or prompt for the operations agent")
    conversation_id: Optional[str] = Field(None, description="Optional ongoing conversation ID")
    thread_id: Optional[str] = Field(None, description="Optional thread ID for checkpointer persistence")
    conversation_history: Optional[list[dict[str, Any]]] = Field(
        None,
        description="Optional prior session messages [{role: 'user'/'assistant', content: str}] for short-term memory",
    )


class ChatResponse(BaseModel):
    response: str
    workflow: Optional[str] = None
    intent: Optional[str] = None
    entities: dict[str, Any] = Field(default_factory=dict)
    approval_required: bool = False
    approval_id: Optional[str] = None
    approval_decision: Optional[str] = None
    thread_id: Optional[str] = None
    request_id: Optional[str] = None
    error: Optional[str] = None
