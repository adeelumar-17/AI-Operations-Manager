'''
This module defines the AgentMessage model, which represents a message in an agent conversation. An agent message is associated with a conversation and has attributes such as role, content, and creation timestamp. The model also defines a relationship to the AgentConversation model.
Classes:
    AgentMessage: Represents a message in an agent conversation.
'''
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .agent_conversation import AgentConversation


class AgentMessage(Base):
    __tablename__ = "agent_messages"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    conversation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "agent_conversations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        Enum(
            "user",
            "assistant",
            "tool",
            "system",
            name="message_role",
        ),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    conversation: Mapped["AgentConversation"] = relationship(
        back_populates="messages"
    )