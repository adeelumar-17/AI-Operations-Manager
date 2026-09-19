'''
what the file does?
This module configures the state checkpointer for LangGraph execution, providing persistent SQLite checkpointing for interrupted agent runs and human-in-the-loop approvals, with an in-memory fallback.

Classes:
    None (State checkpointer configuration module)

Methods:
    get_checkpointer: Returns a singleton checkpointer instance (SqliteSaver or in-memory MemorySaver).
    reset_checkpointer_for_testing: Closes any active SQLite connection and resets the checkpointer to a clean MemorySaver.
'''

import os
import sqlite3
from typing import Optional
from langgraph.checkpoint.base import BaseCheckpointSaver

try:
    from langgraph.checkpoint.sqlite import SqliteSaver
    SQLITE_SAVER_AVAILABLE = True
except ImportError:
    SQLITE_SAVER_AVAILABLE = False

from langgraph.checkpoint.memory import MemorySaver

# Singleton connection and checkpointer
_checkpointer_instance: Optional[BaseCheckpointSaver] = None
_sqlite_conn: Optional[sqlite3.Connection] = None


def get_checkpointer(
    db_path: str = "data/checkpoints/operations_agent.db",
    force_memory: bool = False,
) -> BaseCheckpointSaver:
    """Return a checkpointer instance.

    If force_memory is True or SQLite is unavailable, returns a MemorySaver.
    Otherwise returns a persistent SqliteSaver saving to db_path.
    """
    global _checkpointer_instance, _sqlite_conn

    if _checkpointer_instance is not None:
        return _checkpointer_instance

    if force_memory or not SQLITE_SAVER_AVAILABLE:
        _checkpointer_instance = MemorySaver()
        return _checkpointer_instance

    try:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        _sqlite_conn = sqlite3.connect(db_path, check_same_thread=False)
        _checkpointer_instance = SqliteSaver(_sqlite_conn)
        return _checkpointer_instance
    except Exception as exc:
        print(f"[Warning] Failed to initialize SqliteSaver at '{db_path}': {exc}. Falling back to MemorySaver.")
        _checkpointer_instance = MemorySaver()
        return _checkpointer_instance


def reset_checkpointer_for_testing() -> BaseCheckpointSaver:
    """Reset the checkpointer to a fresh in-memory saver for testing."""
    global _checkpointer_instance, _sqlite_conn
    if _sqlite_conn:
        try:
            _sqlite_conn.close()
        except Exception:
            pass
        _sqlite_conn = None
    _checkpointer_instance = MemorySaver()
    return _checkpointer_instance
