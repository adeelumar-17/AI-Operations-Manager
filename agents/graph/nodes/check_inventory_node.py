'''
what the file does?
This module implements the check_inventory_node workflow node, invoking inventory tools via an LLM to check current product stock, adjust inventory levels, check order feasibility, and query low stock warnings.

Classes:
    None (LangGraph workflow node module)

Methods:
    _get_llm_with_tools: Binds inventory-specific LangChain tools to the LLM.
    check_inventory_node: Workflow node that executes inventory queries and updates, returning action results to state.
'''

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from agents.graph.state import AgentState
from agents.tools import ALL_TOOLS
from agents.prompts.prompts import SYSTEM_PROMPT
from agents.llm import get_llm


def _get_llm_with_tools() -> ChatGroq:
    llm = get_llm()
    # Only bind inventory-relevant tools for this workflow
    inventory_tools = [
        t for t in ALL_TOOLS
        if t.name in ("check_stock", "update_inventory", "check_fulfillment_feasibility", "get_low_stock_products", "search_customer")
    ]
    return llm.bind_tools(inventory_tools)


def check_inventory_node(state: AgentState) -> dict:
    """Execute the inventory / fulfillment check workflow.

    Calls inventory tools based on the user's request and entities,
    then returns the tool results in action_results.
    """
    user_input = state["user_input"]
    entities = state.get("entities", {})

    # Build context-aware prompt
    context_parts = [f"User request: {user_input}"]
    if entities.get("product_names"):
        context_parts.append(f"Products mentioned: {', '.join(entities['product_names'])}")
    if entities.get("quantities"):
        context_parts.append(f"Quantities mentioned: {entities['quantities']}")
    if entities.get("product_skus"):
        context_parts.append(f"SKUs mentioned: {', '.join(entities['product_skus'])}")

    context = "\n".join(context_parts)
    prompt = (
        f"{context}\n\n"
        "Handle the user's inventory request: "
        "- If the user asks how many items/units are available or checks stock, call check_stock (requested_quantity=0 if just checking current stock). "
        "- If the user asks to add, restock, or adjust stock units, call update_inventory. "
        "- If checking multiple products for order feasibility, call check_fulfillment_feasibility. "
        "- If asking about inventory health or low stock, call get_low_stock_products."
    )

    try:
        llm = _get_llm_with_tools()
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]
        response = llm.invoke(messages)

        # Execute any tool calls the LLM requested
        tool_results = []
        if hasattr(response, "tool_calls") and response.tool_calls:
            from langchain_core.messages import ToolMessage
            for tool_call in response.tool_calls:
                tool_fn = next(
                    (t for t in ALL_TOOLS if t.name == tool_call["name"]), None
                )
                if tool_fn:
                    result = tool_fn.invoke(tool_call["args"])
                    tool_results.append({
                        "tool": tool_call["name"],
                        "args": tool_call["args"],
                        "result": result,
                    })

        # If no tool calls, treat the LLM's direct response as the result
        if not tool_results:
            tool_results = [{"tool": "direct_response", "result": response.content}]

        return {
            "action_plan": [{"action": "check_inventory", "entities": entities}],
            "action_results": tool_results,
        }

    except Exception as e:
        return {
            "action_results": [],
            "error": f"Inventory check failed: {e}",
        }
