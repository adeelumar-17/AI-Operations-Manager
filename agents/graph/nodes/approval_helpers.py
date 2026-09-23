"""Persist one exact approval proposal per request and resume it without replay."""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5
from langgraph.types import interrupt
from sqlalchemy import select
from backend.app.db.database import SessionLocal
from backend.app.db.models.approval_request import ApprovalRequest
from backend.app.db.repositories.quote_repository import QuoteRepository
from backend.app.db.repositories.order_repository import OrderRepository
from backend.app.services.quote_service import QuoteService
from backend.app.services.exceptions import ValidationError


def approval_key(state, action_type):
    return uuid5(NAMESPACE_URL, f"officehub:{state['request_id']}:{action_type}")


def saved_approval(state, action_type):
    with SessionLocal() as db:
        return db.get(ApprovalRequest, approval_key(state, action_type)) is not None


def review_action(state, config, action_type, proposal=None, reason="", results=None):
    approval_id = approval_key(state, action_type)
    with SessionLocal() as db:
        row = db.get(ApprovalRequest, approval_id)
        if row is None:
            if proposal is None:
                raise ValidationError("Missing approval proposal.")
            payload = {"proposal": proposal, "thread_id": config["configurable"]["thread_id"],
                       "request_id": state["request_id"], "results": results or []}
            row = ApprovalRequest(id=approval_id, action_type=action_type,
                                  action_payload=payload, reason=reason, status="pending",
                                  requested_by="agent", created_at=datetime.now(timezone.utc))
            db.add(row)
            db.flush()
            if action_type == "quote_discount_approval":
                quote = QuoteRepository(db).get_with_items(proposal["quote_id"])
                if quote is None:
                    raise ValidationError("Quote no longer exists.")
                QuoteService.require_editable(quote)
                if quote.status != proposal["previous_status"] or str(quote.subtotal) != proposal["subtotal"] or str(quote.total) != proposal["total"]:
                    raise ValidationError("Quote changed while approval was being prepared; retry.")
                quote.status = "pending_approval"
                quote.approval_id = approval_id
            db.commit()
        reason = row.reason
    # GraphInterrupt must propagate; no DB transaction stays open during the wait.
    decision = interrupt({"approval_id": str(approval_id), "action_type": action_type, "reason": reason})
    if not isinstance(decision, dict) or decision.get("approval_id") != str(approval_id):
        raise ValidationError("Approval decision does not match the pending action.")
    status = "approved" if decision.get("approved") is True else "rejected"
    with SessionLocal() as db:
        row = db.scalars(select(ApprovalRequest).where(ApprovalRequest.id == approval_id).with_for_update()).one()
        if row.status != status:
            raise ValidationError("The manager decision has not been persisted.")
        payload = dict(row.action_payload)
        if "execution_result" not in payload:
            proposal = payload["proposal"]
            result = "Refund review recorded; no refund was issued by this system."
            if action_type == "quote_discount_approval":
                quote = QuoteRepository(db).get_with_items(proposal["quote_id"])
                if quote is None or quote.approval_id != approval_id or quote.status != "pending_approval":
                    raise ValidationError("Quote no longer matches this pending approval.")
                quote.status = proposal["previous_status"]
                if status == "approved":
                    service = QuoteService(QuoteRepository(db), OrderRepository(db))
                    quote = service.apply_discount(quote.id, Decimal(proposal["discount_percent"]), Decimal("25"))
                    quote.approval_id = approval_id
                    result = f"Discount applied to {quote.quote_number}. Total: ${quote.total}. No order was created."
                else:
                    quote.approval_id = None
                    result = "Discount rejected; the previous quote price and status were preserved."
            payload["execution_result"] = result
            row.action_payload = payload
            db.commit()
        return {"approval_required": True, "approval_id": str(approval_id), "approval_decision": status,
                "action_results": payload.get("results", []) + [
                    {"tool": "manager_approval", "result": payload["execution_result"]}]}
