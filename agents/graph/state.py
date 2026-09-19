'''
what the file does?
This module defines the central AgentState TypedDict schema and workflow constants for the LangGraph state machine, representing the shared state flowing across all classification, routing, execution, approval gating, and response nodes.

Classes:
    AgentState: TypedDict defining the shared state structure (request metadata, intent, workflow, entities, action plan, execution results, approval status, messages, and output response).

Methods:
    None (State schema and constant definitions module)
'''

from typing import Annotated, Any
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Shared state for the operations agent graph.

    Fields are populated incrementally as the graph runs through its nodes.
    Nodes should only write to the fields they own — don't read-then-write
    fields owned by earlier nodes (that creates hidden coupling).
    """

    # ---- Input ---------------------------------------------------------------
    request_id: str
    """Unique ID for this agent run (maps to agent_runs.request_id in DB)."""

    user_input: str
    """The raw user message, exactly as received."""

    conversation_id: str | None
    """ID of the ongoing conversation, if any (for history loading in M8)."""

    # ---- Routing (set by classify/identify/select nodes) ---------------------
    intent: str | None
    """Detected intent, e.g. 'inventory_check', 'create_quote', 'follow_up'."""

    workflow: str | None
    """Selected workflow branch, one of the six workflow names."""

    entities: dict[str, Any]
    """Extracted business entities: customer_id, product_ids, amounts, etc."""

    # ---- Execution (set by workflow nodes) -----------------------------------
    action_plan: list[dict[str, Any]]
    """Ordered list of actions the agent intends to take."""

    action_results: list[dict[str, Any]]
    """Results of executed actions, one entry per action."""

    # ---- Approval gating (set by workflow nodes, consumed by M6) -------------
    approval_required: bool
    """True if any action in this run requires human approval before proceeding."""

    approval_id: str | None
    """ID of the approval_requests row, set when approval_required=True."""

    approval_decision: str | None
    """'approved' or 'rejected' — injected by the resume path in M6."""

    # ---- Output (set by formulate_response node) -----------------------------
    response: str | None
    """The final natural-language response to return to the user."""

    # ---- Error handling ------------------------------------------------------
    error: str | None
    """Set if any node fails; triggers the error-response path."""

    # ---- Conversation history (bounded, loaded in M8) ------------------------
    messages: Annotated[list, add_messages]
    """LangGraph message history — uses add_messages reducer to append safely."""


# Workflow branch names — used as the return values from select_workflow
WORKFLOW_INVENTORY = "inventory_check"
WORKFLOW_QUOTE = "create_quote"
WORKFLOW_INVOICE = "invoice_status"
WORKFLOW_ISSUE = "issue_resolution"
WORKFLOW_CUSTOMER = "customer_management"
WORKFLOW_FOLLOWUP = "follow_up"

ALL_WORKFLOWS = [
    WORKFLOW_INVENTORY,
    WORKFLOW_QUOTE,
    WORKFLOW_INVOICE,
    WORKFLOW_ISSUE,
    WORKFLOW_CUSTOMER,
    WORKFLOW_FOLLOWUP,
]
