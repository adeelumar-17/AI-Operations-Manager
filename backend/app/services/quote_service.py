'''
This module defines the QuoteService, which provides methods for calculating quote totals, discounts, and subtotals based on line items. It also defines the QuoteLineItem dataclass, which represents an individual line item in a quote with its quantity and unit price. The service includes validation to ensure that quantities and prices are valid, and it provides methods to calculate the subtotal, discount amount, and final quote total.
Classes:
    - QuoteLineItem: Represents an individual line item in a quote, with attributes for quantity and unit price, and a method to calculate the line total.
    - QuoteService: Provides methods for managing quotes and line items, including adding, updating, removing, and calculating quote totals and discounts.
Methods:
    - calculate_subtotal: Calculates the subtotal of a list of QuoteLineItem instances.
    - calculate_discount_amount: Calculates the discount amount based on a subtotal and a discount percentage.
    - calculate_quote_total: Calculates the final quote total after applying a discount.
    - add_line_item: Adds a line item to a quote.
    - update_line_item: Updates a line item in a quote.
    - remove_line_item: Removes a line item from a quote.
    - recalculate_quote: Recalculates the quote total after changes to line items.
    - apply_discount: Applies a discount to a quote.
    - convert_to_order: Converts a quote to an order.
'''

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from uuid import UUID

from backend.app.db.models.order import Order
from backend.app.db.models.quote import Quote
from backend.app.db.models.quote_item import QuoteItem
from backend.app.services.authorization_service import (
    check_discount_authorization,
)
from backend.app.services.exceptions import NotFoundError, ValidationError


@dataclass(frozen=True)
class QuoteLineItem:
    quantity: int
    unit_price: Decimal

    def __post_init__(self) -> None:
        if isinstance(self.quantity, bool) or not isinstance(self.quantity, int) or self.quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")

        if not self.unit_price.is_finite() or self.unit_price < Decimal("0"):
            raise ValueError("Unit price cannot be negative.")
        if self.unit_price != self.unit_price.quantize(Decimal("0.01")):
            raise ValueError("Unit price must have at most two decimal places.")

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity


def calculate_subtotal(
    line_items: list[QuoteLineItem],
) -> Decimal:
    return sum(
        (item.line_total for item in line_items),
        Decimal("0.00"),
    )


def calculate_discount_amount(
    subtotal: Decimal,
    discount_percent: Decimal,
) -> Decimal:
    if not subtotal.is_finite() or subtotal < Decimal("0"):
        raise ValueError("Subtotal cannot be negative.")

    if not discount_percent.is_finite() or not Decimal("0") <= discount_percent <= Decimal("100"):
        raise ValueError(
            "Discount percentage must be between 0 and 100."
        )

    return (subtotal * discount_percent / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_quote_total(
    subtotal: Decimal,
    discount_percent: Decimal,
) -> Decimal:
    discount_amount = calculate_discount_amount(
        subtotal=subtotal,
        discount_percent=discount_percent,
    )

    return subtotal - discount_amount


class QuoteService:
    def __init__(
        self,
        quote_repository,
        order_repository,
    ):
        self.quote_repository = quote_repository
        self.order_repository = order_repository

    @staticmethod
    def require_editable(quote):
        if quote.status in {"converted", "expired", "rejected", "pending_approval"}:
            raise ValidationError(f"Cannot edit a {quote.status} quote.")
        expires = getattr(quote, "expires_at", None)
        if expires and expires.replace(tzinfo=expires.tzinfo or timezone.utc) <= datetime.now(timezone.utc):
            raise ValidationError("Quote has expired.")

    def add_line_item(
        self,
        quote_id: UUID,
        product_id: UUID,
        quantity: int,
        unit_price: Decimal,
    ):
        quote = self.quote_repository.get_with_items(quote_id)

        if quote is None:
            raise NotFoundError(f"Quote {quote_id} was not found.")

        line_item = QuoteLineItem(quantity, unit_price)
        self.require_editable(quote)
        quote.status = "draft"
        quote_item = QuoteItem(
            quote_id=quote.id,
            product_id=product_id,
            quantity=line_item.quantity,
            unit_price=line_item.unit_price,
            line_total=line_item.line_total,
        )

        self.quote_repository.add_item(quote_item)
        quote.items.append(quote_item)

        self.recalculate_quote(quote)
        return quote_item

    def update_line_item(
        self,
        quote_id: UUID,
        item_id: UUID,
        quantity: int,
        unit_price: Decimal,
    ):
        quote = self.quote_repository.get_with_items(quote_id)

        if quote is None:
            raise NotFoundError(f"Quote {quote_id} was not found.")

        quote_item = next(
            (item for item in quote.items if item.id == item_id),
            None,
        )

        if quote_item is None:
            raise NotFoundError(f"Quote item {item_id} was not found.")

        line_item = QuoteLineItem(quantity, unit_price)
        self.require_editable(quote)
        quote.status = "draft"
        quote_item.quantity = line_item.quantity
        quote_item.unit_price = line_item.unit_price
        quote_item.line_total = line_item.line_total

        self.quote_repository.update_item(quote_item)
        self.recalculate_quote(quote)

        return quote_item

    def remove_line_item(
        self,
        quote_id: UUID,
        item_id: UUID,
    ):
        quote = self.quote_repository.get_with_items(quote_id)

        if quote is None:
            raise NotFoundError(f"Quote {quote_id} was not found.")

        quote_item = next(
            (item for item in quote.items if item.id == item_id),
            None,
        )

        if quote_item is None:
            raise NotFoundError(f"Quote item {item_id} was not found.")

        self.require_editable(quote)
        quote.status = "draft"
        self.quote_repository.delete_item(quote_item)
        quote.items.remove(quote_item)
        self.recalculate_quote(quote)

        return quote

    def recalculate_quote(
        self,
        quote: Quote,
    ) -> Quote:
        line_items = [
            QuoteLineItem(
                quantity=item.quantity,
                unit_price=item.unit_price,
            )
            for item in quote.items
        ]

        quote.subtotal = calculate_subtotal(line_items)
        quote.discount_amount = calculate_discount_amount(
            subtotal=quote.subtotal,
            discount_percent=quote.discount_percent,
        )
        quote.total = calculate_quote_total(
            subtotal=quote.subtotal,
            discount_percent=quote.discount_percent,
        )

        return self.quote_repository.save(quote)

    def apply_discount(
        self,
        quote_id: UUID,
        discount_percent: Decimal,
        approval_threshold: Decimal = Decimal("10"),
    ) -> Quote:
        quote = self.quote_repository.get_with_items(quote_id)

        if quote is None:
            raise NotFoundError(f"Quote {quote_id} was not found.")

        self.require_editable(quote)
        if not discount_percent.is_finite() or not Decimal("0") <= discount_percent <= Decimal("25"):
            raise ValidationError(
                "Discount percentage must be between 0 and 25 under OfficeHub policy."
            )
        if discount_percent != discount_percent.quantize(Decimal("0.01")):
            raise ValidationError("Discount must have at most two decimal places.")

        authorization = check_discount_authorization(
            discount_percent=discount_percent,
            approval_threshold=approval_threshold,
        )

        quote.discount_percent = discount_percent
        quote = self.recalculate_quote(quote)

        if authorization.approval_required:
            quote.status = "pending_approval"
            quote = self.quote_repository.save(quote)
        else:
            quote.status = "approved"
            quote.approval_id = None
            quote = self.quote_repository.save(quote)

        return quote

    def convert_to_order(
        self,
        quote_id: UUID,
    ) -> Order:
        quote = self.quote_repository.get_with_items(quote_id)

        if quote is None:
            raise NotFoundError(f"Quote {quote_id} was not found.")

        if quote.status != "approved":
            raise ValidationError(
                "Only approved quotes can be converted to orders."
            )
        self.require_editable(quote)

        if not quote.items:
            raise ValidationError("Cannot convert an empty quote.")

        order = self.order_repository.create_from_quote(quote)
        quote.status = "converted"
        self.quote_repository.save(quote)

        return order
