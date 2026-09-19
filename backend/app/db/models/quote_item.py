'''
This module defines the QuoteItem model, which represents an item in a quote. Each quote item is associated with a specific product and belongs to a quote. It includes attributes for quantity, unit price, and line total, along with relationships to the Quote and Product models.
Classes:
    - QuoteItem: Represents an item in a quote, with attributes for product association, quantity, unit price, line total, and relationships to the Quote and Product models.
'''
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .product import Product
    from .quote import Quote


class QuoteItem(Base):
    __tablename__ = "quote_items"

    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="ck_quote_items_quantity_positive",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    quote_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("quotes.id", ondelete="CASCADE"),
        nullable=False,
    )

    product_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("products.id"),
        nullable=False,
    )

    quantity: Mapped[int] = mapped_column(
        # Integer is intentionally used below; this comment is only explanatory.
        # The actual type is declared in the next import/update.
        # 
        # quantity represents whole units.
        Integer,
        nullable=False,
    )

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    line_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    quote: Mapped["Quote"] = relationship(
        back_populates="items",
    )

    product: Mapped["Product"] = relationship()