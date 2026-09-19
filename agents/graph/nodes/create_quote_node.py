'''
what the file does?
This module implements the create_quote_node workflow node, orchestrating quote lookups, policy checks, discount applications, approval gating for high discounts, and quote-to-order conversions.

Classes:
    None (LangGraph workflow node module)

Methods:
    _get_tools_for_quote: Filters ALL_TOOLS to the set required for quoting and policy enforcement.
    create_quote_node: Workflow node executing quote adjustments, checking discount policy thresholds, and raising approval flags when required.
'''

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from agents.graph.state import AgentState
from agents.tools import ALL_TOOLS
from agents.prompts.prompts import SYSTEM_PROMPT
from agents.llm import get_llm


def _get_tools_for_quote() -> list:
    relevant = {
        "search_customer", "get_customer_details",
        "get_quote", "apply_discount_to_quote", "convert_quote_to_order",
        "check_stock", "check_fulfillment_feasibility",
        "search_business_policy",
    }
    return [t for t in ALL_TOOLS if t.name in relevant]


def create_quote_node(state: AgentState) -> dict:
    """Execute the quotation workflow.

    Handles: discount policy lookup, discount application with approval check,
    and quote-to-order conversion.

    Sets approval_required=True if the discount exceeds the policy threshold.
    """
    user_input = state["user_input"]
    entities = state.get("entities", {})

    context_parts = [f"User request: {user_input}"]
    if entities.get("customer_name"):
        context_parts.append(f"Customer: {entities['customer_name']}")
    if entities.get("discount_percent"):
        context_parts.append(f"Requested discount: {entities['discount_percent']}%")
    if entities.get("quote_id"):
        context_parts.append(f"Quote ID: {entities['quote_id']}")

    context = "\n".join(context_parts)
    prompt = (
        f"{context}\n\n"
        "Handle this quotation request. Steps:\n"
        "1. If a customer is mentioned but no ID given, use search_customer first.\n"
        "2. Use search_business_policy to look up the discount policy before applying any discount.\n"
        "3. Apply the discount using apply_discount_to_quote.\n"
        "4. If the response says 'APPROVAL REQUIRED', stop — do not convert to order.\n"
        "5. Only convert to order if the quote is approved and the user explicitly requests it."
    )

    try:
        llm = get_llm().bind_tools(_get_tools_for_quote())

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]

        # Agentic loop — let the LLM call tools until it stops
        tool_results = []
        approval_required = False
        max_iterations = 6

        for _ in range(max_iterations):
            response = llm.invoke(messages)
            messages.append(response)

            if not (hasattr(response, "tool_calls") and response.tool_calls):
                break

            from langchain_core.messages import ToolMessage
            for tool_call in response.tool_calls:
                tool_fn = next((t for t in ALL_TOOLS if t.name == tool_call["name"]), None)
                if tool_fn:
                    result = tool_fn.invoke(tool_call["args"])
                    tool_results.append({
                        "tool": tool_call["name"],
                        "args": tool_call["args"],
                        "result": result,
                    })
                    # Detect approval flag from the tool output
                    if "APPROVAL REQUIRED" in str(result):
                        approval_required = True

                    messages.append(
                        ToolMessage(content=str(result), tool_call_id=tool_call["id"])
                    )

            if approval_required:
                break

        # Also inspect entities and user input for discounts exceeding standard 10% threshold
        import re
        for k, v in entities.items():
            if "discount" in k.lower():
                try:
                    d_val = float(str(v).replace("%", "").strip())
                    if d_val > 10:
                        approval_required = True
                except (ValueError, TypeError):
                    pass

        disc_match = re.search(r"(\d+(?:\.\d+)?)\s*%\s*discount", state.get("user_input", ""), re.IGNORECASE)
        if disc_match and float(disc_match.group(1)) > 10:
            approval_required = True

        approval_id = state.get("approval_id")
        approval_decision = state.get("approval_decision")

        # Human-in-the-loop interrupt if approval is required and not yet decided
        if approval_required and not approval_decision:
            import uuid
            approval_id = approval_id or str(uuid.uuid4())
            try:
                from backend.app.db.database import SessionLocal
                from backend.app.services.approval_service import ApprovalService
                with SessionLocal() as db:
                    service = ApprovalService(db)
                    service.request_approval(
                        action_type="quote_discount_approval",
                        action_payload={"entities": entities, "thread_id": state.get("request_id")},
                        reason="Discount exceeds standard policy threshold (>10%). Requires manager approval.",
                    )
            except Exception:
                pass

            try:
                from langgraph.types import interrupt
                decision_payload = interrupt({
                    "approval_id": approval_id,
                    "action_type": "quote_discount_approval",
                    "reason": "Discount exceeds standard policy threshold (>10%). Requires manager approval.",
                    "payload": entities,
                })
                approved = decision_payload.get("approved", False) if isinstance(decision_payload, dict) else bool(decision_payload)
                approval_decision = "approved" if approved else "rejected"
                tool_results.append({
                    "tool": "manager_approval",
                    "result": f"Manager decision received: {approval_decision.upper()}.",
                })
            except Exception:
                pass

        return {
            "action_plan": [{"action": "create_quote", "entities": entities}],
            "action_results": tool_results,
            "approval_required": approval_required,
            "approval_id": approval_id,
            "approval_decision": approval_decision,
        }

    except Exception as e:
        return {
            "action_results": [],
            "error": f"Quote workflow failed: {e}",
        }
