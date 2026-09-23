"""Tools package for the AI Operations Manager agent.

Exports ALL_TOOLS — a flat list of every @tool-decorated function that can be
bound to an LLM. Import from here rather than from individual modules.

Usage:
    from agents.tools import ALL_TOOLS
    llm_with_tools = llm.bind_tools(ALL_TOOLS)
"""

from agents.tools.customer_tools import (
    search_customer,
    get_customer_details,
    get_customer_history,
)
from agents.tools.inventory_tools import (
    check_stock,
    check_fulfillment_feasibility,
    get_low_stock_products,
    update_inventory,
    get_all_products,
)
from agents.tools.quote_tools import (
    get_quote,
    apply_discount_to_quote,
    convert_quote_to_order,
)
from agents.tools.order_tools import (
    get_order_status,
    update_order_status,
    fulfill_order,
)
from agents.tools.invoice_tools import (
    get_invoice,
    find_overdue_invoices,
    get_days_overdue,
)
from agents.tools.communication_tools import (
    log_communication,
    get_communication_history,
)
from agents.tools.policy_tools import search_business_policy
from agents.tools.followup_tools import create_followup_task

ALL_TOOLS = [
    create_followup_task,
    # Customer management
    search_customer,
    get_customer_details,
    get_customer_history,
    # Inventory
    check_stock,
    check_fulfillment_feasibility,
    get_low_stock_products,
    update_inventory,
    get_all_products,
    # Quotes
    get_quote,
    apply_discount_to_quote,
    convert_quote_to_order,
    # Orders
    get_order_status,
    update_order_status,
    fulfill_order,
    # Invoices
    get_invoice,
    find_overdue_invoices,
    get_days_overdue,
    # Communications
    log_communication,
    get_communication_history,
    # Policy RAG
    search_business_policy,
]

__all__ = ["ALL_TOOLS"]
