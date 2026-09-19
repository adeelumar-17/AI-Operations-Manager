'''
what the file does?
This module provides LangChain-compatible quote management tools for the operations agent, delegating to QuoteService to retrieve quote details, apply discount percentages, and convert accepted quotes into finalized orders.

Classes:
    None (LangChain tool definition module)

Methods:
    _make_quote_service: Helper factory creating a QuoteService instance with a fresh DB session.
    get_quote: Tool to retrieve a quote and its constituent line items by quote ID.
    apply_discount_to_quote: Tool to apply a percentage discount to an existing quote, returning discount details.
    convert_quote_to_order: Tool to convert an approved quote directly into a new customer order.
'''

import json
import uuid
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from langchain_core.tools import tool

from backend.app.db.database import SessionLocal
from backend.app.db.repositories.order_repository import OrderRepository
from backend.app.db.repositories.quote_repository import QuoteRepository
from backend.app.services.quote_service import QuoteService


def _make_quote_service() -> tuple[QuoteService, object]:
    session = SessionLocal()
    service = QuoteService(
        quote_repository=QuoteRepository(session),
        order_repository=OrderRepository(session),
    )
    return service, session


@tool
def get_quote(
    quote_id: Annotated[str, "UUID of the quote to retrieve"],
) -> str:
    """Retrieve a quote and its line items by ID.

    Returns quote number, customer, status, line items, subtotal, discount, and total.
    """
    service, session = _make_quote_service()
    try:
        quote = service.quote_repository.get_with_items(UUID(quote_id))
        if quote is None:
            return f"Quote {quote_id} not found."
        lines = [
            f"Quote: {quote.quote_number}",
            f"  Status: {quote.status}",
            f"  Customer ID: {quote.customer_id}",
            f"  Subtotal: ${quote.subtotal}",
            f"  Discount: {quote.discount_percent}% (${quote.discount_amount})",
            f"  Total: ${quote.total}",
            f"  Items ({len(quote.items)}):",
        ]
        for item in quote.items:
            lines.append(
                f"    - Product {item.product_id} | Qty: {item.quantity} | "
                f"Unit: ${item.unit_price} | Line: ${item.line_total}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving quote: {e}"
    finally:
        session.close()


@tool
def apply_discount_to_quote(
    quote_id: Annotated[str, "UUID of the quote"],
    discount_percent: Annotated[float, "Discount percentage (0-100) to apply"],
    approval_threshold: Annotated[
        float,
        "Max discount % allowed without approval (10 for regular, 15 for preferred customers)",
    ] = 10.0,
) -> str:
    """Apply a discount percentage to a quote.

    Returns the updated totals. If the discount exceeds the approval threshold,
    the quote status becomes 'pending_approval' — the caller MUST surface this
    to the user and NOT proceed without approval.

    The approval_threshold should match the customer's tier:
      - Regular customers: 10%
      - Preferred customers: 15%
    """
    service, session = _make_quote_service()
    try:
        quote = service.apply_discount(
            quote_id=UUID(quote_id),
            discount_percent=Decimal(str(discount_percent)),
            approval_threshold=Decimal(str(approval_threshold)),
        )
        approval_note = ""
        if quote.status == "pending_approval":
            approval_note = (
                "\n⚠ APPROVAL REQUIRED: Discount exceeds threshold. "
                "Quote is pending manager approval before it can be sent."
            )
        return (
            f"Discount applied to {quote.quote_number}:\n"
            f"  Discount: {quote.discount_percent}% (${quote.discount_amount})\n"
            f"  New total: ${quote.total}\n"
            f"  Status: {quote.status}"
            f"{approval_note}"
        )
    except Exception as e:
        return f"Error applying discount: {e}"
    finally:
        session.close()


@tool
def convert_quote_to_order(
    quote_id: Annotated[str, "UUID of the approved quote to convert to an order"],
) -> str:
    """Convert an approved quote to an order.

    The quote must have status 'approved'. Returns the new order number and ID.
    If the quote is not approved (e.g., still pending_approval), this will fail.
    """
    service, session = _make_quote_service()
    try:
        order = service.convert_to_order(UUID(quote_id))
        session.commit()
        return (
            f"✓ Quote converted to order successfully.\n"
            f"  Order number: {order.order_number}\n"
            f"  Order ID: {order.id}\n"
            f"  Total: ${order.total}"
        )
    except Exception as e:
        return f"Error converting quote to order: {e}"
    finally:
        session.close()
