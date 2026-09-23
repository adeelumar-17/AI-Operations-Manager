import logging
logger = logging.getLogger(__name__)
'''
what the file does?
This module provides LangChain-compatible communication tracking tools for the operations agent, delegating to CommunicationService to record inbound/outbound interactions (emails, calls, notes, SMS) and retrieve communication history.

Classes:
    None (LangChain tool definition module)

Methods:
    _make_comm_service: Helper factory creating a CommunicationService instance with a fresh DB session and repositories.
    log_communication: Tool to log an outbound or inbound customer communication event tied to business entities.
    get_communication_history: Tool to fetch recent logged communication entries for a customer ID.
'''

from typing import Annotated
from uuid import UUID

from langchain_core.tools import tool

from backend.app.db.database import SessionLocal
from backend.app.db.repositories.communication_repository import CommunicationRepository
from backend.app.db.repositories.customer_repository import CustomerRepository
from backend.app.services.communication_service import CommunicationService


def _make_comm_service() -> tuple[CommunicationService, object]:
    session = SessionLocal()
    service = CommunicationService(
        communication_repository=CommunicationRepository(session),
        customer_repository=CustomerRepository(session),
    )
    return service, session


@tool
def log_communication(
    customer_id: Annotated[str, "UUID of the customer"],
    communication_type: Annotated[str, "Type: 'email', 'call', 'note', or 'sms'"],
    direction: Annotated[str, "Direction: 'outbound' (agent/staff initiated) or 'inbound'"],
    subject: Annotated[str, "Subject line or brief description"] = "",
    body: Annotated[str, "Full message body or call notes"] = "",
    related_entity_type: Annotated[
        str, "Optional: 'quote', 'order', 'invoice', or 'followup_task'"
    ] = "",
    related_entity_id: Annotated[str, "Optional: UUID of the related entity"] = "",
) -> str:
    """Record a communication event with a customer (email, call, note, or SMS).

    Use after taking any outbound action (sending a quote, making a follow-up call,
    leaving a note). This creates an auditable communication record in the database.
    """
    service, session = _make_comm_service()
    try:
        kwargs: dict = {
            "customer_id": UUID(customer_id),
            "communication_type": communication_type,
            "direction": direction,
            "subject": subject or None,
            "body": body or None,
        }
        if related_entity_type and related_entity_id:
            kwargs["related_entity_type"] = related_entity_type
            kwargs["related_entity_id"] = UUID(related_entity_id)

        comm = service.record_communication(**kwargs)
        session.commit()
        return (
            f"✓ Communication logged.\n"
            f"  ID: {comm.id}\n"
            f"  Type: {comm.type} | Direction: {comm.direction}\n"
            f"  Subject: {comm.subject or '(none)'}\n"
            f"  Status: {comm.status}"
        )
    except Exception as e:
        logger.exception('Operation failed')
        return f"Error logging communication: {e}"
    finally:
        session.close()


@tool
def get_communication_history(
    customer_id: Annotated[str, "UUID of the customer"],
    communication_type: Annotated[
        str, "Optional filter: 'email', 'call', 'note', 'sms', or '' for all"
    ] = "",
    limit: Annotated[int, "Maximum number of records to return (default 10)"] = 10,
) -> str:
    """Retrieve recent communications with a customer.

    Use when you need context on recent interactions before composing a follow-up,
    or when the user asks about the history with a customer.
    """
    service, session = _make_comm_service()
    try:
        comms = service.get_communication_history(
            customer_id=UUID(customer_id),
            communication_type=communication_type or None,
            limit=limit,
        )
        if not comms:
            return f"No communications found for customer {customer_id}."

        recent = comms[:limit]
        lines = [f"Communication history for customer {customer_id} ({len(recent)} shown of {len(comms)}):"]
        for c in recent:
            lines.append(
                f"  [{c.created_at.date()}] {c.type.upper()} ({c.direction}) — "
                f"{c.subject or '(no subject)'} | Status: {c.status} | UUID: {c.id} | Body: {c.body or ''}"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.exception('Operation failed')
        return f"Error retrieving communication history: {e}"
    finally:
        session.close()
