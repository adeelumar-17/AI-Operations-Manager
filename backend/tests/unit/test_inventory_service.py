from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.app.services.inventory_service import (
    InventoryService,
    check_fulfillment_feasibility,
)
from backend.app.services.exceptions import (
    InsufficientStockError,
    NotFoundError,
    ValidationError,
)


def test_fulfillment_is_feasible_when_stock_is_enough():
    result = check_fulfillment_feasibility(
        available_quantity=10,
        requested_quantity=7,
    )

    assert result.feasible is True
    assert result.shortage_quantity == 0


def test_fulfillment_is_not_feasible_when_stock_is_insufficient():
    result = check_fulfillment_feasibility(
        available_quantity=5,
        requested_quantity=8,
    )

    assert result.feasible is False
    assert result.shortage_quantity == 3


def test_negative_stock_is_rejected():
    with pytest.raises(ValueError):
        check_fulfillment_feasibility(
            available_quantity=-1,
            requested_quantity=2,
        )


def test_zero_requested_quantity_is_rejected():
    with pytest.raises(ValueError):
        check_fulfillment_feasibility(
            available_quantity=10,
            requested_quantity=0,
        )

class FakeProductRepository:
    def __init__(self, product=None, low_stock_products=None):
        self.product = product
        self.low_stock_products = low_stock_products or []
        self.saved_product = None
        self.requested_id = None

    def get_by_id(self, product_id):
        self.requested_id = product_id
        return self.product

    def list_low_stock(self):
        return self.low_stock_products

    def save(self, product):
        self.saved_product = product
        return product


class FakeInventoryRepository:
    def __init__(self):
        self.recorded_change = None

    def record_change(
        self,
        product_id,
        change_quantity,
        reason,
        resulting_balance,
        reference_type=None,
        reference_id=None,
    ):
        self.recorded_change = {
            "product_id": product_id,
            "change_quantity": change_quantity,
            "reason": reason,
            "resulting_balance": resulting_balance,
            "reference_type": reference_type,
            "reference_id": reference_id,
        }

        return self.recorded_change


def make_inventory_service(product):
    product_repository = FakeProductRepository(product=product)
    inventory_repository = FakeInventoryRepository()

    service = InventoryService(
        product_repository=product_repository,
        inventory_repository=inventory_repository,
    )

    return service, product_repository, inventory_repository


def test_check_stock_returns_true_when_stock_is_sufficient():
    product_id = uuid4()
    product = SimpleNamespace(id=product_id, stock_quantity=10)
    service, _, _ = make_inventory_service(product)

    assert service.check_stock(product_id, 7) is True


def test_check_stock_returns_false_when_stock_is_insufficient():
    product_id = uuid4()
    product = SimpleNamespace(id=product_id, stock_quantity=5)
    service, _, _ = make_inventory_service(product)

    assert service.check_stock(product_id, 8) is False


def test_list_low_stock_delegates_to_product_repository():
    low_stock_product = object()
    product_repository = FakeProductRepository(
        low_stock_products=[low_stock_product]
    )
    inventory_repository = FakeInventoryRepository()
    service = InventoryService(product_repository, inventory_repository)

    assert service.list_low_stock() == [low_stock_product]


def test_update_inventory_increases_stock_and_records_change():
    product_id = uuid4()
    product = SimpleNamespace(id=product_id, stock_quantity=10)
    service, product_repository, inventory_repository = make_inventory_service(
        product
    )

    result = service.update_inventory(
        product_id=product_id,
        change_quantity=5,
        reason="restock",
    )

    assert product.stock_quantity == 15
    assert product_repository.saved_product is product
    assert inventory_repository.recorded_change["resulting_balance"] == 15
    assert result == inventory_repository.recorded_change


def test_update_inventory_decreases_stock():
    product_id = uuid4()
    product = SimpleNamespace(id=product_id, stock_quantity=10)
    service, _, inventory_repository = make_inventory_service(product)

    service.update_inventory(
        product_id=product_id,
        change_quantity=-4,
        reason="order_fulfilled",
    )

    assert product.stock_quantity == 6
    assert inventory_repository.recorded_change["resulting_balance"] == 6


def test_update_inventory_rejects_negative_resulting_balance():
    product_id = uuid4()
    product = SimpleNamespace(id=product_id, stock_quantity=2)
    service, _, _ = make_inventory_service(product)

    with pytest.raises(InsufficientStockError):
        service.update_inventory(
            product_id=product_id,
            change_quantity=-3,
            reason="order_fulfilled",
        )


def test_update_inventory_rejects_zero_change():
    product_id = uuid4()
    product = SimpleNamespace(id=product_id, stock_quantity=2)
    service, _, _ = make_inventory_service(product)

    with pytest.raises(ValidationError):
        service.update_inventory(
            product_id=product_id,
            change_quantity=0,
            reason="manual_adjustment",
        )


def test_check_stock_rejects_missing_product():
    product_id = uuid4()
    service, _, _ = make_inventory_service(product=None)

    with pytest.raises(NotFoundError):
        service.check_stock(product_id, 1)