import logging
logger = logging.getLogger(__name__)
'''
what the file does?
This module implements the formulate_response graph node, synthesizing tool outputs, execution errors, or pending approval requests into a clear, professional natural-language reply for the user.

Classes:
    None (LangGraph node module)

Methods:
    formulate_response: Graph node synthesizing tool results or approval gates into the final natural language response.
'''


from langchain_core.messages import HumanMessage, SystemMessage

from agents.graph.state import AgentState
from agents.prompts.prompts import RESPONSE_PROMPT, SYSTEM_PROMPT
from agents.llm import get_llm


def formulate_response(state: AgentState) -> dict:
    """Generate the final response from tool results.

    If there's an error, the response explains what went wrong.
    If approval is required, the response describes what's pending.
    Otherwise, summarizes what was accomplished.
    """
    error = state.get("error")
    approval_required = state.get("approval_required", False)
    action_results = state.get("action_results", [])
    workflow = state.get("workflow", "unknown")
    failed = [r for r in action_results if str(r.get("result", "")).startswith("Error")]
    if failed:
        error = error or "; ".join(str(r["result"]) for r in failed)

    # --- Error path ---
    if error:
        return {
            "error": error,
            "response": (
                f"I encountered an issue processing your request: {error}\n"
                "Please check the details and try again, or contact support if the problem persists."
            )
        }

    # --- Build results summary ---
    results_text = ""
    for r in action_results:
        tool_name = r.get("tool", "action")
        result = r.get("result", "")
        results_text += f"\n[{tool_name}]: {result}"

    # --- Approval required path ---
    decision = state.get("approval_decision")
    if approval_required and not decision:
        return {
            "response": (
                "⚠️ **Manager approval required**\n\n"
                "This action requires approval before it can be completed:\n"
                f"{results_text}\n\n"
                "The request has been logged as pending approval. "
                "A manager must approve or reject it before the operation proceeds."
            )
        }

    if decision:
        if decision == "approved":
            return {
                "response": (
                    "✅ **Manager Approval Granted**\n\n"
                    f"The manager decision was recorded.\n{results_text}"
                )
            }
        else:
            return {
                "response": (
                    "❌ **Manager Approval Rejected**\n\n"
                    f"The requested action was rejected by management.\n{results_text}"
                )
            }

    # --- Normal path: use LLM to write the response ---
    try:
        llm = get_llm(temperature=0.3)
        prompt = RESPONSE_PROMPT.format(
            workflow=workflow,
            action_results=results_text or "No actions were taken.",
            approval_required=approval_required,
        )
        response = llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content="Original request: " + state["user_input"] + "\n" + prompt)])
        return {"response": response.content.strip()}

    except Exception as e:
        logger.exception('Operation failed')
        # Fallback: just return the raw results
        return {
            "response": (
                f"Recorded results ({workflow}); response generation was unavailable.\n"
                f"Results:{results_text}"
            )
        }
