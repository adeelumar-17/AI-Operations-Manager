'''
This module defines the Communication model, which represents a communication record in the system. A communication is associated with a customer and can be of various types (email, call, note, sms) and directions (outbound, inbound). It has attributes such as subject, body, related entity type and ID, status, sent timestamp, and timestamps for creation. The model also defines a relationship to the Customer model.
Classes:
    Communication: Represents a communication record in the system.
'''

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .customer import Customer


class Communication(Base):
    __tablename__ = "communications"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    customer_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("customers.id"),
        nullable=False,
    )

    type: Mapped[str] = mapped_column(
        Enum(
            "email",
            "call",
            "note",
            "sms",
            name="communication_type",
        ),
        nullable=False,
    )

    direction: Mapped[str] = mapped_column(
        Enum(
            "outbound",
            "inbound",
            name="communication_direction",
        ),
        nullable=False,
        server_default="outbound",
    )

    subject: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    body: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    related_entity_type: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    related_entity_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        Enum(
            "sent",
            "failed",
            "pending",
            name="communication_status",
        ),
        nullable=False,
        server_default="pending",
    )

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    customer: Mapped["Customer"] = relationship(
        back_populates="communications"
    )