from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.app.services.exceptions import (
    InsufficientStockError,
    InvalidStatusTransitionError,
    NotFoundError,
)
from backend.app.services.order_service import OrderService


class FakeOrderRepository:
    def __init__(self, order=None):
        self.order = order
        self.saved_order = None

    def get_with_items(self, order_id):
        return self.order

    def save(self, order):
        self.saved_order = order
        return order


class FakeInventoryService:
    def __init__(self, available=True):
        self.available = available
        self.checked_items = []
        self.updated_items = []

    def check_stock(self, product_id, requested_quantity):
        self.checked_items.append((product_id, requested_quantity))
        return self.available

    def update_inventory(
        self,
        product_id,
        change_quantity,
        reason,
        reference_type=None,
        reference_id=None,
    ):
        self.updated_items.append(
            {
                "product_id": product_id,
                "change_quantity": change_quantity,
                "reason": reason,
                "reference_type": reference_type,
                "reference_id": reference_id,
            }
        )


def make_order(status="pending", items=None):
    return SimpleNamespace(
        id=uuid4(),
        status=status,
        subtotal=Decimal("35.00"),
        total=Decimal("35.00"),
        shipped_at=None,
        delivered_at=None,
        items=items or [],
    )


def make_item(quantity=2, unit_price=Decimal("10.00")):
    return SimpleNamespace(
        id=uuid4(),
        product_id=uuid4(),
        quantity=quantity,
        unit_price=unit_price,
        line_total=unit_price * quantity,
    )


def make_service(order, available=True):
    order_repository = FakeOrderRepository(order)
    inventory_service = FakeInventoryService(available)
    service = OrderService(order_repository, inventory_service)
    return service, order_repository, inventory_service


def test_get_order_returns_order():
    order = make_order()
    service, _, _ = make_service(order)

    assert service.get_order(order.id) is order


def test_missing_order_raises_not_found():
    service, _, _ = make_service(None)

    with pytest.raises(NotFoundError):
        service.get_order(uuid4())


def test_pending_order_moves_to_processing():
    order = make_order()
    service, repository, _ = make_service(order)

    result = service.transition_status(order.id, "processing")

    assert result is order
    assert order.status == "processing"
    assert repository.saved_order is order


def test_invalid_status_transition_is_rejected():
    order = make_order(status="delivered")
    service, _, _ = make_service(order)

    with pytest.raises(InvalidStatusTransitionError):
        service.transition_status(order.id, "processing")


def test_fulfillment_checks_and_deducts_each_item():
    first_item = make_item(quantity=2)
    second_item = make_item(quantity=3)
    order = make_order(items=[first_item, second_item])
    service, repository, inventory = make_service(order)

    result = service.fulfill_order(order.id)

    assert result is order
    assert order.status == "processing"
    assert inventory.checked_items == [
        (first_item.product_id, 2),
        (second_item.product_id, 3),
    ]
    assert inventory.updated_items == [
        {
            "product_id": first_item.product_id,
            "change_quantity": -2,
            "reason": "order_fulfilled",
            "reference_type": "order",
            "reference_id": order.id,
        },
        {
            "product_id": second_item.product_id,
            "change_quantity": -3,
            "reason": "order_fulfilled",
            "reference_type": "order",
            "reference_id": order.id,
        },
    ]
    assert repository.saved_order is order


def test_fulfillment_rejects_insufficient_stock_before_updates():
    item = make_item()
    order = make_order(items=[item])
    service, _, inventory = make_service(order, available=False)

    with pytest.raises(InsufficientStockError):
        service.fulfill_order(order.id)

    assert inventory.updated_items == []


def test_fulfillment_cannot_run_twice():
    order = make_order(status="processing", items=[make_item()])
    service, _, _ = make_service(order)

    with pytest.raises(InvalidStatusTransitionError):
        service.fulfill_order(order.id)


def test_pending_order_can_be_cancelled_without_inventory_update():
    order = make_order(items=[make_item()])
    service, repository, inventory = make_service(order)

    result = service.cancel_order(order.id)

    assert result is order
    assert order.status == "cancelled"
    assert inventory.updated_items == []
    assert repository.saved_order is order


def test_processing_order_cannot_be_cancelled():
    order = make_order(status="processing")
    service, _, _ = make_service(order)

    with pytest.raises(InvalidStatusTransitionError):
        service.cancel_order(order.id)


def test_order_subtotal_is_calculated_from_items():
    items = [
        make_item(2, Decimal("10.00")),
        make_item(3, Decimal("5.00")),
    ]

    assert OrderService.calculate_order_subtotal(items) == Decimal("35.00")
