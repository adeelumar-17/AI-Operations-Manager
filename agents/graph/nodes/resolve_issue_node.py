"""Issue review; threshold decisions run in Python, never in a prompt."""
import logging
from decimal import Decimal
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.errors import GraphInterrupt
from agents.graph.state import AgentState
from agents.tools import ALL_TOOLS
from agents.prompts.prompts import SYSTEM_PROMPT
from agents.llm import get_llm
from agents.graph.nodes.approval_helpers import saved_approval, review_action
from backend.app.services.authorization_service import check_refund_authorization

logger = logging.getLogger(__name__)


def _get_tools_for_issue():
    relevant = {"search_customer", "get_customer_details", "get_customer_history",
                "get_order_status", "get_invoice", "log_communication", "search_business_policy"}
    return [t for t in ALL_TOOLS if t.name in relevant]


def resolve_issue_node(state: AgentState, config: RunnableConfig) -> dict:
    results = []
    if saved_approval(state, "refund_approval"):
        return review_action(state, config, "refund_approval")
    try:
        entities = state.get("entities", {})
        if "refund" in state["user_input"].lower():
            if entities.get("amount") is None:
                return {"action_results": [{"tool": "direct_response", "result": "What refund amount should be reviewed? No refund has been issued."}]}
            amount = Decimal(str(entities["amount"]).replace("$", "").replace(",", ""))
            decision = check_refund_authorization(amount, Decimal("500"))
            if decision.approval_required:
                return review_action(state, config, "refund_approval", {"amount": str(amount), "entities": entities}, decision.reason)
        tools = {t.name: t for t in _get_tools_for_issue()}
        llm = get_llm().bind_tools(list(tools.values()))
        messages = [SystemMessage(content=SYSTEM_PROMPT), *state.get("messages", []),
                    HumanMessage(content=state["user_input"] + "\nReview facts and policy, and log a proposed resolution if requested. "
                                 "Refunds, return labels and replacements cannot be executed by these tools. "
                                 "Do not claim eligibility or authorization from policy prose alone; missing eligibility facts need human review.")]
        for _ in range(6):
            response = llm.invoke(messages)
            messages.append(response)
            if not response.tool_calls:
                results.append({"tool": "direct_response", "result": response.content})
                break
            for call in response.tool_calls:
                tool = tools.get(call["name"])
                result = tool.invoke(call["args"]) if tool else "Error: tool unavailable in this workflow."
                results.append({"tool": call["name"], "args": call["args"], "result": result})
                messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
        else:
            return {"action_results": results, "error": "Issue review reached its tool limit; remaining actions were not completed."}
        return {"action_results": results, "action_plan": [{"action": "issue_resolution", "entities": entities}]}
    except GraphInterrupt:
        raise
    except Exception as exc:
        logger.exception("Issue workflow failed")
        return {"action_results": results, "error": f"Issue workflow failed: {exc}"}
