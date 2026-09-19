'''
This file defines the Product model for the application. The Product model represents a product entity in the database and includes fields such as id, sku, name, description, category, unit_price, stock_quantity, reorder_threshold, supplier_id, active, created_at, and updated_at. The model uses SQLAlchemy's ORM features to map the class to the products table in the database.
class: Product - A SQLAlchemy model representing a product entity in the database, with fields for id, sku, name, description, category, unit_price, stock_quantity, reorder_threshold, supplier_id, active, created_at, and updated_at.
'''
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .inventory import Inventory
    from .supplier import Supplier

class Product(Base):
    __tablename__ = "products"

    __table_args__ = (
        CheckConstraint("unit_price >= 0", name="ck_products_unit_price_non_negative"),
        CheckConstraint("stock_quantity >= 0", name="ck_products_stock_quantity_non_negative"),
        CheckConstraint(
            "reorder_threshold >= 0",
            name="ck_products_reorder_threshold_non_negative",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    sku: Mapped[str] = mapped_column(
        String,
        unique=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    category: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    stock_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    reorder_threshold: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    supplier_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="SET NULL"),
        nullable=True,
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
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

    supplier: Mapped["Supplier | None"] = relationship(
        back_populates="products",
    )

    inventory_changes: Mapped[list["Inventory"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )