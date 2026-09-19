'''
what the file does?
This module implements the check_invoice_node workflow node, handling invoice and overdue balance lookups, customer payment histories, and days overdue calculations via LLM tool execution.

Classes:
    None (LangGraph workflow node module)

Methods:
    _get_tools_for_invoice: Returns invoice-related LangChain tools for binding to the LLM.
    check_invoice_node: Workflow node executing invoice status queries and returning action results.
'''

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

from agents.graph.state import AgentState
from agents.tools import ALL_TOOLS
from agents.prompts.prompts import SYSTEM_PROMPT
from agents.llm import get_llm


def _get_tools_for_invoice() -> list:
    relevant = {
        "search_customer", "get_invoice", "find_overdue_invoices",
        "get_days_overdue", "get_customer_history",
    }
    return [t for t in ALL_TOOLS if t.name in relevant]


def check_invoice_node(state: AgentState) -> dict:
    """Execute the invoice status / overdue workflow."""
    user_input = state["user_input"]
    entities = state.get("entities", {})

    context_parts = [f"User request: {user_input}"]
    if entities.get("customer_name"):
        context_parts.append(f"Customer: {entities['customer_name']}")
    if entities.get("invoice_id"):
        context_parts.append(f"Invoice: {entities['invoice_id']}")
    if entities.get("customer_id"):
        context_parts.append(f"Customer ID: {entities['customer_id']}")

    context = "\n".join(context_parts)
    prompt = (
        f"{context}\n\n"
        "Handle this invoice/payment request:\n"
        "- For a specific invoice, use get_invoice.\n"
        "- For overdue invoices (one customer), use find_overdue_invoices with the customer ID.\n"
        "- For all overdue invoices, use find_overdue_invoices with 'all'.\n"
        "- For days overdue on a specific invoice, use get_days_overdue."
    )

    try:
        llm = get_llm().bind_tools(_get_tools_for_invoice())

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]
        tool_results = []

        for _ in range(4):
            response = llm.invoke(messages)
            messages.append(response)

            if not (hasattr(response, "tool_calls") and response.tool_calls):
                break

            for tool_call in response.tool_calls:
                tool_fn = next((t for t in ALL_TOOLS if t.name == tool_call["name"]), None)
                if tool_fn:
                    result = tool_fn.invoke(tool_call["args"])
                    tool_results.append({
                        "tool": tool_call["name"],
                        "args": tool_call["args"],
                        "result": result,
                    })
                    messages.append(
                        ToolMessage(content=str(result), tool_call_id=tool_call["id"])
                    )

        return {
            "action_plan": [{"action": "check_invoice", "entities": entities}],
            "action_results": tool_results,
        }

    except Exception as e:
        return {
            "action_results": [],
            "error": f"Invoice workflow failed: {e}",
        }
