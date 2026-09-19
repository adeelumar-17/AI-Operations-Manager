'''
This module defines the CommunicationService, which provides methods for managing and tracking communications with customers. It includes functionality for recording communications, marking them as sent or failed, and retrieving communication history.
Classes:
    - CommunicationService: Provides methods for managing and tracking communications with customers.
Methods:
    - record_communication: Records a new communication with a customer.
    - mark_sent: Marks a communication as sent, recording the timestamp.
    - mark_failed: Marks a communication as failed.
    - get_communication_history: Retrieves the communication history for a specific customer, optionally filtered by type, direction, and status.
    - get_by_id: Retrieves a communication by its ID.
'''

from datetime import datetime
from uuid import UUID

from backend.app.db.models.communication import Communication
from backend.app.services.exceptions import NotFoundError, ValidationError


COMMUNICATION_TYPES = {"email", "call", "note", "sms"}
DIRECTIONS = {"inbound", "outbound"}
STATUSES = {"pending", "sent", "failed"}

class CommunicationService:
    def __init__(
        self,
        communication_repository,
        customer_repository,
    ):
        self.communication_repository = communication_repository
        self.customer_repository = customer_repository

    def record_communication(
        self,
        customer_id: UUID,
        communication_type: str,
        direction: str,
        subject: str | None = None,
        body: str | None = None,
        related_entity_type: str | None = None,
        related_entity_id: UUID | None = None,
    ) -> Communication:
        self._require_customer(customer_id)
        self._validate_type_and_direction(communication_type, direction)

        if communication_type in {"email", "sms", "note"} and not body:
            raise ValidationError(
                f"A body is required for {communication_type} communications."
            )

        if (related_entity_type is None) != (related_entity_id is None):
            raise ValidationError(
                "Related entity type and ID must be provided together."
            )

        if related_entity_type is not None and not related_entity_type.strip():
            raise ValidationError("Related entity type cannot be empty.")

        return self.communication_repository.create(
            customer_id=customer_id,
            communication_type=communication_type,
            direction=direction,
            subject=subject,
            body=body,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )

    def mark_sent(
        self,
        communication_id: UUID,
        sent_at: datetime,
    ) -> Communication:
        communication = self.get_by_id(communication_id)

        if communication is None:
            raise NotFoundError(
                f"Communication {communication_id} was not found."
            )

        if communication.status != "pending":
            raise ValidationError(
                "Only pending communications can be marked as sent."
            )

        communication.status = "sent"
        communication.sent_at = sent_at
        return self.communication_repository.save(communication)

    def mark_failed(
        self,
        communication_id: UUID,
    ) -> Communication:
        communication = self.get_by_id(communication_id)

        if communication is None:
            raise NotFoundError(
                f"Communication {communication_id} was not found."
            )

        if communication.status != "pending":
            raise ValidationError(
                "Only pending communications can be marked as failed."
            )

        communication.status = "failed"
        communication.sent_at = None
        return self.communication_repository.save(communication)

    def get_communication_history(
        self,
        customer_id: UUID,
        communication_type: str | None = None,
        direction: str | None = None,
        status: str | None = None,
    ) -> list[Communication]:
        self._require_customer(customer_id)

        if communication_type is not None and communication_type not in COMMUNICATION_TYPES:
            raise ValidationError("Invalid communication type.")

        if direction is not None and direction not in DIRECTIONS:
            raise ValidationError("Invalid communication direction.")

        if status is not None and status not in STATUSES:
            raise ValidationError("Invalid communication status.")

        return self.communication_repository.list_by_customer(
            customer_id=customer_id,
            communication_type=communication_type,
            direction=direction,
            status=status,
        )

    def get_by_id(
        self,
        communication_id: UUID,
    ) -> Communication | None:
        return self.communication_repository.get_by_id(communication_id)

    def _require_customer(self, customer_id: UUID):
        if self.customer_repository.get_by_id(customer_id) is None:
            raise NotFoundError(f"Customer {customer_id} was not found.")

    @staticmethod
    def _validate_type_and_direction(
        communication_type: str,
        direction: str,
    ) -> None:
        if communication_type not in COMMUNICATION_TYPES:
            raise ValidationError("Invalid communication type.")

        if direction not in DIRECTIONS:
            raise ValidationError("Invalid communication direction.")

