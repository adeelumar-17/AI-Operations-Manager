from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.app.services.communication_service import CommunicationService
from backend.app.services.exceptions import NotFoundError, ValidationError


class FakeCustomerRepository:
    def __init__(self, customer=None):
        self.customer = customer

    def get_by_id(self, customer_id):
        return self.customer

class FakeCommunicationRepository:
    def __init__(self, communication=None, history=None):
        self.communication = communication
        self.history = history or []
        self.created_arguments = None
        self.saved_communication = None

    def create(
        self,
        customer_id,
        communication_type,
        direction,
        subject=None,
        body=None,
        related_entity_type=None,
        related_entity_id=None,
    ):
        self.created_arguments = {
            "customer_id": customer_id,
            "type": communication_type,
            "direction": direction,
            "subject": subject,
            "body": body,
            "related_entity_type": related_entity_type,
            "related_entity_id": related_entity_id,
        }
        return self.communication

    def get_by_id(self, communication_id):
        return self.communication

    def list_by_customer(
        self,
        customer_id,
        communication_type=None,
        direction=None,
        status=None,
    ):
        return self.history

    def save(self, communication):
        self.saved_communication = communication
        return communication


def make_service(customer=object(), communication=None, history=None):
    customer_repository = FakeCustomerRepository(customer)
    communication_repository = FakeCommunicationRepository(
        communication=communication,
        history=history,
    )
    service = CommunicationService(
        communication_repository=communication_repository,
        customer_repository=customer_repository,
    )
    return service, customer_repository, communication_repository


def test_record_communication_creates_pending_record():
    customer_id = uuid4()
    communication = SimpleNamespace(status="pending", sent_at=None)
    service, _, repository = make_service(communication=communication)

    result = service.record_communication(
        customer_id=customer_id,
        communication_type="email",
        direction="outbound",
        subject="Update",
        body="Your order has shipped.",
    )

    assert result is communication
    assert repository.created_arguments["customer_id"] == customer_id
    assert repository.created_arguments["type"] == "email"


def test_record_communication_requires_existing_customer():
    service, _, _ = make_service(customer=None)

    with pytest.raises(NotFoundError):
        service.record_communication(
            uuid4(), "note", "inbound", body="A note"
        )


def test_record_communication_rejects_invalid_type():
    service, _, _ = make_service()

    with pytest.raises(ValidationError):
        service.record_communication(
            uuid4(), "push", "outbound", body="Unsupported"
        )


def test_record_communication_requires_body_for_note():
    service, _, _ = make_service()

    with pytest.raises(ValidationError):
        service.record_communication(uuid4(), "note", "outbound")


def test_record_communication_requires_related_entity_pair():
    service, _, _ = make_service()

    with pytest.raises(ValidationError):
        service.record_communication(
            uuid4(),
            "call",
            "outbound",
            related_entity_type="order",
        )


def test_history_delegates_filters_to_repository():
    customer_id = uuid4()
    service, _, repository = make_service(history=["communication"])

    result = service.get_communication_history(
        customer_id,
        communication_type="email",
        direction="outbound",
        status="sent",
    )

    assert result == ["communication"]
    assert repository is not None


def test_mark_sent_sets_status_and_timestamp():
    sent_at = datetime(2026, 9, 10, 12, 0)
    communication = SimpleNamespace(status="pending", sent_at=None)
    service, _, repository = make_service(communication=communication)

    result = service.mark_sent(uuid4(), sent_at)

    assert result is communication
    assert communication.status == "sent"
    assert communication.sent_at == sent_at
    assert repository.saved_communication is communication


def test_mark_failed_sets_failed_status_and_clears_timestamp():
    communication = SimpleNamespace(
        status="pending",
        sent_at=datetime(2026, 9, 10, 12, 0),
    )
    service, _, _ = make_service(communication=communication)

    service.mark_failed(uuid4())

    assert communication.status == "failed"
    assert communication.sent_at is None


def test_sent_communication_cannot_be_marked_failed():
    communication = SimpleNamespace(status="sent", sent_at=datetime.now())
    service, _, _ = make_service(communication=communication)

    with pytest.raises(ValidationError):
        service.mark_failed(uuid4())