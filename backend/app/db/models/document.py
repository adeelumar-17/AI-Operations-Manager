'''
This module defines the Document model, which represents a document in the system. A document has attributes such as title, source path, type, and creation timestamp. The model also defines a relationship to the DocumentChunk model.
Classes:
    Document: Represents a document in the system.
'''

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .document_chunk import DocumentChunk


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    source_path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    doc_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
        server_default="policy",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )