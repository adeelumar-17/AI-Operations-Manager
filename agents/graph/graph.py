'''
This module defines and compiles the core LangGraph StateGraph topology for the operations agent. It wires routing nodes (parse, classify, extract, select), conditional execution branches for all 6 operational workflows, and response formulation with durable checkpointing.
Classes:
    None (Graph definition and assembly module).
Methods:
    build_graph: Constructs and compiles the operations agent StateGraph with persistence checkpointing and interrupt boundaries.
'''

from langgraph.graph import StateGraph, END
from typing import Any
from agents.graph.state import (
    AgentState,
    WORKFLOW_INVENTORY,
    WORKFLOW_QUOTE,
    WORKFLOW_INVOICE,
    WORKFLOW_CUSTOMER,
    WORKFLOW_ISSUE,
    WORKFLOW_FOLLOWUP,
)
from agents.graph.nodes.parse_request import parse_request
from agents.graph.nodes.classify_intent import classify_intent
from agents.graph.nodes.identify_entities import identify_entities
from agents.graph.nodes.select_workflow import select_workflow, route_to_workflow
from agents.graph.nodes.check_inventory_node import check_inventory_node
from agents.graph.nodes.create_quote_node import create_quote_node
from agents.graph.nodes.check_invoice_node import check_invoice_node
from agents.graph.nodes.customer_mgmt_node import customer_mgmt_node
from agents.graph.nodes.resolve_issue_node import resolve_issue_node
from agents.graph.nodes.followup_node import followup_node
from agents.graph.nodes.formulate_response import formulate_response
from backend.app.core.audit import audit_node


def build_graph(checkpointer=None) -> Any:
    """Construct and compile the operations agent graph.

    Args:
        checkpointer: Optional checkpointer. Defaults to get_checkpointer().

    Returns a compiled graph ready to invoke.
    """
    graph = StateGraph(AgentState)

    # --- Routing nodes (every request passes through all four) ---------------
    graph.add_node("parse_request", audit_node("parse_request")(parse_request))
    graph.add_node("classify_intent", audit_node("classify_intent")(classify_intent))
    graph.add_node("identify_entities", audit_node("identify_entities")(identify_entities))
    graph.add_node("select_workflow", audit_node("select_workflow")(select_workflow))

    # --- Workflow nodes (only one is visited per run) ------------------------
    graph.add_node(WORKFLOW_INVENTORY, audit_node(WORKFLOW_INVENTORY)(check_inventory_node))
    graph.add_node(WORKFLOW_QUOTE, audit_node(WORKFLOW_QUOTE)(create_quote_node))
    graph.add_node(WORKFLOW_INVOICE, audit_node(WORKFLOW_INVOICE)(check_invoice_node))
    graph.add_node(WORKFLOW_CUSTOMER, audit_node(WORKFLOW_CUSTOMER)(customer_mgmt_node))
    graph.add_node(WORKFLOW_ISSUE, audit_node(WORKFLOW_ISSUE)(resolve_issue_node))
    graph.add_node(WORKFLOW_FOLLOWUP, audit_node(WORKFLOW_FOLLOWUP)(followup_node))

    # --- Response node (every path converges here) ---------------------------
    graph.add_node("formulate_response", audit_node("formulate_response")(formulate_response))

    # --- Edges ---------------------------------------------------------------
    graph.set_entry_point("parse_request")
    graph.add_edge("parse_request", "classify_intent")
    graph.add_edge("classify_intent", "identify_entities")
    graph.add_edge("identify_entities", "select_workflow")

    # Conditional routing from select_workflow → one of the 6 workflow nodes
    graph.add_conditional_edges(
        "select_workflow",
        route_to_workflow,
        {
            WORKFLOW_INVENTORY: WORKFLOW_INVENTORY,
            WORKFLOW_QUOTE: WORKFLOW_QUOTE,
            WORKFLOW_INVOICE: WORKFLOW_INVOICE,
            WORKFLOW_CUSTOMER: WORKFLOW_CUSTOMER,
            WORKFLOW_ISSUE: WORKFLOW_ISSUE,
            WORKFLOW_FOLLOWUP: WORKFLOW_FOLLOWUP,
        },
    )

    # All workflow nodes converge at formulate_response
    for workflow_node in [
        WORKFLOW_INVENTORY,
        WORKFLOW_QUOTE,
        WORKFLOW_INVOICE,
        WORKFLOW_CUSTOMER,
        WORKFLOW_ISSUE,
        WORKFLOW_FOLLOWUP,
    ]:
        graph.add_edge(workflow_node, "formulate_response")

    graph.add_edge("formulate_response", END)

    from agents.memory.checkpointer import get_checkpointer
    active_checkpointer = checkpointer if checkpointer is not None else get_checkpointer()
    return graph.compile(checkpointer=active_checkpointer)


# Module-level singleton — import and use `agent_graph` directly
agent_graph = build_graph()
