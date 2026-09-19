'''
This module defines the PaymentRepository class, which provides methods for interacting with the Payment model in the database. The PaymentRepository class is initialized with a SQLAlchemy Session object and provides a method to create a new payment, including the invoice ID, amount, method, reference, and optional paid date.
Classes:
    PaymentRepository: A class for interacting with the Payment model in the database.
Methods:
    create: Creates a new payment with the specified details.
'''

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.db.models.payment import Payment


class PaymentRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        invoice_id: UUID,
        amount: Decimal,
        method: str,
        reference: str | None = None,
        paid_at: datetime | None = None,
    ) -> Payment:
        payment = Payment(
            invoice_id=invoice_id,
            amount=amount,
            method=method,
            reference=reference,
        )

        if paid_at is not None:
            payment.paid_at = paid_at

        self.session.add(payment)
        self.session.flush()

        return payment

