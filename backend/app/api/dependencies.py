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
from fastapi import Header, HTTPException, status
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
) -> dict:
    """Extract authenticated user info from request headers."""
    return {
        "user_id": x_user_id or "anonymous-operator",
        "role": (x_user_role or "operator").lower(),
    }


def require_role(allowed_roles: list[str]):
    """Enforce endpoint access control based on user role."""
    def role_checker(current_user: dict = Header(None)) -> dict:
        user = current_user or {"role": "operator"}
        role = user.get("role", "operator")
        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: role '{role}' is not in allowed roles {allowed_roles}.",
            )
        return user
    return role_checker
