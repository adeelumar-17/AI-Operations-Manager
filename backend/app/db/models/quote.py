'''
This module defines the Quote model, which represents a quote in the system. A quote is associated with a customer and can have multiple items. It also has various attributes such as status, subtotal, discount, total, and timestamps for creation and updates.
Classes: 
    - Quote: Represents a quote in the system, with attributes for customer association, status, subtotal, discount, total, and timestamps. It also defines relationships to the Customer, User, QuoteItem, and ApprovalRequest models.
'''

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .approval_request import ApprovalRequest

if TYPE_CHECKING:
    from .approval_request import ApprovalRequest
    from .customer import Customer
    from .order import Order
    from .quote_item import QuoteItem
    from .user import User


class Quote(Base):
    __tablename__ = "quotes"

    __table_args__ = (
        CheckConstraint(
            "discount_percent BETWEEN 0 AND 100",
            name="ck_quotes_discount_percent",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    quote_number: Mapped[str] = mapped_column(
        String,
        unique=True,
        nullable=False,
    )

    customer_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("customers.id"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        Enum(
            "draft",
            "pending_approval",
            "approved",
            "rejected",
            "converted",
            "expired",
            name="quote_status",
        ),
        nullable=False,
        server_default="draft",
    )

    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        server_default=text("0"),
    )

    discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        server_default=text("0"),
    )

    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        server_default=text("0"),
    )

    total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        server_default=text("0"),
    )

    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )

    approval_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("approval_requests.id"),
        nullable=True,
    )

    expires_at: Mapped[datetime | None] = mapped_column(
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
        back_populates="quotes",
    )

    created_by_user: Mapped["User | None"] = relationship(
        foreign_keys=[created_by],
    )

    items: Mapped[list["QuoteItem"]] = relationship(
        back_populates="quote",
        cascade="all, delete-orphan",
    )

    orders: Mapped[list["Order"]] = relationship(
        back_populates="quote",
    )
    approval: Mapped["ApprovalRequest | None"] = relationship(
        back_populates="quotes"
    )