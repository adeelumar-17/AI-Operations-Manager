'''
what the file does?
This module provides operational audit logging utilities and decorators for recording agent execution runs, node visits, tool executions, approval statuses, and operational errors in the audit_logs table.

Classes:
    None (Audit utility and decorator module)

Methods:
    record_audit_log: Persists an individual structured audit log entry to the database with fallback logging on failure.
    audit_node: Decorator factory wrapping LangGraph node functions to automatically capture and log node execution inputs, outputs, errors, and timing.
'''

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from uuid import UUID, uuid4

from backend.app.db.database import SessionLocal
from backend.app.db.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


def record_audit_log(
    node: str,
    tool: Optional[str] = None,
    action: Optional[str] = None,
    input_data: Optional[dict[str, Any]] = None,
    output_data: Optional[dict[str, Any]] = None,
    approval_status: Optional[str] = None,
    result: Optional[str] = None,
    error: Optional[str] = None,
    run_id: Optional[UUID | str] = None,
    conversation_id: Optional[UUID | str] = None,
    user_id: Optional[UUID | str] = None,
) -> Optional[UUID]:
    """Record an audit log entry in the database.

    Gracefully logs a warning if the database is unreachable rather than failing the agent run.
    """
    try:
        def _to_uuid(val: Any) -> Optional[UUID]:
            if not val:
                return None
            if isinstance(val, UUID):
                return val
            try:
                return UUID(str(val))
            except (ValueError, TypeError):
                return None

        with SessionLocal() as db:
            log_entry = AuditLog(
                id=uuid4(),
                run_id=_to_uuid(run_id),
                conversation_id=_to_uuid(conversation_id),
                user_id=_to_uuid(user_id),
                node=node,
                tool=tool,
                action=action,
                input=input_data or {},
                output=output_data or {},
                approval_status=approval_status,
                result=result,
                error=error,
                timestamp=datetime.now(timezone.utc),
            )
            db.add(log_entry)
            db.commit()
            return log_entry.id
    except Exception as exc:
        logger.debug(f"Audit log recording skipped (DB unavailable or error): {exc}")
        return None


def audit_node(node_name: str):
    """Decorator for wrapping LangGraph nodes to automatically capture audit logs."""
    def decorator(fn: Callable):
        def wrapper(state: dict, *args, **kwargs) -> dict:
            run_id = state.get("request_id")
            conv_id = state.get("conversation_id")
            input_summary = {
                "workflow": state.get("workflow"),
                "intent": state.get("intent"),
                "user_input": state.get("user_input", "")[:100],
            }

            try:
                result = fn(state, *args, **kwargs)
                record_audit_log(
                    node=node_name,
                    action=state.get("workflow") or node_name,
                    input_data=input_summary,
                    output_data={
                        "approval_required": result.get("approval_required"),
                        "approval_decision": result.get("approval_decision"),
                        "has_response": bool(result.get("response")),
                    },
                    approval_status=result.get("approval_decision"),
                    result=str(result.get("response", ""))[:200] if result.get("response") else None,
                    error=result.get("error"),
                    run_id=run_id,
                    conversation_id=conv_id,
                )
                return result
            except Exception as exc:
                record_audit_log(
                    node=node_name,
                    action=state.get("workflow") or node_name,
                    input_data=input_summary,
                    error=str(exc),
                    run_id=run_id,
                    conversation_id=conv_id,
                )
                raise exc
        return wrapper
    return decorator
