'''
This file defines the Inventory model for the application. The Inventory model represents an inventory change record in the database and includes fields such as id, product_id, change_quantity, reason, reference_type, reference_id, resulting_balance, created_by, and created_at. The model uses SQLAlchemy's ORM features to map the class to the inventory table in the database.
class: Inventory - A SQLAlchemy model representing an inventory change record in the database, with fields for id, product_id, change_quantity, reason, reference_type, reference_id, resulting_balance, created_by, and created_at.
'''
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .product import Product

class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    product_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )

    change_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    reason: Mapped[str] = mapped_column(
        Enum(
            "restock",
            "order_fulfilled",
            "order_cancelled",
            "manual_adjustment",
            "return",
            name="inventory_change_reason",
        ),
        nullable=False,
    )

    reference_type: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    reference_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
    )

    resulting_balance: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    product: Mapped["Product"] = relationship(
        back_populates="inventory_changes",
    )