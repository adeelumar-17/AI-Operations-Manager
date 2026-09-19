'''
what the file does?
This module provides LangChain-compatible invoice and billing tools for the operations agent, wrapping InvoiceService to query invoice details, list overdue customer invoices, and compute days overdue.

Classes:
    None (LangChain tool definition module)

Methods:
    _make_invoice_service: Helper factory creating an InvoiceService instance with a fresh DB session and repositories.
    get_invoice: Tool to retrieve detailed billing information, status, due date, and payments for an invoice ID.
    find_overdue_invoices: Tool to search for unpaid invoices past their due date, optionally filtered by customer ID.
    get_days_overdue: Tool to calculate elapsed days past an invoice's due date.
'''

from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from langchain_core.tools import tool
from sqlalchemy import select

from backend.app.db.database import SessionLocal
from backend.app.db.models.invoice import Invoice
from backend.app.db.repositories.invoice_repository import InvoiceRepository
from backend.app.db.repositories.payment_repository import PaymentRepository
from backend.app.services.invoice_service import InvoiceService, calculate_days_overdue


def _make_invoice_service() -> tuple[InvoiceService, object]:
    session = SessionLocal()
    service = InvoiceService(
        invoice_repository=InvoiceRepository(session),
        payment_repository=PaymentRepository(session),
    )
    return service, session


@tool
def get_invoice(
    invoice_id: Annotated[str, "UUID of the invoice to retrieve"],
) -> str:
    """Retrieve an invoice's details including amount, status, due date, and payments.

    Use when the user asks about a specific invoice or payment status.
    """
    service, session = _make_invoice_service()
    try:
        invoice = service.get_invoice(UUID(invoice_id))
        days_overdue = calculate_days_overdue(invoice.due_date, date.today())
        lines = [
            f"Invoice: {invoice.invoice_id}",
            f"  Status: {invoice.status}",
            f"  Amount: ${invoice.amount}",
            f"  Issue date: {invoice.issue_date}",
            f"  Due date: {invoice.due_date}",
        ]
        if days_overdue > 0 and invoice.status not in ("paid", "cancelled"):
            lines.append(f"  ⚠ Days overdue: {days_overdue}")
        if invoice.paid_date:
            lines.append(f"  Paid date: {invoice.paid_date}")
        if invoice.payments:
            lines.append(f"  Payments ({len(invoice.payments)}):")
            for p in invoice.payments:
                lines.append(f"    - ${p.amount} via {p.method or 'unknown'} on {p.paid_at.date()}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving invoice: {e}"
    finally:
        session.close()


@tool
def find_overdue_invoices(
    customer_id: Annotated[
        str,
        "UUID of the customer to check, or 'all' to find all overdue invoices",
    ] = "all",
) -> str:
    """Find overdue invoices — for a specific customer or across all customers.

    Returns invoice IDs, amounts, due dates, and days overdue. Use for
    follow-up workflows and collections management.
    """
    service, session = _make_invoice_service()
    try:
        today = date.today()
        stmt = (
            select(Invoice)
            .where(Invoice.status.in_(["sent", "partially_paid", "overdue"]))
            .where(Invoice.due_date < today)
            .order_by(Invoice.due_date)
        )
        if customer_id != "all":
            stmt = stmt.where(Invoice.customer_id == UUID(customer_id))

        invoices = list(session.scalars(stmt).all())

        if not invoices:
            return "No overdue invoices found."

        lines = [f"Overdue invoices ({len(invoices)}):"]
        for inv in invoices:
            days = calculate_days_overdue(inv.due_date, today)
            lines.append(
                f"  - {inv.invoice_id} | Customer: {inv.customer_id} | "
                f"Amount: ${inv.amount} | Due: {inv.due_date} | "
                f"Days overdue: {days}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error finding overdue invoices: {e}"
    finally:
        session.close()


@tool
def get_days_overdue(
    invoice_id: Annotated[str, "UUID of the invoice"],
) -> str:
    """Calculate how many days overdue a specific invoice is.

    Returns 0 if the invoice is not yet past its due date.
    The calculation is always done in application code (today - due_date),
    never stored as a stale value in the database.
    """
    service, session = _make_invoice_service()
    try:
        days = service.get_days_overdue(UUID(invoice_id), date.today())
        invoice = service.get_invoice(UUID(invoice_id))
        if days == 0:
            return f"Invoice {invoice.invoice_id} is not overdue (due: {invoice.due_date})."
        return f"Invoice {invoice.invoice_id} is {days} day(s) overdue (due: {invoice.due_date})."
    except Exception as e:
        return f"Error calculating days overdue: {e}"
    finally:
        session.close()
