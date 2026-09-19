'''
This module defines the ApprovalRequest model, which represents a request for approval in the system. An approval request is associated with an agent run and has attributes such as requested by, action type, action payload, reason, status, approved by, resolved at, and created at. The model also defines relationships to the AgentRun, Quote, and User models.
Classes:
    ApprovalRequest: Represents a request for approval in the system.
'''

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .agent_run import AgentRun
    from .quote import Quote
    from .user import User


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

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

    requested_by: Mapped[str] = mapped_column(
        String,
        nullable=False,
        server_default="agent",
    )

    action_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    action_payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        Enum(
            "pending",
            "approved",
            "rejected",
            "expired",
            name="approval_status",
        ),
        nullable=False,
        server_default="pending",
    )

    approved_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    run: Mapped["AgentRun | None"] = relationship(
        back_populates="approval_requests"
    )

    approved_by_user: Mapped["User | None"] = relationship(
        foreign_keys=[approved_by]
    )

    quotes: Mapped[list["Quote"]] = relationship(
        back_populates="approval"
    )