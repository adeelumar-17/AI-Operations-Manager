'''
This module defines the AgentRun model, which represents a run of an agent in the system. An agent run is associated with a conversation and has attributes such as request ID, intent, status, start time, completion time, and error message. The model also defines relationships to the AgentConversation, ApprovalRequest, and AuditLog models.
Classes:
    AgentRun: Represents a run of an agent in the system.
'''
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .agent_conversation import AgentConversation
    from .approval_request import ApprovalRequest
    from .audit_log import AuditLog


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    conversation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agent_conversations.id"),
        nullable=True,
    )

    request_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    intent: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        Enum(
            "running",
            "waiting_approval",
            "completed",
            "failed",
            name="run_status",
        ),
        nullable=False,
        server_default="running",
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    conversation: Mapped["AgentConversation | None"] = relationship(
        back_populates="runs"
    )

    approval_requests: Mapped[list["ApprovalRequest"]] = relationship(
        back_populates="run"
    )

    audit_logs: Mapped[list["AuditLog"]] = relationship(
        back_populates="run"
    )