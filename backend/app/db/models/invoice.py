'''
This module defines the Invoice model, which represents an invoice in the system. An invoice is associated with a customer and can be linked to an order. It has various attributes such as amount, issue date, due date, status, and timestamps for creation and updates.
Classes: 
    - Invoice: Represents an invoice in the system, with attributes for customer association, order association, amount, issue date, due date, status, paid date, and timestamps. It also defines relationships to the Customer, Order, and Payment models.
'''

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .customer import Customer
    from .order import Order
    from .payment import Payment


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    invoice_id: Mapped[str] = mapped_column(
        String,
        unique=True,
        nullable=False,
    )

    customer_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("customers.id"),
        nullable=False,
    )

    order_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("orders.id"),
        nullable=True,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    issue_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    due_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        Enum(
            "draft",
            "sent",
            "partially_paid",
            "paid",
            "overdue",
            "cancelled",
            name="invoice_status",
        ),
        nullable=False,
        server_default="draft",
    )

    paid_date: Mapped[date | None] = mapped_column(
        Date,
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
        back_populates="invoices"
    )

    order: Mapped["Order | None"] = relationship(
        back_populates="invoices"
    )

    payments: Mapped[list["Payment"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
    )