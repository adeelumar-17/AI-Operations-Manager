'''
This module defines the InvoiceRepository class, which provides methods for interacting with the Invoice model in the database. The repository uses SQLAlchemy to perform database operations, such as querying invoices by customer ID and ordering them by issue date.
Classes:
    InvoiceRepository: A class that provides methods for interacting with the Invoice model.
Methods:
    list_by_customer: Lists invoices associated with a specific customer ID, returning them in descending order of issue date.
    get_by_id: Retrieves an invoice by its ID.
    get_with_payments: Retrieves an invoice along with its payments.
    save: Saves an invoice to the database.
'''

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.db.models.invoice import Invoice


class InvoiceRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_by_customer(self, customer_id: UUID) -> list[Invoice]:
        statement = (
            select(Invoice)
            .where(Invoice.customer_id == customer_id)
            .order_by(Invoice.issue_date.desc())
        )

        return list(self.session.scalars(statement).all())

    def get_by_id(self, invoice_id: UUID) -> Invoice | None:
        statement = select(Invoice).where(Invoice.id == invoice_id)
        result = self.session.scalars(statement).one_or_none()
        return result

    def get_with_payments(self, invoice_id: UUID) -> Invoice | None:
        try:
            predicate = Invoice.id == UUID(str(invoice_id))
        except ValueError:
            predicate = Invoice.invoice_id == str(invoice_id)
        statement = (
            select(Invoice)
            .where(predicate)
            .options(selectinload(Invoice.payments))
            .with_for_update()
        )
        result = self.session.scalars(statement).one_or_none()
        return result

    def save(self, invoice: Invoice) -> Invoice:
        self.session.add(invoice)
        self.session.flush()
        return invoice
