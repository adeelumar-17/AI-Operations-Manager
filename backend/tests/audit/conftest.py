"""Offline regressions: never use the configured deployment database or LLM."""
import os
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["SCHEDULER_ENABLED"] = "false"

from datetime import datetime, timezone
from uuid import uuid4
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from agents.memory.checkpointer import get_checkpointer

get_checkpointer(force_memory=True)


@compiles(JSONB, "sqlite")
def jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@pytest.fixture
def database(monkeypatch):
    from backend.app.db.models import Base
    engine = create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def functions(conn, record):
        conn.create_function("gen_random_uuid", 0, lambda: uuid4().hex)
        conn.create_function("now", 0, lambda: datetime.now(timezone.utc).replace(tzinfo=None).isoformat(' '))
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, autoflush=False)
    import backend.app.db.database as db_module
    monkeypatch.setattr(db_module, "SessionLocal", sessions)
    from agents.graph.nodes import approval_helpers
    monkeypatch.setattr(approval_helpers, "SessionLocal", sessions)
    yield sessions
    engine.dispose()
