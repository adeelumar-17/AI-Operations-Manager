'''
what the file does?
This module implements the resolve_issue_node workflow node, handling customer complaints, returns, refund evaluations against business policy, and approval escalations for high-value refunds.

Classes:
    None (LangGraph workflow node module)

Methods:
    _get_tools_for_issue: Returns relevant LangChain tools for issue triage and policy verification.
    resolve_issue_node: Workflow node that queries orders/policies, evaluates refund eligibility, and triggers approvals if needed.
'''

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

from agents.graph.state import AgentState
from agents.tools import ALL_TOOLS
from agents.prompts.prompts import SYSTEM_PROMPT
from agents.llm import get_llm


def _get_tools_for_issue() -> list:
    relevant = {
        "search_customer", "get_customer_details", "get_customer_history",
        "get_order_status", "get_invoice",
        "log_communication",
        "search_business_policy",
    }
    return [t for t in ALL_TOOLS if t.name in relevant]


def resolve_issue_node(state: AgentState) -> dict:
    """Execute the issue resolution workflow.

    Looks up the customer and related order/invoice, retrieves the return/refund
    policy, determines if approval is needed (refund > $500), and logs the
    communication. Sets approval_required if the refund amount exceeds the threshold.
    """
    user_input = state["user_input"]
    entities = state.get("entities", {})

    context_parts = [f"User request: {user_input}"]
    if entities.get("customer_name"):
        context_parts.append(f"Customer: {entities['customer_name']}")
    if entities.get("order_id"):
        context_parts.append(f"Order: {entities['order_id']}")
    if entities.get("amount"):
        context_parts.append(f"Amount: ${entities['amount']}")

    context = "\n".join(context_parts)
    prompt = (
        f"{context}\n\n"
        "Handle this issue/complaint:\n"
        "1. Look up the customer if needed.\n"
        "2. Use search_business_policy to check the return and refund policy.\n"
        "3. Look up the related order or invoice if an ID is mentioned.\n"
        "4. If a refund is requested, check if it exceeds $500 (requires approval).\n"
        "5. Log a note communication after determining the resolution.\n"
        "6. Summarize what action was taken or what approval is needed."
    )

    try:
        llm = get_llm().bind_tools(_get_tools_for_issue())

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]
        tool_results = []
        approval_required = False

        for _ in range(6):
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
                    # Detect if refund policy requires approval
                    result_str = str(result)
                    if "approval" in result_str.lower() and "require" in result_str.lower():
                        amount = entities.get("amount", 0)
                        if amount and float(str(amount).replace("$", "")) > 500:
                            approval_required = True

                    messages.append(
                        ToolMessage(content=result_str, tool_call_id=tool_call["id"])
                    )

        approval_id = state.get("approval_id")
        approval_decision = state.get("approval_decision")

        # Human-in-the-loop interrupt if refund > $500 requires approval
        if approval_required and not approval_decision:
            import uuid
            approval_id = approval_id or str(uuid.uuid4())
            try:
                from backend.app.db.database import SessionLocal
                from backend.app.services.approval_service import ApprovalService
                with SessionLocal() as db:
                    service = ApprovalService(db)
                    service.request_approval(
                        action_type="refund_approval",
                        action_payload={"entities": entities, "thread_id": state.get("request_id")},
                        reason="Refund amount exceeds policy threshold ($500). Requires manager approval.",
                    )
            except Exception:
                pass

            try:
                from langgraph.types import interrupt
                decision_payload = interrupt({
                    "approval_id": approval_id,
                    "action_type": "refund_approval",
                    "reason": "Refund amount exceeds policy threshold ($500). Requires manager approval.",
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
            "action_plan": [{"action": "issue_resolution", "entities": entities}],
            "action_results": tool_results,
            "approval_required": approval_required,
            "approval_id": approval_id,
            "approval_decision": approval_decision,
        }

    except Exception as e:
        return {
            "action_results": [],
            "error": f"Issue resolution workflow failed: {e}",
        }
