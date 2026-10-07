"""Quote tools with a durable, deterministic approval boundary."""
import logging
import json
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.errors import GraphInterrupt
from agents.graph.state import AgentState
from agents.tools import ALL_TOOLS
from agents.prompts.prompts import SYSTEM_PROMPT
from agents.llm import get_llm
from backend.app.services.exceptions import ApprovalRequired
from agents.graph.nodes.approval_helpers import saved_approval, review_action

logger = logging.getLogger(__name__)


def _get_tools_for_quote():
    relevant = {"search_customer", "get_customer_details", "get_quote", "create_quote",
                "apply_discount_to_quote", "convert_quote_to_order", "check_stock",
                "check_fulfillment_feasibility", "get_all_products", "search_business_policy",
                "get_customer_history", "get_order_status", "update_order_status", "fulfill_order"}
    return [t for t in ALL_TOOLS if t.name in relevant]


def create_quote_node(state: AgentState, config: RunnableConfig) -> dict:
    results = []
    entities = dict(state.get("entities", {}))
    action_type = "quote_discount_approval"
    # Failures while resuming must leave a retriable checkpoint, not end the graph.
    if saved_approval(state, action_type):
        return review_action(state, config, action_type)
    try:
        tools = {t.name: t for t in _get_tools_for_quote()}
        llm = get_llm().bind_tools(list(tools.values()))
        messages = [SystemMessage(content=SYSTEM_PROMPT), *state.get("messages", []),
                    HumanMessage(content=state["user_input"] + "\nResolve identifiers using tools. "
                                 "Apply only requested changes. Convert or fulfill only when explicitly requested. "
                                 "For a new quotation, call create_quote with the customer's identifier and requested items. "
                                 "Use get_all_products or check_stock to resolve generic product descriptions to catalog SKUs. "
                                 "Use catalog prices through the tool; never calculate or invent prices. "
                                 "Retain its returned quote ID for later actions. Ask for clarification on ambiguous identifiers.")]
        for _ in range(6):
            response = llm.invoke(messages)
            messages.append(response)
            if not response.tool_calls:
                results.append({"tool": "direct_response", "result": response.content})
                break
            for call in response.tool_calls:
                tool = tools.get(call["name"])
                result = tool.invoke(call["args"]) if tool else "Error: tool unavailable in this workflow."
                if call["name"] == "create_quote" and not str(result).startswith("Error"):
                    entities["quote_id"] = json.loads(result)["quote_id"]
                results.append({"tool": call["name"], "args": call["args"], "result": result})
                messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
        else:
            return {"action_results": results, "error": "Quote workflow reached its tool limit; remaining actions were not completed."}
        return {"entities": entities,
                "action_plan": [{"action": "create_quote", "entities": entities}],
                "action_results": results}
    except ApprovalRequired as proposal:
        return review_action(state, config, proposal.action_type, proposal.payload, proposal.reason, results)
    except GraphInterrupt:
        raise
    except Exception as exc:
        logger.exception("Quote workflow failed")
        return {"action_results": results, "error": f"Quote workflow failed: {exc}"}
