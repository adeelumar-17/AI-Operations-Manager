'''
This module provides functions for calculating the status of invoices.

Classes:
    InvoiceService
Methods:
    calculate_total_paid: Calculates the total amount paid for a list of payments.
    calculate_days_overdue: Calculates the number of days an invoice is overdue based on the due date and the current date.
    calculate_invoice_status: Determines the status of an invoice based on the amount, total paid, due date, current status, and as of date.
'''

from datetime import date, datetime
from decimal import Decimal
from collections.abc import Iterable
from uuid import UUID

from backend.app.db.models.payment import Payment
from backend.app.services.exceptions import NotFoundError, ValidationError


class InvoiceService:
    def __init__(
        self,
        invoice_repository,
        payment_repository,
    ):
        self.invoice_repository = invoice_repository
        self.payment_repository = payment_repository

    def get_invoice(self, invoice_id: UUID):
        invoice = self.invoice_repository.get_with_payments(invoice_id)

        if invoice is None:
            raise NotFoundError(f"Invoice {invoice_id} was not found.")

        return invoice

    def get_days_overdue(
        self,
        invoice_id: UUID,
        as_of: date,
    ) -> int:
        invoice = self.get_invoice(invoice_id)
        return calculate_days_overdue(invoice.due_date, as_of)

    def refresh_status(
        self,
        invoice_id: UUID,
        as_of: date,
    ):
        invoice = self.get_invoice(invoice_id)
        total_paid = calculate_total_paid(invoice.payments)

        invoice.status = calculate_invoice_status(
            amount=invoice.amount,
            total_paid=total_paid,
            due_date=invoice.due_date,
            current_status=invoice.status,
            as_of=as_of,
        )

        if invoice.status == "paid":
            invoice.paid_date = invoice.paid_date or as_of
        elif invoice.status != "cancelled":
            invoice.paid_date = None

        return self.invoice_repository.save(invoice)

    def record_payment(
        self,
        invoice_id: UUID,
        amount: Decimal,
        method: str,
        reference: str | None = None,
        paid_at: datetime | None = None,
        as_of: date | None = None,
    ):
        if amount <= Decimal("0"):
            raise ValidationError("Payment amount must be greater than zero.")

        invoice = self.get_invoice(invoice_id)
        total_paid = calculate_total_paid(invoice.payments)

        if total_paid + amount > invoice.amount:
            raise ValidationError(
                "Payment would exceed the invoice amount."
            )

        payment = self.payment_repository.create(
            invoice_id=invoice_id,
            amount=amount,
            method=method,
            reference=reference,
            paid_at=paid_at,
        )

        invoice.payments.append(payment)
        self.refresh_status(invoice_id, as_of or date.today())

        return payment


def calculate_total_paid(
    payments: Iterable[Payment],
) -> Decimal:
    return sum(
        (payment.amount for payment in payments),
        Decimal("0.00"),
    )


def calculate_days_overdue(
    due_date: date,
    as_of: date,
) -> int:
    return max((as_of - due_date).days, 0)


def calculate_invoice_status(
    amount: Decimal,
    total_paid: Decimal,
    due_date: date,
    current_status: str,
    as_of: date,
) -> str:
    """Calculate the persisted invoice status from payment and date facts."""
    if amount < Decimal("0"):
        raise ValueError("Invoice amount cannot be negative.")

    if total_paid < Decimal("0"):
        raise ValueError("Total paid cannot be negative.")

    if current_status == "cancelled":
        return "cancelled"

    if total_paid > amount:
        raise ValueError("Total paid cannot exceed invoice amount.")

    if total_paid == amount:
        return "paid"

    if current_status == "draft":
        return "draft"

    if due_date < as_of:
        return "overdue"

    if total_paid > Decimal("0"):
        return "partially_paid"

    return "sent"

