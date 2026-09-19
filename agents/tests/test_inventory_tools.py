from types import SimpleNamespace
from uuid import uuid4
from agents.tools.inventory_tools import _find_product


class FakeProductRepo:
    def __init__(self, product):
        self.product = product

    def get_by_id(self, pid):
        if self.product and self.product.id == pid:
            return self.product
        return None

    def get_by_sku(self, sku):
        if self.product and self.product.sku.lower() == sku.lower():
            return self.product
        return None

    def search_by_name_or_sku(self, query):
        if self.product and (
            query.lower() in self.product.name.lower()
            or query.lower() in self.product.sku.lower()
        ):
            return [self.product]
        return []


def test_find_product_by_uuid():
    pid = uuid4()
    p = SimpleNamespace(id=pid, sku="SKU-100", name="Desk", stock_quantity=10)
    repo = FakeProductRepo(p)
    assert _find_product(repo, str(pid)) == p


def test_find_product_by_sku():
    pid = uuid4()
    p = SimpleNamespace(id=pid, sku="SKU-100", name="Desk", stock_quantity=10)
    repo = FakeProductRepo(p)
    assert _find_product(repo, "SKU-100") == p


def test_find_product_by_name():
    pid = uuid4()
    p = SimpleNamespace(id=pid, sku="SKU-100", name="Desk Pro", stock_quantity=10)
    repo = FakeProductRepo(p)
    assert _find_product(repo, "Desk Pro") == p


def test_find_product_handles_malformed_uuid_gracefully():
    pid = uuid4()
    p = SimpleNamespace(id=pid, sku="SKU-1234", name="Chair", stock_quantity=10)
    repo = FakeProductRepo(p)
    # Malformed UUID strings must not raise ValueError
    assert _find_product(repo, "not-a-uuid") is None
    assert _find_product(repo, "SKU-1234") == p
