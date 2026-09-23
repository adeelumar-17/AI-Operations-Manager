"""Verify a follow-up produced a persisted communication, not just prose."""
import re
from uuid import UUID
from backend.app.db.models.communication import Communication


def require_logged_communication(result, session, customer_id, entity_type=None, entity_id=None):
    if result.get("error") or (result.get("approval_required") and not result.get("approval_decision")):
        raise ValueError(result.get("error") or "The operation is awaiting approval.")
    for action in result.get("action_results", []):
        if action.get("tool") != "log_communication":
            continue
        match = re.search(r"\bID: ([0-9a-fA-F-]{36})", str(action.get("result", "")))
        if not match:
            continue
        comm = session.get(Communication, UUID(match.group(1)))
        if comm and comm.customer_id == customer_id and comm.direction == "outbound" and comm.status != "failed":
            if entity_id and (comm.related_entity_id != entity_id or comm.related_entity_type != entity_type):
                continue
            return comm
    raise ValueError("No matching follow-up communication was recorded; nothing was sent.")
