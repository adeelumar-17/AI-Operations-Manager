from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.app.services.quote_service import (
    QuoteLineItem,
    QuoteService,
    calculate_discount_amount,
    calculate_quote_total,
    calculate_subtotal,
)


def test_calculate_subtotal():
    items = [
        QuoteLineItem(2, Decimal("100.00")),
        QuoteLineItem(3, Decimal("50.00")),
    ]

    assert calculate_subtotal(items) == Decimal("350.00")


def test_empty_quote_has_zero_subtotal():
    assert calculate_subtotal([]) == Decimal("0.00")


def test_calculate_discount_amount():
    result = calculate_discount_amount(
        subtotal=Decimal("1000.00"),
        discount_percent=Decimal("10"),
    )

    assert result == Decimal("100.00")

    assert calculate_discount_amount(
        Decimal("100.00"),
        Decimal("0"),
    ) == Decimal("0.00")

    assert calculate_discount_amount(
        Decimal("100.00"),
        Decimal("100"),
    ) == Decimal("100.00")


def test_calculate_quote_total():
    result = calculate_quote_total(
        subtotal=Decimal("1000.00"),
        discount_percent=Decimal("10"),
    )

    assert result == Decimal("900.00")


def test_invalid_line_item_quantity_is_rejected():
    with pytest.raises(ValueError):
        QuoteLineItem(
            quantity=0,
            unit_price=Decimal("10.00"),
        )


class FakeQuoteRepository:
    def __init__(self, quote=None):
        self.quote = quote
        self.saved_quote = None
        self.added_item = None
        self.updated_item = None
        self.deleted_item = None

    def get_by_id(self, quote_id):
        return self.quote

    def get_with_items(self, quote_id):
        return self.quote

    def add_item(self, item):
        self.added_item = item
        return item

    def update_item(self, item):
        self.updated_item = item
        return item

    def delete_item(self, item):
        self.deleted_item = item

    def save(self, quote):
        self.saved_quote = quote
        return quote


class FakeOrderRepository:
    def __init__(self, order=None):
        self.order = order
        self.received_quote = None

    def create_from_quote(self, quote):
        self.received_quote = quote
        return self.order

    def get_received_quote(self):
        return self.received_quote


def test_approved_quote_converts_to_order():
    quote = SimpleNamespace(
        id=uuid4(),
        quote_number="Q-1001",
        customer_id=uuid4(),
        status="approved",
        subtotal=Decimal("200.00"),
        discount_percent=Decimal("0"),
        discount_amount=Decimal("0.00"),
        total=Decimal("200.00"),
        items=[],
    )

    expected_order = object()
    quote_repository = FakeQuoteRepository(quote=quote)
    order_repository = FakeOrderRepository(order=expected_order)

    service = QuoteService(
        quote_repository=quote_repository,
        order_repository=order_repository,
    )

    result = service.convert_to_order(quote.id)

    assert result is expected_order
    assert order_repository.received_quote is quote
    assert quote.status == "converted"
    assert quote_repository.saved_quote is quote


def test_discount_above_threshold_requires_quote_approval():
    quote = SimpleNamespace(
        id=uuid4(),
        status="draft",
        subtotal=Decimal("100.00"),
        discount_percent=Decimal("0"),
        discount_amount=Decimal("0.00"),
        total=Decimal("100.00"),
        items=[],
    )
    quote_repository = FakeQuoteRepository(quote=quote)
    service = QuoteService(
        quote_repository=quote_repository,
        order_repository=FakeOrderRepository(),
    )

    result = service.apply_discount(
        quote_id=quote.id,
        discount_percent=Decimal("10.01"),
        approval_threshold=Decimal("10"),
    )

    assert result.status == "pending_approval"
    assert quote_repository.saved_quote is quote