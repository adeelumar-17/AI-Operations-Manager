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

from datetime import date, datetime, timezone
import logging
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload, selectinload
from backend.app.services.invoice_service import outstanding_balance
from backend.app.services.execution_service import require_logged_communication

from backend.app.api.dependencies import get_db, get_current_user
from backend.app.db.models.invoice import Invoice
from backend.app.db.repositories.followup_repository import FollowupRepository
from agents.agent_service import run_agent

router = APIRouter(prefix="/invoices", tags=["Invoices"])
logger = logging.getLogger(__name__)


def _format_invoice(inv: Invoice) -> dict:
    return {
        "id": str(inv.id),
        "invoice_id": inv.invoice_id,
        "invoice_number": inv.invoice_id,
        "customer_id": str(inv.customer_id),
        "customer_name": inv.customer.name if inv.customer else "Customer",
        "total": float(inv.amount),
        "amount": float(inv.amount),
        "amount_due": float(outstanding_balance(inv)),
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
    if status and status not in {"all", "draft", "sent", "partially_paid", "paid", "overdue", "cancelled"}:
        raise HTTPException(status_code=422, detail="Invalid invoice status.")
    stmt = select(Invoice).options(joinedload(Invoice.customer), selectinload(Invoice.payments)).order_by(Invoice.issue_date.desc())
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
        .options(joinedload(Invoice.customer), selectinload(Invoice.payments))
        .where(Invoice.status.in_(["sent", "partially_paid", "overdue"]), Invoice.due_date < date.today())
        .order_by(Invoice.due_date.asc())
    )
    if customer_id:
        stmt = stmt.where(Invoice.customer_id == customer_id)
    overdue = db.scalars(stmt).all()
    return [_format_invoice(inv) for inv in overdue if outstanding_balance(inv) > 0]


@router.get("/{invoice_id}")
def get_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Retrieve details for a specific invoice by UUID or invoice_id."""
    stmt = select(Invoice).options(joinedload(Invoice.customer), selectinload(Invoice.payments))
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
    stmt = select(Invoice).options(joinedload(Invoice.customer), selectinload(Invoice.payments))
    try:
        inv_uuid = UUID(invoice_id)
        stmt = stmt.where(or_(Invoice.id == inv_uuid, Invoice.invoice_id == invoice_id))
    except ValueError:
        stmt = stmt.where(Invoice.invoice_id == invoice_id)

    invoice = db.scalars(stmt).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    balance = outstanding_balance(invoice)
    if invoice.status not in {"sent", "partially_paid", "overdue"} or invoice.due_date >= date.today() or balance <= 0:
        raise HTTPException(status_code=409, detail="Only unpaid overdue invoices can receive an overdue reminder.")
    target_id, customer_id, number = invoice.id, invoice.customer_id, invoice.invoice_id
    repo = FollowupRepository(db)
    task = repo.create(
        task_type="overdue_invoice",
        scheduled_at=datetime.now(timezone.utc),
        customer_id=invoice.customer_id,
        status="in_progress",
    )
    # Trigger autonomous agent reminder
    cust_name = invoice.customer.name if invoice.customer else "the customer"
    prompt = (
        f"Overdue invoice reminder: draft and log an outbound email (do not send) "
        f"for invoice {number} (UUID {target_id}) to customer {cust_name} (UUID {customer_id}). "
        f"Outstanding balance is ${balance:.2f}. Link the communication to related_entity_type invoice and related_entity_id {target_id}."
    )
    task_id = task.id
    db.rollback()  # release read transactions before the LLM/tool work
    success = False
    try:
        agent_res = run_agent(user_input=prompt)
        require_logged_communication(agent_res, db, customer_id, "invoice", target_id)
        repo.mark_completed(task_id)
        success = True
        response_text = "Reminder draft recorded; no email was sent."
    except Exception as e:
        db.rollback()
        logger.exception("Invoice reminder failed")
        repo.mark_failed(task_id, error=str(e))
        response_text = f"Reminder failed: {e}"

    return {
        "success": success,
        "message": f"{number}: {response_text}",
        "invoice_id": number,
        "task_id": str(task_id),
    }
