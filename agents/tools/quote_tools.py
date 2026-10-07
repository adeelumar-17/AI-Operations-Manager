'''
what the file does?
This module provides LangChain-compatible quote management tools for the operations agent, delegating to QuoteService to retrieve quote details, apply discount percentages, and convert accepted quotes into finalized orders.

Classes:
    None (LangChain tool definition module)

Methods:
    create_quote: Tool to create a new draft from customer/product identifiers and catalog prices.
    _make_quote_service: Helper factory creating a QuoteService instance with a fresh DB session.
    get_quote: Tool to retrieve a quote and its constituent line items by quote ID.
    apply_discount_to_quote: Tool to apply a percentage discount to an existing quote, returning discount details.
    convert_quote_to_order: Tool to convert an approved quote directly into a new customer order.
'''

import logging
import json
from decimal import Decimal
from typing import Annotated
from uuid import UUID
from pydantic import BaseModel, Field, StrictInt


from langchain_core.tools import tool

from backend.app.db.database import SessionLocal
from backend.app.db.repositories.order_repository import OrderRepository
from backend.app.db.repositories.quote_repository import QuoteRepository
from backend.app.db.repositories.product_repository import ProductRepository
from backend.app.services.quote_service import QuoteService
from backend.app.services.authorization_service import discount_limit, check_discount_authorization
from backend.app.services.exceptions import ApprovalRequired, ValidationError
from agents.tools.customer_tools import _make_customer_service
from agents.tools.inventory_tools import _find_product

logger = logging.getLogger(__name__)


class QuoteCreationItem(BaseModel):
    product_identifier: str = Field(..., description="Product UUID, exact SKU, or product name")
    quantity: StrictInt = Field(..., gt=0, description="Positive whole number of units")


def _make_quote_service() -> tuple[QuoteService, object]:
    session = SessionLocal()
    service = QuoteService(
        quote_repository=QuoteRepository(session),
        order_repository=OrderRepository(session),
    )
    return service, session


@tool
def create_quote(
    customer_identifier: Annotated[str, "Customer name, email, company name, or UUID"],
    items: Annotated[list[QuoteCreationItem], "Items with product_identifier and positive integer quantity; prices come from the database"],
) -> str:
    """Create a new draft quote using stored catalog prices and service calculations.

    Resolve ambiguous customers/products by asking for a UUID/SKU; never guess.
    Returns JSON with quote_id, quote_number, customer_id, exact totals and items.
    Creation neither applies discounts nor deducts stock. Use the returned ID in
    subsequent discount, approval or explicit order-conversion requests.
    """
    customers, session = _make_customer_service()
    try:
        identifier = customer_identifier.strip()
        try:
            customer_id = UUID(identifier)
        except ValueError:
            matches = customers.search_customers(identifier)
            if len(matches) != 1:
                if not matches:
                    raise ValidationError(f"Customer '{identifier}' not found.")
                raise ValidationError("Ambiguous customer. Specify a customer UUID: " +
                                      ", ".join(f"{c.name} ({c.id})" for c in matches))
            customer = matches[0]
        else:
            customer = customers.get_customer(customer_id)
        products = ProductRepository(session)
        resolved = []
        for item in items:
            product = _find_product(products, item.product_identifier)
            if product is None:
                raise ValidationError(f"Product '{item.product_identifier}' not found.")
            resolved.append((product, item.quantity))
        service = QuoteService(QuoteRepository(session), customers.order_repository)
        quote = service.create_quote(customer.id, [
            (product.id, quantity, product.unit_price) for product, quantity in resolved
        ])
        session.commit()
        return json.dumps({
            "success": True, "quote_id": str(quote.id), "quote_number": quote.quote_number,
            "customer_id": str(customer.id), "customer_name": customer.name, "status": quote.status,
            "subtotal": str(quote.subtotal), "discount_percent": str(quote.discount_percent),
            "discount_amount": str(quote.discount_amount), "total": str(quote.total),
            "items": [{"product_id": str(product.id), "sku": product.sku,
                       "product_name": product.name, "quantity": quantity,
                       "unit_price": str(product.unit_price)} for product, quantity in resolved],
        })
    except Exception as exc:
        session.rollback()
        logger.exception("Quote creation failed")
        return f"Error creating quote: {exc}"
    finally:
        session.close()


@tool
def get_quote(
    quote_id: Annotated[str, "UUID of the quote to retrieve"],
) -> str:
    """Retrieve a quote and its line items by ID.

    Returns quote number, customer, status, line items, subtotal, discount, and total.
    """
    service, session = _make_quote_service()
    try:
        quote = service.quote_repository.get_with_items(quote_id)
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
        logger.exception('Operation failed')
        return f"Error retrieving quote: {e}"
    finally:
        session.close()


@tool
def apply_discount_to_quote(
    quote_id: Annotated[str, "UUID of the quote"],
    discount_percent: Annotated[float, "Discount percentage (0-25) to apply under OfficeHub policy"],
) -> str:
    """Apply a discount percentage to a quote.

    Returns the updated totals. If the discount exceeds the approval threshold,
    the quote status becomes 'pending_approval' — the caller MUST surface this
    to the user and NOT proceed without approval.

    Customer policy limits are resolved by Python from the stored customer record.
    """
    service, session = _make_quote_service()
    try:
        existing = service.quote_repository.get_with_items(quote_id)
        if existing is None:
            raise ValidationError("Quote not found.")
        service.require_editable(existing)
        percent = Decimal(str(discount_percent))
        if not percent.is_finite() or not Decimal("0") <= percent <= Decimal("25"):
            raise ValidationError("Discount must be between 0 and 25 percent.")
        if percent != percent.quantize(Decimal("0.01")):
            raise ValidationError("Discount must have at most two decimal places.")
        threshold = discount_limit(existing.customer)
        decision = check_discount_authorization(percent, threshold)
        if decision.approval_required:
            raise ApprovalRequired("quote_discount_approval", {
                "quote_id": str(existing.id), "discount_percent": str(percent),
                "previous_status": existing.status,
                "subtotal": str(existing.subtotal), "total": str(existing.total),
            }, decision.reason)
        quote = service.apply_discount(
            quote_id=existing.id,
            discount_percent=percent,
            approval_threshold=threshold,
        )
        session.commit()
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
    except ApprovalRequired:
        raise
    except Exception as e:
        logger.exception('Operation failed')
        session.rollback()
        logger.exception("Discount application failed")
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
        order = service.convert_to_order(quote_id)
        session.commit()
        return (
            f"✓ Quote converted to order successfully.\n"
            f"  Order number: {order.order_number}\n"
            f"  Order ID: {order.id}\n"
            f"  Total: ${order.total}"
        )
    except Exception as e:
        logger.exception('Operation failed')
        return f"Error converting quote to order: {e}"
    finally:
        session.close()
