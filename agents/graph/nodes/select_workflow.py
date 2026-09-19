'''
what the file does?
This module implements the select_workflow routing node and edge condition function, validating the detected intent against permitted workflow names and determining the next node to branch into.

Classes:
    None (LangGraph node and conditional router module)

Methods:
    select_workflow: Node function mapping state['intent'] to state['workflow'] with safe fallback.
    route_to_workflow: Conditional edge predicate that returns the workflow branch name for graph routing.
'''

from agents.graph.state import (
    AgentState,
    ALL_WORKFLOWS,
    WORKFLOW_CUSTOMER,
)


def select_workflow(state: AgentState) -> dict:
    """Map the classified intent to a workflow branch name.

    If the intent is already a valid workflow name, pass it through.
    Falls back to 'customer_management' if intent is unrecognized.
    """
    intent = state.get("intent") or ""
    workflow = intent if intent in ALL_WORKFLOWS else WORKFLOW_CUSTOMER
    return {"workflow": workflow}


def route_to_workflow(state: AgentState) -> str:
    """Edge function for the conditional router in graph.py.

    LangGraph calls this after select_workflow to decide which node to visit next.
    Returns the workflow string which must exactly match a key in the conditional_edges dict.
    """
    return state.get("workflow") or WORKFLOW_CUSTOMER
