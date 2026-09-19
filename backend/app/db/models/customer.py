'''
This file defines the User model for the application, which represents a user in the system. The User model includes fields for storing user information such as username, email, hashed password, and timestamps for creation and updates. It also establishes relationships with other models, such as the Agent model.

class: Customer - A SQLAlchemy model representing a customer in the system, with fields for name, email, phone, company name, address, notes, and timestamps for creation and updates. 
'''

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .quote import Quote
    from .order import Order
    from .invoice import Invoice  
    from .communication import Communication


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    email: Mapped[str | None] = mapped_column(
        String,
        unique=True,
        nullable=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    company_name: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
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

    quotes: Mapped[list["Quote"]] = relationship(
    back_populates="customer",
    )

    orders: Mapped[list["Order"]] = relationship(
        back_populates="customer", 
    )

    invoices: Mapped[list["Invoice"]] = relationship(
    back_populates="customer"
    )

    communications: Mapped[list["Communication"]] = relationship(
        back_populates="customer"
    )