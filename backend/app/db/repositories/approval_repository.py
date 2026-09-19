'''
This module defines the ApprovalRepository class, which provides methods for database CRUD operations on the ApprovalRequest model. It supports creating approval requests, fetching requests by ID, listing pending requests, resolving requests as approved or rejected, and deleting requests.
Classes:
    ApprovalRepository: A repository class that provides methods for interacting with the ApprovalRequest model in PostgreSQL.
Methods:
    create: Creates and persists a new approval request in the database.
    get_by_id: Retrieves an approval request by its unique identifier.
    list_pending: Retrieves all approval requests currently in 'pending' status.
    resolve: Updates an approval request status to 'approved' or 'rejected' with reviewer details and timestamps.
    delete: Deletes an approval request from the database.
'''

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.db.models.approval_request import ApprovalRequest


class ApprovalRepository:
    """Repository handling CRUD operations for approval requests."""

    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        action_type: str,
        action_payload: dict,
        reason: str,
        run_id: Optional[UUID] = None,
        requested_by: str = "agent",
    ) -> ApprovalRequest:
        """Create a new pending approval request."""
        approval = ApprovalRequest(
            id=uuid4(),
            run_id=run_id,
            requested_by=requested_by,
            action_type=action_type,
            action_payload=action_payload,
            reason=reason,
            status="pending",
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(approval)
        self.session.commit()
        self.session.refresh(approval)
        return approval

    def get_by_id(self, approval_id: UUID | str) -> Optional[ApprovalRequest]:
        """Fetch an approval request by its ID."""
        if isinstance(approval_id, str):
            try:
                approval_id = UUID(approval_id)
            except ValueError:
                return None
        return self.session.get(ApprovalRequest, approval_id)

    def list_pending(self) -> list[ApprovalRequest]:
        """List all pending approval requests ordered by creation time."""
        stmt = (
            select(ApprovalRequest)
            .where(ApprovalRequest.status == "pending")
            .order_by(ApprovalRequest.created_at.desc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def list_all(self, limit: int = 50) -> list[ApprovalRequest]:
        """List all approval requests."""
        stmt = (
            select(ApprovalRequest)
            .order_by(ApprovalRequest.created_at.desc())
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())

    def resolve(
        self,
        approval_id: UUID | str,
        status: str,
        approved_by: Optional[UUID | str] = None,
    ) -> Optional[ApprovalRequest]:
        """Resolve an approval request (approved or rejected)."""
        approval = self.get_by_id(approval_id)
        if not approval:
            return None

        # Safely convert approved_by to a valid User UUID if exists, else None
        user_uuid: Optional[UUID] = None
        if approved_by:
            if isinstance(approved_by, UUID):
                user_uuid = approved_by
            elif isinstance(approved_by, str):
                try:
                    user_uuid = UUID(approved_by)
                except ValueError:
                    user_uuid = None

            if user_uuid:
                from backend.app.db.models.user import User
                if not self.session.get(User, user_uuid):
                    user_uuid = None

        approval.status = status
        approval.approved_by = user_uuid
        approval.resolved_at = datetime.now(timezone.utc)

        # Synchronize linked Quotes status to match approval resolution
        from backend.app.db.models.quote import Quote
        linked_quotes = self.session.query(Quote).filter(Quote.approval_id == approval.id).all()
        for q in linked_quotes:
            if status == "approved":
                q.status = "approved"
            elif status == "rejected":
                q.status = "rejected"

        self.session.commit()
        self.session.refresh(approval)
        return approval
