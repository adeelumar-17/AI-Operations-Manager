"""Serverless integration regressions, with no deployment/database access."""
import importlib
from unittest.mock import Mock
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient


def test_vercel_never_starts_background_scheduler(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("SCHEDULER_ENABLED", "true")
    main = importlib.import_module("backend.app.main")
    previous = main._SCHEDULER_ENABLED
    try:
        main = importlib.reload(main)
        start = Mock()
        monkeypatch.setattr(main, "start_scheduler", start)
        with TestClient(main.app) as client:
            assert client.get("/health").json()["status"] == "ok"
            response = client.options("/api/v1/chat", headers={
                "Origin": "https://ai-operations-manager-umber.vercel.app",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-user-id",
            })
            assert response.status_code == 200
            assert response.headers["access-control-allow-origin"]
        start.assert_not_called()
    finally:
        main._SCHEDULER_ENABLED = previous


def test_vercel_refuses_nonpersistent_checkpoint_fallback(monkeypatch):
    from agents.memory import checkpointer
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setattr(checkpointer, "_checkpointer_instance", None)
    monkeypatch.setattr(checkpointer, "POSTGRES_SAVER_AVAILABLE", False)
    with pytest.raises(RuntimeError, match="Persistent PostgreSQL"):
        checkpointer.get_checkpointer()


def test_due_task_limit_keeps_remaining_work_pending(database):
    from test_regressions import seed_quote
    from backend.app.db.repositories.followup_repository import FollowupRepository
    customer_id, _, _ = seed_quote(database)
    with database() as db:
        repo = FollowupRepository(db)
        for _ in range(2):
            repo.create("customer_followup", datetime.now(timezone.utc) - timedelta(minutes=1), customer_id)
        assert len(repo.get_due_tasks(limit=1)) == 1
        assert len(repo.get_due_tasks()) == 2


def test_onnx_dispatch_does_not_import_pytorch(monkeypatch):
    from rag import embeddings
    import rag.onnx_embeddings as onnx
    monkeypatch.setenv("EMBEDDING_BACKEND", "onnx")
    encode = Mock(return_value=[0.0] * 384)
    monkeypatch.setattr(onnx, "embed", encode)
    assert len(embeddings.embed_query("policy")) == 384
    encode.assert_called_once_with("policy")


def test_existing_embedding_backend_default_is_preserved(monkeypatch):
    from rag.embeddings import _get_embedding_backend
    monkeypatch.delenv("EMBEDDING_BACKEND", raising=False)
    monkeypatch.delenv("VERCEL", raising=False)
    assert _get_embedding_backend() == "sentence-transformers"
    monkeypatch.setenv("VERCEL", "1")
    assert _get_embedding_backend() == "onnx"
