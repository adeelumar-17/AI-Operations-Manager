"""Individual scheduling and follow-up logging"""
import logging
from datetime import datetime, timezone
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from agents.graph.state import AgentState
from agents.tools import ALL_TOOLS
from agents.prompts.prompts import SYSTEM_PROMPT
from agents.llm import get_llm

logger = logging.getLogger(__name__)


def _get_tools_for_followup() -> list:
    relevant = {"search_customer", "get_customer_details", "get_customer_history", "get_communication_history", "log_communication", "find_overdue_invoices", "get_invoice", "get_quote", "create_followup_task"}
    return [t for t in ALL_TOOLS if t.name in relevant]


def followup_node(state: AgentState) -> dict:
    results = []
    try:
        tools = {t.name: t for t in _get_tools_for_followup()}
        llm = get_llm().bind_tools(list(tools.values()))
        prompt = state['user_input'] + '\nCurrent UTC time: ' + datetime.now(timezone.utc).isoformat() + '\nFor a future reminder, resolve the customer and call create_followup_task; do not log a communication now. Ask for a time and timezone if unknown; never replace an unparseable date with now. For a due task, check the referenced quote or invoice and log a note or email draft with its related entity UUID. Tools log drafts but cannot send messages. Stale quote discovery is unavailable.'
        messages = [SystemMessage(content=SYSTEM_PROMPT), *state.get('messages', [])[-20:], HumanMessage(content=prompt)]
        for _ in range(6):
            response = llm.invoke(messages)
            messages.append(response)
            if not response.tool_calls:
                results.append({'tool': 'direct_response', 'result': response.content})
                break
            for call in response.tool_calls:
                tool = tools.get(call['name'])
                result = tool.invoke(call['args']) if tool else 'Error: tool unavailable in this workflow.'
                results.append({'tool': call['name'], 'args': call['args'], 'result': result})
                messages.append(ToolMessage(content=str(result), tool_call_id=call['id']))
        else:
            return {'action_results': results, 'error': 'Tool limit reached; remaining actions were not completed.'}
        return {'action_results': results, 'action_plan': [{'action': 'follow_up', 'entities': state.get('entities', {})}]}
    except Exception as exc:
        logger.exception('Individual scheduling and follow-up logging failed')
        return {'action_results': results, 'error': str(exc)}
