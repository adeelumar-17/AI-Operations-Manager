"""Quote creation, approval policy and fulfillment regressions."""
import json
from decimal import Decimal
from uuid import UUID, uuid4
from unittest.mock import Mock
import pytest
from sqlalchemy import select, func
from pydantic import ValidationError as SchemaError
from backend.app.db.models import Customer, Product, Quote, Order, Inventory
from backend.app.services.exceptions import ApprovalRequired


def seed(sessions):
    with sessions() as db:
        customer = Customer(id=uuid4(), name="Ahmed Industries", email="ahmed@test.local", notes="Regular customer tier.")
        product = Product(id=uuid4(), name="Ergonomic Chair", sku="CHAIR-1", category="Office",
                          unit_price=Decimal("249.99"), stock_quantity=30, reorder_threshold=2)
        db.add_all([customer, product]); db.commit()
        return customer.id, product.id


def wire(database, monkeypatch):
    from agents.tools import customer_tools, order_tools
    monkeypatch.setattr(customer_tools, "SessionLocal", database)
    monkeypatch.setattr(order_tools, "SessionLocal", database)


@pytest.mark.parametrize("identifier", ["name", "email", "uuid"])
def test_create_quote_resolves_customer_and_uses_catalog_price(database, monkeypatch, identifier):
    from agents.tools.quote_tools import create_quote
    customer_id, product_id = seed(database)
    wire(database, monkeypatch)
    customer = {"name": "Ahmed Industries", "email": "ahmed@test.local", "uuid": str(customer_id)}[identifier]
    product = {"name": "Ergonomic Chair", "email": "CHAIR-1", "uuid": str(product_id)}[identifier]
    result = json.loads(create_quote.invoke({"customer_identifier": customer,
        "items": [{"product_identifier": product, "quantity": 20}]}))
    with database() as db:
        quote = db.get(Quote, UUID(result["quote_id"]))
        assert quote.customer_id == customer_id
        assert quote.total == Decimal("4999.80")
        assert quote.status == "draft"
        assert quote.discount_percent == 0
        assert len(quote.items) == 1
        assert quote.items[0].unit_price == Decimal("249.99")
        assert db.get(Product, product_id).stock_quantity == 30


@pytest.mark.parametrize("quantity", [0, -1, 1.5, True])
def test_invalid_quantities_do_not_create_quotes(database, monkeypatch, quantity):
    from agents.tools.quote_tools import create_quote
    seed(database); wire(database, monkeypatch)
    with pytest.raises(SchemaError):
        create_quote.invoke({"customer_identifier": "Ahmed Industries",
                            "items": [{"product_identifier": "CHAIR-1", "quantity": quantity}]})
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Quote)) == 0


def test_missing_later_product_does_not_persist_partial_quote(database, monkeypatch):
    from agents.tools.quote_tools import create_quote
    seed(database); wire(database, monkeypatch)
    result = create_quote.invoke({"customer_identifier": "Ahmed Industries", "items": [
        {"product_identifier": "CHAIR-1", "quantity": 1}, {"product_identifier": "MISSING", "quantity": 1}]})
    assert result.startswith("Error creating quote:")
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Quote)) == 0


def test_ambiguous_customer_does_not_pick_first_match(database, monkeypatch):
    from agents.tools.quote_tools import create_quote
    seed(database); wire(database, monkeypatch)
    with database() as db:
        db.add(Customer(id=uuid4(), name="Ahmed Trading")); db.commit()
    result = create_quote.invoke({"customer_identifier": "Ahmed", "items": [{"product_identifier": "CHAIR-1", "quantity": 1}]})
    assert "Ambiguous customer" in result


def test_quote_node_exposes_canonical_id_in_existing_entities(database, monkeypatch):
    from langchain_core.messages import AIMessage
    from agents.graph.nodes import create_quote_node as node
    seed(database); wire(database, monkeypatch)
    llm = Mock()
    llm.bind_tools.return_value = llm
    llm.invoke.side_effect = [AIMessage(content="", tool_calls=[{
        "id": "create-1", "name": "create_quote", "args": {"customer_identifier": "Ahmed Industries",
        "items": [{"product_identifier": "CHAIR-1", "quantity": 20}]}}]), AIMessage(content="Created")]
    monkeypatch.setattr(node, "get_llm", lambda: llm)
    result = node.create_quote_node({"request_id": str(uuid4()), "user_input": "Create a quote", "entities": {}},
                                    {"configurable": {"thread_id": str(uuid4())}})
    canonical_id = result["entities"]["quote_id"]
    with database() as db:
        assert db.get(Quote, UUID(canonical_id)).total == Decimal("4999.80")


def test_discount_uses_shared_authorization_and_fulfillment_deducts_stock(database, monkeypatch):
    from agents.tools import quote_tools, order_tools
    from backend.app.services.authorization_service import check_discount_authorization
    _, product_id = seed(database); wire(database, monkeypatch)
    monkeypatch.setattr(quote_tools, "SessionLocal", database)
    spy = Mock(wraps=check_discount_authorization)
    monkeypatch.setattr(quote_tools, "check_discount_authorization", spy)
    created = json.loads(quote_tools.create_quote.invoke({"customer_identifier": "Ahmed Industries",
                        "items": [{"product_identifier": "CHAIR-1", "quantity": 20}]}))
    with pytest.raises(ApprovalRequired):
        quote_tools.apply_discount_to_quote.invoke({"quote_id": created["quote_id"], "discount_percent": 15})
    spy.assert_called_with(Decimal("15"), Decimal("10"))
    # A permitted discount makes this quote eligible for conversion.
    assert "Discount applied" in quote_tools.apply_discount_to_quote.invoke({"quote_id": created["quote_id"], "discount_percent": 10})
    assert "converted to order" in quote_tools.convert_quote_to_order.invoke({"quote_id": created["quote_id"]})
    with database() as db:
        order_id = db.scalar(select(Order.id))
        assert db.get(Product, product_id).stock_quantity == 30
    assert "fulfilled" in order_tools.fulfill_order.invoke({"order_id": str(order_id)})
    with database() as db:
        assert db.get(Product, product_id).stock_quantity == 10
        assert db.get(Order, order_id).status == "processing"
        ledger = db.scalars(select(Inventory).where(Inventory.reference_id == order_id)).one()
        assert ledger.change_quantity == -20
        assert ledger.resulting_balance == 10
    assert "Error fulfilling" in order_tools.fulfill_order.invoke({"order_id": str(order_id)})
    with database() as db:
        assert db.get(Product, product_id).stock_quantity == 10
