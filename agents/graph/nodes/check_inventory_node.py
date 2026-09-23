"""Inventory queries and adjustments"""
import logging
from datetime import datetime, timezone
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from agents.graph.state import AgentState
from agents.tools import ALL_TOOLS
from agents.prompts.prompts import SYSTEM_PROMPT
from agents.llm import get_llm

logger = logging.getLogger(__name__)


def _get_tools_for_inventory() -> list:
    relevant = {"check_stock", "update_inventory", "check_fulfillment_feasibility", "get_low_stock_products", "get_all_products", "search_customer", "get_order_status", "fulfill_order", "update_order_status"}
    return [t for t in ALL_TOOLS if t.name in relevant]


def check_inventory_node(state: AgentState) -> dict:
    results = []
    try:
        tools = {t.name: t for t in _get_tools_for_inventory()}
        llm = get_llm().bind_tools(list(tools.values()))
        prompt = state['user_input'] + '\nCurrent UTC time: ' + datetime.now(timezone.utc).isoformat() + '\nUse tools for catalog, stock, restocking and fulfillment. Resolve ambiguous products before changing stock. Use multiple tool rounds when a request depends on earlier results. Only perform requested changes.'
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
        return {'action_results': results, 'action_plan': [{'action': 'check_inventory', 'entities': state.get('entities', {})}]}
    except Exception as exc:
        logger.exception('Inventory queries and adjustments failed')
        return {'action_results': results, 'error': str(exc)}
