'''
This module defines the Order model, which represents an order in the system. An order is associated with a customer and can have multiple items. It also has various attributes such as status, subtotal, total, and timestamps for creation and updates.
Classes: 
    - Order: Represents an order in the system, with attributes for customer association, status, subtotal, total, and timestamps. It also defines relationships to the Customer, Quote, and OrderItem models.
'''

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .customer import Customer
    from .order_item import OrderItem
    from .quote import Quote
    from .invoice import Invoice


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    order_number: Mapped[str] = mapped_column(
        String,
        unique=True,
        nullable=False,
    )

    customer_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("customers.id"),
        nullable=False,
    )

    quote_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("quotes.id"),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        Enum(
            "pending",
            "processing",
            "shipped",
            "delivered",
            "cancelled",
            name="order_status",
        ),
        nullable=False,
        server_default="pending",
    )

    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    shipped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    customer: Mapped["Customer"] = relationship(
        back_populates="orders",
    )

    quote: Mapped["Quote | None"] = relationship(
        back_populates="orders",
    )

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )

    invoices: Mapped[list["Invoice"]] = relationship(
        back_populates="order"
    )