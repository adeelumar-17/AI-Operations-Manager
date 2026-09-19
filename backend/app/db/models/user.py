'''
This file defines the User model for the application, which represents a user in the system. The User model includes fields for storing user information such as username, email, hashed password, and timestamps for creation and updates. It also establishes relationships with other models, such as the Agent model.

class: User - A SQLAlchemy model representing a user in the system, with fields for email, hashed password, full name, role, active status, and timestamps for creation and updates.
'''

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    email: Mapped[str] = mapped_column(
        String,
        unique=True,
        nullable=False,
    )

    hashed_password: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    full_name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        Enum(
            "admin",
            "manager",
            "staff",
            name="user_role",
        ),
        nullable=False,
        server_default="staff",
    )

    is_active: Mapped[bool] = mapped_column(
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