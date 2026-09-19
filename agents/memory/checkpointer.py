'''
what the file does?
This module configures the state checkpointer for LangGraph execution, providing persistent PostgreSQL checkpointing (PostgresSaver) for interrupted agent runs and human-in-the-loop approvals, with an in-memory fallback.

Classes:
    None (State checkpointer configuration module)

Methods:
    get_checkpointer: Returns a singleton checkpointer instance (PostgresSaver or in-memory MemorySaver).
    reset_checkpointer_for_testing: Closes any active connection pool and resets the checkpointer to a clean MemorySaver.
    close_checkpointer: Closes the underlying connection pool if open.
'''

from typing import Optional, Any
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

try:
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool
    from langgraph.checkpoint.postgres import PostgresSaver
    POSTGRES_SAVER_AVAILABLE = True
except ImportError:
    POSTGRES_SAVER_AVAILABLE = False

# Singleton connection pool and checkpointer
_checkpointer_instance: Optional[BaseCheckpointSaver] = None
_pool: Optional[Any] = None


def get_checkpointer(
    db_url: Optional[str] = None,
    force_memory: bool = False,
) -> BaseCheckpointSaver:
    """Return a checkpointer instance.

    If force_memory is True or PostgresSaver is unavailable, returns a MemorySaver.
    Otherwise returns a persistent PostgresSaver connected to db_url (or settings.DATABASE_URL).
    """
    global _checkpointer_instance, _pool

    if _checkpointer_instance is not None:
        return _checkpointer_instance

    if force_memory or not POSTGRES_SAVER_AVAILABLE:
        _checkpointer_instance = MemorySaver()
        return _checkpointer_instance

    try:
        from backend.app.core.config import settings

        raw_url = db_url or settings.DATABASE_URL
        # Normalize SQLAlchemy dialect prefix (postgresql+psycopg://) to libpq format (postgresql://)
        conn_info = raw_url.replace("postgresql+psycopg://", "postgresql://")
        if not conn_info:
            _checkpointer_instance = MemorySaver()
            return _checkpointer_instance

        connection_kwargs = {"autocommit": True, "row_factory": dict_row}
        _pool = ConnectionPool(
            conninfo=conn_info,
            max_size=10,
            kwargs=connection_kwargs,
            open=True,
        )
        _checkpointer_instance = PostgresSaver(_pool)
        return _checkpointer_instance
    except Exception as exc:
        print(f"[Warning] Failed to initialize PostgresSaver: {exc}. Falling back to MemorySaver.")
        _checkpointer_instance = MemorySaver()
        return _checkpointer_instance


def close_checkpointer() -> None:
    """Close the underlying connection pool if open."""
    global _checkpointer_instance, _pool
    if _pool is not None:
        try:
            _pool.close()
        except Exception:
            pass
        _pool = None
    _checkpointer_instance = None


def reset_checkpointer_for_testing() -> BaseCheckpointSaver:
    """Reset the checkpointer to a fresh in-memory saver for testing."""
    close_checkpointer()
    global _checkpointer_instance
    _checkpointer_instance = MemorySaver()
    return _checkpointer_instance
