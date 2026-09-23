'''
This module defines the API routes for managing human-in-the-loop approvals. It provides endpoints for listing pending approval requests, retrieving specific approvals, and submitting managerial approval or rejection decisions that resume interrupted LangGraph agent workflows.
Classes:
    None (FastAPI router module).
Methods:
    list_pending_approvals: GET endpoint that returns all approval requests currently awaiting review.
    get_approval: GET endpoint that retrieves a single approval request by its ID.
    approve_action: POST endpoint allowing a manager to approve an action and resume the paused agent workflow.
    reject_action: POST endpoint allowing a manager to reject an action and cancel or redirect the paused agent workflow.
'''

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_db, get_current_user, require_role
from backend.app.schemas.approval import ApprovalResponse, ApprovalDecisionRequest
from backend.app.schemas.chat import ChatResponse
from backend.app.services.approval_service import ApprovalService
from agents.agent_service import resume_agent

router = APIRouter(prefix="/approvals", tags=["Approvals"])


def _resume(**kwargs):
    try:
        return resume_agent(**kwargs)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[ApprovalResponse])
def list_pending_approvals(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all pending actions requiring manager approval."""
    service = ApprovalService(db)
    return service.list_pending_approvals()


@router.get("/{approval_id}", response_model=ApprovalResponse)
def get_approval(
    approval_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get details of a specific approval request."""
    service = ApprovalService(db)
    approval = service.get_approval(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found.")
    return approval


@router.post("/{approval_id}/approve", response_model=ChatResponse)
def approve_action(
    approval_id: UUID,
    req: ApprovalDecisionRequest = ApprovalDecisionRequest(),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role(["manager", "admin"])),
):
    """Approve a pending action and resume the agent graph to finalize it."""
    service = ApprovalService(db)
    approval = service.get_approval(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found.")

    if approval.status not in {"pending", "approved"}:
        raise HTTPException(
            status_code=400,
            detail=f"Approval request is already resolved with status '{approval.status}'.",
        )

    db.rollback()  # resume opens its own short business transactions
    res = _resume(
        approval_id=str(approval_id),
        approved=True,
        comment=req.comment,
        reviewer_id=current_user["user_id"],
    )

    return ChatResponse(
        response=res.get("response", ""),
        workflow=res.get("workflow"),
        intent=res.get("intent"),
        entities=res.get("entities", {}),
        approval_required=True,
        approval_id=str(approval_id),
        approval_decision="approved",
        thread_id=res.get("thread_id"),
        request_id=res.get("request_id"),
        error=res.get("error"),
    )


@router.post("/{approval_id}/reject", response_model=ChatResponse)
def reject_action(
    approval_id: UUID,
    req: ApprovalDecisionRequest = ApprovalDecisionRequest(),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role(["manager", "admin"])),
):
    """Reject a pending action and resume the agent graph with rejection."""
    service = ApprovalService(db)
    approval = service.get_approval(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found.")

    if approval.status not in {"pending", "rejected"}:
        raise HTTPException(
            status_code=400,
            detail=f"Approval request is already resolved with status '{approval.status}'.",
        )

    db.rollback()
    res = _resume(
        approval_id=str(approval_id),
        approved=False,
        comment=req.comment,
        reviewer_id=current_user["user_id"],
    )

    return ChatResponse(
        response=res.get("response", ""),
        workflow=res.get("workflow"),
        intent=res.get("intent"),
        entities=res.get("entities", {}),
        approval_required=True,
        approval_id=str(approval_id),
        approval_decision="rejected",
        thread_id=res.get("thread_id"),
        request_id=res.get("request_id"),
        error=res.get("error"),
    )
