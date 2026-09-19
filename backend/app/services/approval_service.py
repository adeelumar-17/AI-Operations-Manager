'''
This module defines the ApprovalService class, which provides business logic for managing human-in-the-loop approval workflows. It handles requesting approval for high-risk actions (e.g. large discounts), retrieving pending approvals, and recording approval or rejection decisions by managers.
Classes:
    ApprovalService: Service class that manages approval requests and resolves managerial review decisions.
Methods:
    request_approval: Creates a new approval request record for an intercepted agent action.
    get_approval: Retrieves an approval request by its unique identifier.
    list_pending_approvals: Returns all approval requests currently waiting for manager review.
    approve: Resolves an approval request with status 'approved' and records the approving manager.
    reject: Resolves an approval request with status 'rejected' and records the reviewing manager.
'''

from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from backend.app.db.repositories.approval_repository import ApprovalRepository
from backend.app.db.models.approval_request import ApprovalRequest


class ApprovalService:
    """Business logic service for managing approval requests."""

    def __init__(self, session: Session):
        self.session = session
        self.repo = ApprovalRepository(session)

    def request_approval(
        self,
        action_type: str,
        action_payload: dict,
        reason: str,
        run_id: Optional[UUID] = None,
        requested_by: str = "agent",
    ) -> ApprovalRequest:
        """Create a new approval request for an agent action."""
        return self.repo.create(
            action_type=action_type,
            action_payload=action_payload,
            reason=reason,
            run_id=run_id,
            requested_by=requested_by,
        )

    def get_approval(self, approval_id: UUID | str) -> Optional[ApprovalRequest]:
        """Get an approval request by ID."""
        return self.repo.get_by_id(approval_id)

    def list_pending_approvals(self) -> list[ApprovalRequest]:
        """List all pending approval requests."""
        return self.repo.list_pending()

    def approve(
        self,
        approval_id: UUID | str,
        approved_by: Optional[UUID] = None,
    ) -> Optional[ApprovalRequest]:
        """Approve an action request."""
        return self.repo.resolve(
            approval_id=approval_id,
            status="approved",
            approved_by=approved_by,
        )

    def reject(
        self,
        approval_id: UUID | str,
        approved_by: Optional[UUID] = None,
    ) -> Optional[ApprovalRequest]:
        """Reject an action request."""
        return self.repo.resolve(
            approval_id=approval_id,
            status="rejected",
            approved_by=approved_by,
        )
