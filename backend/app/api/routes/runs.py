'''
This module defines the API routes for agent execution telemetry and audit logs. It provides endpoints for listing chronological agent execution runs and inspecting granular node transitions, tool invocations, and input/output payloads recorded during each run.
Classes:
    None (FastAPI router module).
Methods:
    list_runs: GET endpoint returning recent agent execution runs sorted chronologically descending.
    get_run_audit_logs: GET endpoint returning detailed step-by-step audit logs and tool calls for a specific agent run.
'''

from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_db, get_current_user
from backend.app.db.models.agent_run import AgentRun
from backend.app.db.models.audit_log import AuditLog

router = APIRouter(prefix="/runs", tags=["Agent Runs & Audits"])


@router.get("")
def list_runs(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List agent execution runs, sorted by most recent first."""
    stmt = select(AgentRun).order_by(AgentRun.started_at.desc()).limit(50)
    runs = db.scalars(stmt).all()
    return [
        {
            "id": str(r.id),
            "request_id": r.request_id,
            "intent": r.intent or "unknown",
            "status": r.status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "error": r.error,
        }
        for r in runs
    ]


@router.get("/{run_id}/logs")
def get_run_audit_logs(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get audit logs for a specific agent run."""
    try:
        run_uuid = UUID(run_id)
    except ValueError:
        return []

    stmt = select(AuditLog).where(AuditLog.run_id == run_uuid).order_by(AuditLog.timestamp.asc())
    logs = db.scalars(stmt).all()
    return [
        {
            "id": str(log.id),
            "run_id": str(log.run_id) if log.run_id else run_id,
            "node": log.node,
            "tool": log.tool,
            "input": log.input,
            "output": log.output,
            "action": log.action,
            "approval_status": log.approval_status,
            "result": log.result,
            "error": log.error,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        }
        for log in logs
    ]
