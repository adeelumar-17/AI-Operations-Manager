'''
This module defines the CommunicationRepository class, which provides methods for interacting with the Communication model in the database. The repository uses SQLAlchemy to perform database operations, such as querying communications by customer ID and ordering them by creation date.
Classes:
    CommunicationRepository: A class that provides methods for interacting with the Communication model.
Methods:
    list_by_customer: Lists communications associated with a specific customer ID, optionally filtered by type, direction, and status.
    get_by_id: Retrieves one communication by ID.
    create: Creates a new communication record.
    save: Saves an existing communication record.
'''
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models.communication import Communication


class CommunicationRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_by_customer(
        self,
        customer_id: UUID,
        communication_type: str | None = None,
        direction: str | None = None,
        status: str | None = None,
    ) -> list[Communication]:
        statement = (
            select(Communication)
            .where(Communication.customer_id == customer_id)
        )

        if communication_type is not None:
            statement = statement.where(Communication.type == communication_type)

        if direction is not None:
            statement = statement.where(Communication.direction == direction)

        if status is not None:
            statement = statement.where(Communication.status == status)

        statement = statement.order_by(Communication.created_at.desc())

        return list(self.session.scalars(statement).all())

    def get_by_id(self, communication_id: UUID) -> Communication | None:
        return self.session.get(Communication, communication_id)

    def create(
        self,
        customer_id: UUID,
        communication_type: str,
        direction: str,
        subject: str | None = None,
        body: str | None = None,
        related_entity_type: str | None = None,
        related_entity_id: UUID | None = None,
    ) -> Communication:
        communication = Communication(
            customer_id=customer_id,
            type=communication_type,
            direction=direction,
            subject=subject,
            body=body,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            status="pending",
        )
        self.session.add(communication)
        self.session.flush()
        return communication

    def save(self, communication: Communication) -> Communication:
        self.session.add(communication)
        self.session.flush()
        return communication