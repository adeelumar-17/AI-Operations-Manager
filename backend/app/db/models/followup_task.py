'''
This module defines the FollowupTask model, which represents a follow-up task in the system. A follow-up task is associated with a customer and/or a quote, and has a type, scheduled time, status, and other attributes. The model also defines relationships to the Customer and Quote models.
Classes:
    FollowupTask: Represents a follow-up task in the system.
'''

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .customer import Customer
    from .quote import Quote


class FollowupTask(Base):
    __tablename__ = "followup_tasks"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    task_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    customer_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("customers.id"),
        nullable=True,
    )

    quote_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("quotes.id"),
        nullable=True,
    )

    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        Enum(
            "pending",
            "in_progress",
            "completed",
            "failed",
            "cancelled",
            name="followup_task_status",
        ),
        nullable=False,
        server_default="pending",
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    customer: Mapped["Customer | None"] = relationship()

    quote: Mapped["Quote | None"] = relationship()
