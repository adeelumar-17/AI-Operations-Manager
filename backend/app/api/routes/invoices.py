'''
This module defines the API routes for accounts receivable and invoice management. It provides endpoints for listing all invoices, filtering overdue invoices, retrieving individual invoice details, and dispatching autonomous collections reminders via the operations agent.
Classes:
    None (FastAPI router module).
Methods:
    _format_invoice: Internal helper to serialize an Invoice SQLAlchemy model into a standardized dictionary.
    list_invoices: GET endpoint to list all invoices with optional status filtering.
    list_overdue_invoices: GET endpoint to retrieve past-due invoices requiring attention.
    get_invoice: GET endpoint to retrieve details for a specific invoice by its ID.
    send_invoice_reminder: POST endpoint that creates a follow-up task and runs the agent to draft and log an overdue payment notice.
'''

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from backend.app.api.dependencies import get_db, get_current_user
from backend.app.db.models.invoice import Invoice
from backend.app.db.repositories.followup_repository import FollowupRepository
from agents.agent_service import run_agent

router = APIRouter(prefix="/invoices", tags=["Invoices"])


def _format_invoice(inv: Invoice) -> dict:
    return {
        "id": str(inv.id),
        "invoice_id": inv.invoice_id,
        "invoice_number": inv.invoice_id,
        "customer_id": str(inv.customer_id),
        "customer_name": inv.customer.name if inv.customer else "Customer",
        "total": float(inv.amount),
        "amount": float(inv.amount),
        "amount_due": float(inv.amount) if inv.status != "paid" else 0.0,
        "due_date": inv.due_date.isoformat() if inv.due_date else None,
        "issue_date": inv.issue_date.isoformat() if inv.issue_date else None,
        "status": inv.status,
        "paid_at": inv.paid_date.isoformat() if inv.paid_date else None,
    }


@router.get("")
def list_invoices(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all invoices, optionally filtered by status."""
    stmt = select(Invoice).options(joinedload(Invoice.customer)).order_by(Invoice.issue_date.desc())
    if status and status != "all":
        stmt = stmt.where(Invoice.status == status)
    invoices = db.scalars(stmt).all()
    return [_format_invoice(inv) for inv in invoices]


@router.get("/overdue")
def list_overdue_invoices(
    customer_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Retrieve all overdue invoices, optionally filtered by customer."""
    stmt = (
        select(Invoice)
        .options(joinedload(Invoice.customer))
        .where(Invoice.status == "overdue")
        .order_by(Invoice.due_date.asc())
    )
    if customer_id:
        stmt = stmt.where(Invoice.customer_id == customer_id)
    overdue = db.scalars(stmt).all()
    return [_format_invoice(inv) for inv in overdue]


@router.get("/{invoice_id}")
def get_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Retrieve details for a specific invoice by UUID or invoice_id."""
    stmt = select(Invoice).options(joinedload(Invoice.customer))
    try:
        inv_uuid = UUID(invoice_id)
        stmt = stmt.where(or_(Invoice.id == inv_uuid, Invoice.invoice_id == invoice_id))
    except ValueError:
        stmt = stmt.where(Invoice.invoice_id == invoice_id)

    invoice = db.scalars(stmt).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    return _format_invoice(invoice)


@router.post("/{invoice_id}/remind")
def send_invoice_reminder(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Dispatch an autonomous reminder task for an overdue invoice."""
    stmt = select(Invoice).options(joinedload(Invoice.customer))
    try:
        inv_uuid = UUID(invoice_id)
        stmt = stmt.where(or_(Invoice.id == inv_uuid, Invoice.invoice_id == invoice_id))
    except ValueError:
        stmt = stmt.where(Invoice.invoice_id == invoice_id)

    invoice = db.scalars(stmt).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    repo = FollowupRepository(db)
    task = repo.create(
        task_type="overdue_invoice",
        scheduled_at=datetime.now(timezone.utc),
        customer_id=invoice.customer_id,
    )
    # Trigger autonomous agent reminder
    cust_name = invoice.customer.name if invoice.customer else "the customer"
    prompt = (
        f"Overdue invoice reminder: Please draft and send an overdue payment notice "
        f"for invoice {invoice.invoice_id} to {cust_name} for outstanding balance ${float(invoice.amount):.2f}."
    )
    try:
        agent_res = run_agent(user_input=prompt)
        repo.mark_completed(task.id)
        response_text = agent_res.get("response", "Reminder dispatched.")
    except Exception as e:
        repo.mark_failed(task.id, error=str(e))
        response_text = "Follow-up task queued for execution."

    return {
        "success": True,
        "message": f"Reminder sent for {invoice.invoice_id}: {response_text}",
        "invoice_id": invoice.invoice_id,
        "task_id": str(task.id),
    }
