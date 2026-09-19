from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from backend.app.services.exceptions import NotFoundError, ValidationError
from backend.app.services.invoice_service import (
    InvoiceService,
    calculate_days_overdue,
    calculate_invoice_status,
    calculate_total_paid,
)


class SimpleNamespace:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

class FakeInvoiceRepository:
    def __init__(self, invoice=None):
        self.invoice = invoice
        self.saved_invoice = None

    def get_with_payments(self, invoice_id):
        return self.invoice

    def save(self, invoice):
        self.saved_invoice = invoice
        return invoice

class FakePaymentRepository:
    def __init__(self, payment=None):
        self.payment = payment
        self.created_arguments = None

    def create(
        self,
        invoice_id,
        amount,
        method,
        reference=None,
        paid_at=None,
    ):
        self.created_arguments = {
            "invoice_id": invoice_id,
            "amount": amount,
            "method": method,
            "reference": reference,
            "paid_at": paid_at,
        }
        return self.payment


def make_invoice(
    amount=Decimal("100.00"),
    due_date=date(2026, 9, 8),
    status="sent",
    payments=None,
):
    return SimpleNamespace(
        id=uuid4(),
        amount=amount,
        due_date=due_date,
        status=status,
        paid_date=None,
        payments=payments or [],
    )


def make_service(invoice, payment=None):
    invoice_repository = FakeInvoiceRepository(invoice)
    payment_repository = FakePaymentRepository(payment)
    service = InvoiceService(invoice_repository, payment_repository)
    return service, invoice_repository, payment_repository


def test_calculate_total_paid_uses_decimal_values():
    payments = [
        SimpleNamespace(amount=Decimal("25.00")),
        SimpleNamespace(amount=Decimal("10.50")),
    ]

    assert calculate_total_paid(payments) == Decimal("35.50")


def test_due_today_is_not_overdue():
    assert calculate_days_overdue(
        date(2026, 9, 8), date(2026, 9, 8)
    ) == 0


def test_future_due_date_is_not_overdue():
    assert calculate_days_overdue(
        date(2026, 9, 10), date(2026, 9, 8)
    ) == 0


def test_one_day_overdue_is_calculated():
    assert calculate_days_overdue(
        date(2026, 9, 7), date(2026, 9, 8)
    ) == 1


def test_status_is_paid_when_payment_equals_amount():
    assert calculate_invoice_status(
        Decimal("100.00"),
        Decimal("100.00"),
        date(2026, 9, 1),
        "sent",
        date(2026, 9, 8),
    ) == "paid"


def test_status_is_partially_paid_before_due_date():
    assert calculate_invoice_status(
        Decimal("100.00"),
        Decimal("25.00"),
        date(2026, 9, 10),
        "sent",
        date(2026, 9, 8),
    ) == "partially_paid"


def test_status_is_overdue_after_due_date():
    assert calculate_invoice_status(
        Decimal("100.00"),
        Decimal("25.00"),
        date(2026, 9, 7),
        "sent",
        date(2026, 9, 8),
    ) == "overdue"


def test_cancelled_status_is_preserved():
    assert calculate_invoice_status(
        Decimal("100.00"),
        Decimal("0.00"),
        date(2026, 9, 1),
        "cancelled",
        date(2026, 9, 8),
    ) == "cancelled"


def test_get_invoice_raises_for_missing_invoice():
    service, _, _ = make_service(None)

    with pytest.raises(NotFoundError):
        service.get_invoice(uuid4())


def test_refresh_status_saves_paid_invoice():
    invoice = make_invoice(
        due_date=date(2026, 9, 1),
        payments=[SimpleNamespace(amount=Decimal("100.00"))],
    )
    service, invoice_repository, _ = make_service(invoice)

    result = service.refresh_status(invoice.id, date(2026, 9, 8))

    assert result is invoice
    assert invoice.status == "paid"
    assert invoice.paid_date == date(2026, 9, 8)
    assert invoice_repository.saved_invoice is invoice


def test_record_payment_rejects_overpayment():
    invoice = make_invoice()
    service, _, _ = make_service(invoice)

    with pytest.raises(ValidationError):
        service.record_payment(invoice.id, Decimal("100.01"), "card")


def test_record_payment_creates_payment_and_updates_status():
    invoice = make_invoice()
    payment = SimpleNamespace(amount=Decimal("100.00"))
    service, invoice_repository, payment_repository = make_service(
        invoice,
        payment,
    )

    paid_at = datetime(2026, 9, 8, 12, 0)
    result = service.record_payment(
        invoice.id,
        Decimal("100.00"),
        "card",
        paid_at=paid_at,
        as_of=date(2026, 9, 8),
    )

    assert result is payment
    assert payment_repository.created_arguments["paid_at"] == paid_at
    assert invoice.status == "paid"
    assert invoice_repository.saved_invoice is invoice