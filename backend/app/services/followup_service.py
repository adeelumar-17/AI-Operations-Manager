"""Validation shared by the task API and conversational scheduling tool."""
from datetime import datetime, timezone
from uuid import UUID
from backend.app.db.models.customer import Customer
from backend.app.db.models.quote import Quote
from backend.app.db.repositories.followup_repository import FollowupRepository
from backend.app.services.exceptions import ValidationError, NotFoundError


def create_followup(session, task_type, scheduled_at, customer_id=None, quote_id=None):
    try:
        customer_id = UUID(str(customer_id)) if customer_id else None
        quote_id = UUID(str(quote_id)) if quote_id else None
        if isinstance(scheduled_at, str):
            scheduled_at = datetime.fromisoformat(scheduled_at)
    except (ValueError, TypeError) as exc:
        raise ValidationError("Use valid UUIDs and an ISO 8601 timestamp with a timezone offset.") from exc
    if scheduled_at.tzinfo is None or scheduled_at.utcoffset() is None:
        raise ValidationError("Scheduled time must include a timezone offset.")
    if scheduled_at <= datetime.now(timezone.utc):
        raise ValidationError("Scheduled time must be in the future.")
    if not task_type.strip():
        raise ValidationError("Task type cannot be empty.")
    if customer_id and session.get(Customer, customer_id) is None:
        raise NotFoundError("Customer not found.")
    if quote_id:
        quote = session.get(Quote, quote_id)
        if quote is None:
            raise NotFoundError("Quote not found.")
        if customer_id and quote.customer_id != customer_id:
            raise ValidationError("Quote does not belong to this customer.")
        customer_id = customer_id or quote.customer_id
    if customer_id is None:
        raise ValidationError("A customer or quote is required.")
    return FollowupRepository(session).create(task_type.strip(), scheduled_at.astimezone(timezone.utc), customer_id, quote_id)
