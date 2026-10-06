'''
what the file does?
This module provides database engine creation, connection pooling, and session management for the application using SQLAlchemy.

Classes:
    None (Database connection and session factory module)

Methods:
    get_db: Generator function providing a transactional database session with guaranteed closure upon completion.
'''
from collections.abc import Generator
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import settings

pool_options = {"pool_size": 2, "max_overflow": 2, "pool_recycle": 300} if os.getenv("VERCEL") == "1" and not settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    **pool_options,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
