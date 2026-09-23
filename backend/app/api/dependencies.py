'''
what the file does?
This module provides FastAPI request dependencies used across API routes for database session management, user identity and role extraction from request headers, and role-based access control.

Classes:
    None (FastAPI dependency definitions)

Methods:
    get_db: Provides a transactional SQLAlchemy database session per request and ensures cleanup.
    get_current_user: Extracts authenticated user info (ID and role) from custom request headers.
    require_role: Higher-order dependency factory that enforces allowed user roles for protected endpoints.
'''

from typing import Generator, Optional
from fastapi import Depends, Header, HTTPException, status
from uuid import UUID
from sqlalchemy.orm import Session

from backend.app.db.database import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Provide a transactional database session for each request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    x_user_id: Optional[str] = Header(None, alias="X-User-Id", description="User ID"),
    x_user_role: Optional[str] = Header("operator", alias="X-User-Role", description="User role (admin, manager, operator)"),
    db: Session = Depends(get_db),
) -> dict:
    """Demo identity only: validate the ID and derive roles from the database.

    X-User-Id is intentionally not authentication. X-User-Role is accepted for
    compatibility but never trusted for authorization.
    """
    from backend.app.db.models.user import User
    try:
        user = db.get(User, UUID(x_user_id or ""))
    except (ValueError, TypeError):
        user = None
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Provide X-User-Id for an active demo user.")
    identity = {"user_id": str(user.id), "role": user.role}
    db.rollback()  # release the read transaction before any long-running agent work
    return identity


def require_role(allowed_roles: list[str]):
    """Enforce endpoint access control based on user role."""
    def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="An active authorized user is required.",
            )
        return current_user
    return role_checker
