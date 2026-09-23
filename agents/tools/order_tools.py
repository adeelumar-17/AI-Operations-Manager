import logging
logger = logging.getLogger(__name__)
'''
what the file does?
This module provides LangChain-compatible order management tools for the operations agent, delegating to OrderService to retrieve order status, advance fulfillment lifecycle states, and execute order fulfillment.

Classes:
    None (LangChain tool definition module)

Methods:
    _make_order_service: Helper factory creating an OrderService instance with fresh DB session and dependencies.
    get_order_status: Tool to retrieve current status, totals, shipment dates, and line items for an order ID.
    update_order_status: Tool to transition an order's status (e.g. pending to confirmed, shipped, or delivered).
    fulfill_order: Tool to fulfill an order and decrement inventory levels for all ordered items.
'''

from typing import Annotated


from langchain_core.tools import tool

from backend.app.db.database import SessionLocal
from backend.app.db.repositories.inventory_repository import InventoryRepository
from backend.app.db.repositories.order_repository import OrderRepository
from backend.app.db.repositories.product_repository import ProductRepository
from backend.app.services.inventory_service import InventoryService
from backend.app.services.order_service import OrderService


def _make_order_service() -> tuple[OrderService, object]:
    session = SessionLocal()
    inventory_service = InventoryService(
        product_repository=ProductRepository(session),
        inventory_repository=InventoryRepository(session),
    )
    service = OrderService(
        order_repository=OrderRepository(session),
        inventory_service=inventory_service,
    )
    return service, session


@tool
def get_order_status(
    order_id: Annotated[str, "UUID of the order to look up"],
) -> str:
    """Retrieve an order's current status and key details.

    Returns the order number, status, total, shipped/delivered timestamps,
    and a list of items. Use when the customer asks about their order.
    """
    service, session = _make_order_service()
    try:
        order = service.get_order(order_id)
        lines = [
            f"Order: {order.order_number}",
            f"  Status: {order.status}",
            f"  Total: ${order.total}",
            f"  Created: {order.created_at.date()}",
        ]
        if order.shipped_at:
            lines.append(f"  Shipped: {order.shipped_at.date()}")
        if order.delivered_at:
            lines.append(f"  Delivered: {order.delivered_at.date()}")
        lines.append(f"  Items ({len(order.items)}):")
        for item in order.items:
            lines.append(
                f"    - Product {item.product_id} | Qty: {item.quantity} | Total: ${item.line_total}"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.exception('Operation failed')
        return f"Error retrieving order: {e}"
    finally:
        session.close()


@tool
def update_order_status(
    order_id: Annotated[str, "UUID of the order"],
    new_status: Annotated[
        str,
        "New status: 'processing', 'shipped', 'delivered', or 'cancelled'",
    ],
) -> str:
    """Transition an order to a new status.

    Valid transitions: pending→processing/cancelled, processing→shipped, shipped→delivered.
    Returns the updated order. Will fail if the transition is not allowed.
    """
    service, session = _make_order_service()
    try:
        order = service.transition_status(order_id, new_status)
        session.commit()
        return (
            f"✓ Order {order.order_number} status updated to '{order.status}'."
        )
    except Exception as e:
        logger.exception('Operation failed')
        return f"Error updating order status: {e}"
    finally:
        session.close()


@tool
def fulfill_order(
    order_id: Annotated[str, "UUID of the pending order to fulfill"],
) -> str:
    """Fulfill a pending order — checks inventory for all items and deducts stock.

    This will fail if any item has insufficient stock. On success the order
    status moves to 'processing' and inventory is updated.
    """
    service, session = _make_order_service()
    try:
        order = service.fulfill_order(order_id)
        session.commit()
        return (
            f"✓ Order {order.order_number} fulfilled. Status: {order.status}. "
            f"Inventory has been updated."
        )
    except Exception as e:
        logger.exception('Operation failed')
        return f"Error fulfilling order: {e}"
    finally:
        session.close()
