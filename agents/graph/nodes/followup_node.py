'''
what the file does?
This module implements the followup_node workflow node, creating scheduled followup tasks, triggering automated customer reminders, and performing bulk follow-ups on aging quotes or overdue invoices.

Classes:
    None (LangGraph workflow node module)

Methods:
    _get_tools_for_followup: Returns communication and customer tools for follow-up workflows.
    followup_node: Workflow node that schedules tasks, records follow-up communications, and executes automated reminders.
'''

import uuid
from datetime import datetime, timezone
from typing import Any

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from sqlalchemy import select, text

from agents.graph.state import AgentState
from agents.tools import ALL_TOOLS
from agents.prompts.prompts import SYSTEM_PROMPT
from agents.llm import get_llm
from backend.app.db.database import SessionLocal


def _get_tools_for_followup() -> list:
    relevant = {
        "search_customer", "get_customer_details", "get_customer_history",
        "log_communication", "get_communication_history",
        "find_overdue_invoices",
    }
    return [t for t in ALL_TOOLS if t.name in relevant]


def followup_node(state: AgentState) -> dict:
    """Execute the follow-up workflow.

    Two sub-cases:
    1. Explicit follow-up: user names a customer + timeframe → creates followup_task
    2. Bulk follow-up: find and action quotes/invoices past a threshold
    """
    user_input = state["user_input"]
    entities = state.get("entities", {})

    context_parts = [f"User request: {user_input}"]
    if entities.get("customer_name"):
        context_parts.append(f"Customer: {entities['customer_name']}")
    if entities.get("date"):
        context_parts.append(f"Timeframe: {entities['date']}")

    context = "\n".join(context_parts)
    prompt = (
        f"{context}\n\n"
        "Handle this follow-up request:\n"
        "1. If the user names a specific customer, look them up with search_customer.\n"
        "2. If this is a bulk follow-up (e.g., 'all overdue invoices'), "
        "use find_overdue_invoices to get the list.\n"
        "3. Log a note or email communication for each customer you follow up with.\n"
        "4. Summarize what follow-ups were scheduled or executed."
    )

    try:
        llm = get_llm().bind_tools(_get_tools_for_followup())

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]
        tool_results = []

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
                    messages.append(
                        ToolMessage(content=str(result), tool_call_id=tool_call["id"])
                    )

        # Optionally create a followup_task record if a specific date was extracted
        task_id = None
        if entities.get("date") and entities.get("customer_id"):
            task_id = _create_followup_task(
                customer_id=entities["customer_id"],
                scheduled_at_str=entities["date"],
                task_type="manual_reminder",
            )

        if task_id:
            tool_results.append({
                "tool": "create_followup_task",
                "result": f"Follow-up task created: {task_id}",
            })

        return {
            "action_plan": [{"action": "follow_up", "entities": entities}],
            "action_results": tool_results,
        }

    except Exception as e:
        return {
            "action_results": [],
            "error": f"Follow-up workflow failed: {e}",
        }


def _create_followup_task(
    customer_id: str,
    scheduled_at_str: str,
    task_type: str = "manual_reminder",
    quote_id: str | None = None,
) -> str | None:
    """Insert a followup_tasks row and return the new task ID."""
    try:
        # Parse a simple date string — production would use dateparser
        from datetime import datetime
        # Try ISO format first, then fallback
        try:
            scheduled_at = datetime.fromisoformat(scheduled_at_str)
        except ValueError:
            scheduled_at = datetime.now(timezone.utc)

        task_id = str(uuid.uuid4())
        session = SessionLocal()
        try:
            session.execute(
                text(
                    """
                    INSERT INTO followup_tasks
                        (id, task_type, customer_id, quote_id, scheduled_at, status, created_at)
                    VALUES
                        (:id, :task_type, :customer_id, :quote_id, :scheduled_at, 'pending', now())
                    """
                ),
                {
                    "id": task_id,
                    "task_type": task_type,
                    "customer_id": customer_id,
                    "quote_id": quote_id,
                    "scheduled_at": scheduled_at,
                },
            )
            session.commit()
            return task_id
        finally:
            session.close()
    except Exception:
        return None
