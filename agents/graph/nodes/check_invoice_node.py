"""Invoice facts and reminder drafts"""
import logging
from datetime import datetime, timezone
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from agents.graph.state import AgentState
from agents.tools import ALL_TOOLS
from agents.prompts.prompts import SYSTEM_PROMPT
from agents.llm import get_llm

logger = logging.getLogger(__name__)


def _get_tools_for_invoice() -> list:
    relevant = {"search_customer", "get_customer_details", "get_invoice", "find_overdue_invoices", "get_days_overdue", "get_customer_history", "log_communication", "get_communication_history"}
    return [t for t in ALL_TOOLS if t.name in relevant]


def check_invoice_node(state: AgentState) -> dict:
    results = []
    try:
        tools = {t.name: t for t in _get_tools_for_invoice()}
        llm = get_llm().bind_tools(list(tools.values()))
        prompt = state['user_input'] + '\nCurrent UTC time: ' + datetime.now(timezone.utc).isoformat() + '\nUse invoice tools for balances and overdue calculations. You cannot record payments or send email. When asked for a reminder, log an outbound email draft linked to the invoice UUID, and describe it as a draft.'
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
        return {'action_results': results, 'action_plan': [{'action': 'check_invoice', 'entities': state.get('entities', {})}]}
    except Exception as exc:
        logger.exception('Invoice facts and reminder drafts failed')
        return {'action_results': results, 'error': str(exc)}
