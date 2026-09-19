'''
what the file does?
This module provides database engine creation, connection pooling, and session management for the application using SQLAlchemy.

Classes:
    None (Database connection and session factory module)

Methods:
    get_db: Generator function providing a transactional database session with guaranteed closure upon completion.
'''
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
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