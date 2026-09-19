from uuid import uuid4

import pytest

from backend.app.services.customer_service import CustomerService
from backend.app.services.exceptions import NotFoundError, ValidationError


class FakeCustomerRepository:
    def __init__(self, customer=None, search_results=None):
        self.customer = customer
        self.search_results = search_results or []
        self.searched_query = None
        self.requested_id = None

    def search(self, query):
        self.searched_query = query
        return self.search_results

    def get_by_id(self, customer_id):
        self.requested_id = customer_id
        return self.customer


class FakeHistoryRepository:
    def __init__(self, results):
        self.results = results
        self.requested_id = None

    def list_by_customer(self, customer_id):
        self.requested_id = customer_id
        return self.results


def make_service(customer=None):
    return CustomerService(
        customer_repository=FakeCustomerRepository(customer=customer),
        order_repository=FakeHistoryRepository(["order"]),
        invoice_repository=FakeHistoryRepository(["invoice"]),
        communication_repository=FakeHistoryRepository(["communication"]),
    )


def test_search_customers_strips_query():
    customer_repository = FakeCustomerRepository(
        search_results=["customer"]
    )

    service = CustomerService(
        customer_repository=customer_repository,
        order_repository=FakeHistoryRepository([]),
        invoice_repository=FakeHistoryRepository([]),
        communication_repository=FakeHistoryRepository([]),
    )

    result = service.search_customers("  Ahmed  ")

    assert result == ["customer"]
    assert customer_repository.searched_query == "Ahmed"


def test_empty_search_query_is_rejected():
    service = make_service()

    with pytest.raises(ValidationError):
        service.search_customers("   ")


def test_get_customer_returns_customer():
    customer_id = uuid4()
    customer = object()
    repository = FakeCustomerRepository(customer=customer)

    service = CustomerService(
        customer_repository=repository,
        order_repository=FakeHistoryRepository([]),
        invoice_repository=FakeHistoryRepository([]),
        communication_repository=FakeHistoryRepository([]),
    )

    assert service.get_customer(customer_id) is customer
    assert repository.requested_id == customer_id


def test_missing_customer_raises_not_found():
    service = make_service(customer=None)

    with pytest.raises(NotFoundError):
        service.get_customer(uuid4())


def test_get_customer_history_returns_all_history():
    customer_id = uuid4()
    customer_repository = FakeCustomerRepository(customer=object())
    order_repository = FakeHistoryRepository(["order"])
    invoice_repository = FakeHistoryRepository(["invoice"])
    communication_repository = FakeHistoryRepository(["communication"])

    service = CustomerService(
        customer_repository=customer_repository,
        order_repository=order_repository,
        invoice_repository=invoice_repository,
        communication_repository=communication_repository,
    )

    result = service.get_customer_history(customer_id)

    assert result == {
        "orders": ["order"],
        "invoices": ["invoice"],
        "communications": ["communication"],
    }

    assert order_repository.requested_id == customer_id
    assert invoice_repository.requested_id == customer_id
    assert communication_repository.requested_id == customer_id

def test_get_order_history_delegates_to_order_repository():
    customer_id = uuid4()
    customer_repository = FakeCustomerRepository(customer=object())
    order_repository = FakeHistoryRepository(["order"])

    service = CustomerService(
        customer_repository=customer_repository,
        order_repository=order_repository,
        invoice_repository=FakeHistoryRepository([]),
        communication_repository=FakeHistoryRepository([]),
    )

    result = service.get_order_history(customer_id)

    assert result == ["order"]
    assert order_repository.requested_id == customer_id

def test_get_invoice_history_delegates_to_invoice_repository():
    customer_id = uuid4()
    invoice_repository = FakeHistoryRepository(["invoice"])

    service = CustomerService(
        customer_repository=FakeCustomerRepository(customer=object()),
        order_repository=FakeHistoryRepository([]),
        invoice_repository=invoice_repository,
        communication_repository=FakeHistoryRepository([]),
    )

    result = service.get_invoice_history(customer_id)

    assert result == ["invoice"]
    assert invoice_repository.requested_id == customer_id

def test_get_communication_history_delegates_to_communication_repository():
    customer_id = uuid4()
    communication_repository = FakeHistoryRepository(["communication"])

    service = CustomerService(
        customer_repository=FakeCustomerRepository(customer=object()),
        order_repository=FakeHistoryRepository([]),
        invoice_repository=FakeHistoryRepository([]),
        communication_repository=communication_repository,
    )

    result = service.get_communication_history(customer_id)

    assert result == ["communication"]
    assert communication_repository.requested_id == customer_id

def test_get_order_history_requires_existing_customer():
    service = make_service(customer=None)

    with pytest.raises(NotFoundError):
        service.get_order_history(uuid4())