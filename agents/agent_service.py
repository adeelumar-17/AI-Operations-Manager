'''
This module defines the AgentService interface, serving as the single decoupled entry point for invoking and resuming the LangGraph operations agent. It is called by both FastAPI HTTP endpoints and APScheduler background jobs.
Classes:
    None (Agent facade and execution service module).
Methods:
    run_agent: Executes a single user operational prompt through the compiled LangGraph StateGraph, managing thread checkpoints and detecting policy interruptions.
    resume_agent: Resumes an interrupted workflow from a durable checkpoint when a manager approves or rejects an intercepted action.
'''

import uuid
from typing import Any, Optional

from langgraph.types import Command

from agents.graph.graph import agent_graph
from agents.graph.state import AgentState


def run_agent(
    user_input: str,
    conversation_id: str | None = None,
    request_id: str | None = None,
    conversation_history: list[dict] | None = None,
    thread_id: str | None = None,
) -> dict[str, Any]:
    """Invoke the operations agent for a single user request.

    Args:
        user_input: The raw user message.
        conversation_id: Optional — links this run to an ongoing conversation.
        request_id: Optional — unique ID for this run; auto-generated if absent.
        conversation_history: Optional — bounded list of prior messages to include as context.
        thread_id: Optional — persistence thread ID for LangGraph checkpointer. Defaults to conversation_id or request_id.

    Returns:
        A dict with at minimum:
          - "request_id": str
          - "thread_id": str
          - "response": the agent's natural-language response
          - "workflow": which workflow was selected
          - "intent": the detected intent
          - "approval_required": bool
          - "approval_id": str | None
          - "approval_decision": str | None
          - "error": str | None
    """
    req_id = request_id or str(uuid.uuid4())
    active_thread = thread_id or conversation_id or req_id

    initial_state: AgentState = {
        "request_id": req_id,
        "user_input": user_input,
        "conversation_id": conversation_id,
        "intent": None,
        "workflow": None,
        "entities": {},
        "action_plan": [],
        "action_results": [],
        "approval_required": False,
        "approval_id": None,
        "approval_decision": None,
        "response": None,
        "error": None,
        "messages": conversation_history or [],
    }

    config = {"configurable": {"thread_id": active_thread}}
    final_state = agent_graph.invoke(initial_state, config=config)

    # Check for LangGraph interrupt
    interrupt_info = None
    if "__interrupt__" in final_state and final_state["__interrupt__"]:
        interrupt_info = final_state["__interrupt__"][0].value

    approval_required = final_state.get("approval_required", False) or bool(interrupt_info)
    approval_id = final_state.get("approval_id")

    if interrupt_info and isinstance(interrupt_info, dict):
        approval_id = interrupt_info.get("approval_id") or approval_id

    response_text = final_state.get("response")
    if not response_text:
        if approval_required:
            response_text = (
                "Action requires managerial approval before proceeding. "
                f"Approval Request ID: {approval_id or 'pending'}. "
                "The operation is safely paused and will resume once reviewed."
            )
        else:
            response_text = "No response generated."

    return {
        "request_id": final_state.get("request_id", req_id),
        "thread_id": active_thread,
        "response": response_text,
        "workflow": final_state.get("workflow"),
        "intent": final_state.get("intent"),
        "entities": final_state.get("entities", {}),
        "action_results": final_state.get("action_results", []),
        "approval_required": approval_required,
        "approval_id": approval_id,
        "approval_decision": final_state.get("approval_decision"),
        "error": final_state.get("error"),
    }


def resume_agent(
    approval_id: str,
    approved: bool,
    thread_id: Optional[str] = None,
    comment: str = "",
    reviewer_id: Optional[str] = None,
) -> dict[str, Any]:
    """Resume an interrupted agent workflow with a managerial approval decision.

    Args:
        approval_id: The ID of the pending approval request.
        approved: True to approve the action; False to reject.
        thread_id: Optional thread ID. If absent, retrieved from the DB approval record.
        comment: Optional reviewer comment.
        reviewer_id: Optional user ID of the reviewer.

    Returns:
        The updated agent run result after continuing from the checkpoint.
    """
    resolved_thread = thread_id

    # Sync with DB approval_requests table if DB is accessible
    try:
        from backend.app.db.database import SessionLocal
        from backend.app.services.approval_service import ApprovalService
        with SessionLocal() as db:
            service = ApprovalService(db)
            if approved:
                rec = service.approve(approval_id, approved_by=reviewer_id)
            else:
                rec = service.reject(approval_id, approved_by=reviewer_id)

            if rec and not resolved_thread and rec.action_payload:
                resolved_thread = rec.action_payload.get("thread_id")
    except Exception:
        pass

    if not resolved_thread:
        # Fallback to approval_id itself if thread not found
        resolved_thread = approval_id

    config = {"configurable": {"thread_id": resolved_thread}}
    resume_payload = {
        "approved": approved,
        "comment": comment,
        "reviewer_id": reviewer_id,
        "approval_id": approval_id,
    }

    # Resume graph from the checkpoint
    final_state = agent_graph.invoke(Command(resume=resume_payload), config=config)

    decision_str = "approved" if approved else "rejected"
    response_text = final_state.get("response") or (
        f"Operation successfully resumed with decision: {decision_str.upper()}."
    )

    return {
        "request_id": final_state.get("request_id"),
        "thread_id": resolved_thread,
        "response": response_text,
        "workflow": final_state.get("workflow"),
        "intent": final_state.get("intent"),
        "entities": final_state.get("entities", {}),
        "action_results": final_state.get("action_results", []),
        "approval_required": True,
        "approval_id": approval_id,
        "approval_decision": decision_str,
        "error": final_state.get("error"),
    }
