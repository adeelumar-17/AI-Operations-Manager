'''
what the file does?
This module implements the customer_mgmt_node workflow node, handling customer searches, profile lookups, communication history reviews, and general CRM interactions.

Classes:
    None (LangGraph workflow node module)

Methods:
    _get_tools_for_customer: Returns customer-related LangChain tools for LLM binding.
    customer_mgmt_node: Workflow node executing customer CRM actions and updating state with results.
'''

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

from agents.graph.state import AgentState
from agents.tools import ALL_TOOLS
from agents.prompts.prompts import SYSTEM_PROMPT
from agents.llm import get_llm


def _get_tools_for_customer() -> list:
    relevant = {
        "search_customer", "get_customer_details", "get_customer_history",
        "get_communication_history", "log_communication",
    }
    return [t for t in ALL_TOOLS if t.name in relevant]


def customer_mgmt_node(state: AgentState) -> dict:
    """Execute the customer management workflow."""
    user_input = state["user_input"]
    entities = state.get("entities", {})

    context_parts = [f"User request: {user_input}"]
    if entities.get("customer_name"):
        context_parts.append(f"Customer: {entities['customer_name']}")
    if entities.get("customer_id"):
        context_parts.append(f"Customer ID: {entities['customer_id']}")

    context = "\n".join(context_parts)
    prompt = (
        f"{context}\n\n"
        "Handle this customer management request:\n"
        "- If a customer name is given but no ID, use search_customer first.\n"
        "- For full account history (orders, invoices, communications), use get_customer_history.\n"
        "- For just communication history, use get_communication_history.\n"
        "- For a quick profile view, use get_customer_details."
    )

    try:
        llm = get_llm().bind_tools(_get_tools_for_customer())

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
            "action_plan": [{"action": "customer_management", "entities": entities}],
            "action_results": tool_results,
        }

    except Exception as e:
        return {
            "action_results": [],
            "error": f"Customer management workflow failed: {e}",
        }
