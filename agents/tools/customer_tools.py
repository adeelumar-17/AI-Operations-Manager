'''
what the file does?
This module provides LangChain-compatible customer management tools for the operations agent, wrapping CustomerService to search customer records, retrieve detailed profile info, and pull unified historical interactions (orders, invoices, and communications).

Classes:
    None (LangChain tool definition module)

Methods:
    _make_customer_service: Helper factory creating a CustomerService instance with a fresh DB session and repositories.
    search_customer: Tool to search for customers by name, email, or company name.
    get_customer_details: Tool to fetch full profile and contact details for a specific customer ID.
    get_customer_history: Tool to fetch chronological order, invoice, and communication history for a customer.
'''

from typing import Annotated
from uuid import UUID

from langchain_core.tools import tool

from backend.app.core.config import settings
from backend.app.db.database import SessionLocal
from backend.app.db.repositories.customer_repository import CustomerRepository
from backend.app.db.repositories.order_repository import OrderRepository
from backend.app.db.repositories.invoice_repository import InvoiceRepository
from backend.app.db.repositories.communication_repository import CommunicationRepository
from backend.app.services.customer_service import CustomerService


def _make_customer_service() -> tuple[CustomerService, object]:
    """Instantiate CustomerService with a fresh session. Caller must close session."""
    session = SessionLocal()
    service = CustomerService(
        customer_repository=CustomerRepository(session),
        order_repository=OrderRepository(session),
        invoice_repository=InvoiceRepository(session),
        communication_repository=CommunicationRepository(session),
    )
    return service, session


@tool
def search_customer(
    query: Annotated[str, "Customer name, email address, or company name to search for"],
) -> str:
    """Search for a customer by name, email, or company name.

    Returns a list of matching customers with their IDs, names, emails, and company names.
    Use this first when the user mentions a customer by name or company.
    """
    service, session = _make_customer_service()
    try:
        customers = service.search_customers(query)
        if not customers:
            return f"No customers found matching '{query}'."
        lines = [f"Found {len(customers)} customer(s):"]
        for c in customers:
            lines.append(
                f"  - ID: {c.id} | Name: {c.name} | Email: {c.email or 'N/A'} | Company: {c.company_name or 'N/A'}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error searching for customer: {e}"
    finally:
        session.close()


@tool
def get_customer_details(
    customer_id: Annotated[str, "UUID of the customer to retrieve"],
) -> str:
    """Get full details for a specific customer, including contact info and notes.

    Use after search_customer to get the full profile for a known customer ID.
    """
    service, session = _make_customer_service()
    try:
        customer = service.get_customer(UUID(customer_id))
        return (
            f"Customer: {customer.name}\n"
            f"  ID: {customer.id}\n"
            f"  Email: {customer.email or 'N/A'}\n"
            f"  Phone: {customer.phone or 'N/A'}\n"
            f"  Company: {customer.company_name or 'N/A'}\n"
            f"  Address: {customer.address or 'N/A'}\n"
            f"  Notes: {customer.notes or 'N/A'}\n"
            f"  Created: {customer.created_at.date()}"
        )
    except Exception as e:
        return f"Error retrieving customer: {e}"
    finally:
        session.close()


@tool
def get_customer_history(
    customer_id: Annotated[str, "UUID of the customer"],
) -> str:
    """Retrieve a summary of a customer's full history: orders, invoices, and communications.

    Use when the user asks about a customer's account, past activity, or relationship.
    """
    service, session = _make_customer_service()
    try:
        history = service.get_customer_history(UUID(customer_id))
        orders = history["orders"]
        invoices = history["invoices"]
        comms = history["communications"]

        lines = [f"Customer history for ID {customer_id}:"]
        lines.append(f"\nOrders ({len(orders)}):")
        for o in orders:
            lines.append(f"  - {o.order_number} | Status: {o.status} | Total: ${o.total}")
        lines.append(f"\nInvoices ({len(invoices)}):")
        for inv in invoices:
            lines.append(f"  - {inv.invoice_id} | Status: {inv.status} | Amount: ${inv.amount} | Due: {inv.due_date}")
        lines.append(f"\nCommunications ({len(comms)}):")
        for comm in comms[:5]:  # bounded — don't dump the entire history
            lines.append(f"  - [{comm.type}] {comm.subject or '(no subject)'} | Status: {comm.status}")
        if len(comms) > 5:
            lines.append(f"  ... and {len(comms) - 5} more")
        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving customer history: {e}"
    finally:
        session.close()
