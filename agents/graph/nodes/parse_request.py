'''
what the file does?
This module implements the parse_request entry node in the LangGraph workflow, initializing and sanitizing input state fields, generating request IDs, and setting default values before classification.

Classes:
    None (LangGraph node module)

Methods:
    parse_request: Entry node that sanitizes user input, generates a unique request_id, and initializes state fields.
'''

import uuid
from agents.graph.state import AgentState


def parse_request(state: AgentState) -> dict:
    """Normalize the incoming user request.

    Ensures request_id is populated and user_input is clean.
    Sets sensible defaults for all fields that later nodes will populate.
    """
    return {
        "request_id": state.get("request_id") or str(uuid.uuid4()),
        "user_input": state.get("user_input", "").strip(),
        # Ensure these are initialized so later nodes can safely read them
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
    }
