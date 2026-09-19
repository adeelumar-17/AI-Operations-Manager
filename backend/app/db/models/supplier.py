'''
This file defines the Supplier model for the application. The Supplier model represents a supplier entity in the database and includes fields such as id, name, contact_email, phone, address, and created_at. The model uses SQLAlchemy's ORM features to map the class to the suppliers table in the database.
class: Supplier - A SQLAlchemy model representing a supplier entity in the database, with fields for id, name, contact_email, phone, address, and created_at.
'''

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .product import Product

class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    contact_email: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    address: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    products: Mapped[list["Product"]] = relationship(
    back_populates="supplier",
    )