'''
This module defines the AgentConversation model, which represents a conversation between an agent and a customer in the system. An agent conversation is associated with a user (agent) and a customer, and has attributes such as status, start time, and last message time. The model also defines relationships to the User, Customer, AgentMessage, and AgentRun models.
Classes:
    AgentConversation: Represents a conversation between an agent and a customer in the system.
'''
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .agent_message import AgentMessage
    from .agent_run import AgentRun
    from .customer import Customer
    from .user import User


class AgentConversation(Base):
    __tablename__ = "agent_conversations"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )

    customer_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("customers.id"),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        Enum(
            "active",
            "closed",
            name="conversation_status",
        ),
        nullable=False,
        server_default="active",
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    user: Mapped["User | None"] = relationship()

    customer: Mapped["Customer | None"] = relationship()

    messages: Mapped[list["AgentMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

    runs: Mapped[list["AgentRun"]] = relationship(
        back_populates="conversation",
    )