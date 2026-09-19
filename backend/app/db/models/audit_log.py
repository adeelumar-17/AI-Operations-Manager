'''
This module defines the AuditLog model, which represents an audit log entry in the system. An audit log entry is associated with an agent run, a conversation, and a user, and has attributes such as node, tool, input, output, action, approval status, result, error, and timestamp. The model also defines relationships to the AgentRun, AgentConversation, and User models.
Classes:
    AuditLog: Represents an audit log entry in the system.
'''

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .agent_conversation import AgentConversation
    from .agent_run import AgentRun
    from .user import User


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agent_runs.id"),
        nullable=True,
    )

    conversation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agent_conversations.id"),
        nullable=True,
    )

    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )

    node: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    tool: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    input: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    output: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    action: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    approval_status: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    result: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    timestamp: Mapped[datetime] = mapped_column(
        "timestamp",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    run: Mapped["AgentRun | None"] = relationship(
        back_populates="audit_logs"
    )

    conversation: Mapped["AgentConversation | None"] = relationship()

    user: Mapped["User | None"] = relationship()