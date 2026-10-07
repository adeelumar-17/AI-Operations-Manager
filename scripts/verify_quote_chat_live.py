"""Run the requested real-Groq/PostgreSQL flow through the HTTP API handlers.

Creates ONE live quotation and applies discounts/approval to that quotation.
Does not seed records, alter customer tiers, convert orders or fulfill stock.
The process scheduler is disabled only inside this test process.
"""
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID
from sqlalchemy import select
from fastapi.testclient import TestClient
from backend.app.db.database import SessionLocal
from backend.app.db.models import Customer, Quote, User
from backend.app.services.authorization_service import discount_limit
from backend.app.services.quote_service import calculate_quote_total


def snapshot(quote_id):
    with SessionLocal() as db:
        quote = db.get(Quote, quote_id)
        return {"id": str(quote.id), "quote_number": quote.quote_number,
                "status": quote.status, "subtotal": str(quote.subtotal),
                "discount_percent": str(quote.discount_percent), "total": str(quote.total),
                "approval_id": str(quote.approval_id) if quote.approval_id else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true", help="Continue a recorded run that stopped after creating its quote")
    args = parser.parse_args()
    import backend.app.main as main_module
    main_module._SCHEDULER_ENABLED = False
    report = {"verification": "Real Groq and configured PostgreSQL via in-process HTTP TestClient; no LLM or database mocks",
              "started_at": datetime.now(timezone.utc).isoformat(), "steps": []}
    path = Path("QUOTE_CHAT_LIVE_RESULTS.json")
    if args.resume:
        report = json.loads(path.read_text(encoding="utf-8"))
        report.pop("error", None)
    try:
        with SessionLocal() as db:
            customer = db.scalars(select(Customer).where(Customer.name == "Ahmed Industries")).one()
            customer_id, threshold = customer.id, discount_limit(customer)
            reviewer = db.scalars(select(User).where(User.is_active.is_(True), User.role == "manager")).first()
            if reviewer is None:
                raise RuntimeError("An active manager database user is required.")
            headers = {"X-User-Id": str(reviewer.id)}
            before = set(db.scalars(select(Quote.id).where(Quote.customer_id == customer_id)))
        report["automatic_discount_threshold"] = str(threshold)
        with TestClient(main_module.app) as client:
            def call(label, method, url, body=None):
                response = client.request(method, url, headers=headers, json=body)
                result = response.json()
                report["steps"].append({"step": label, "method": method, "path": url,
                                        "request": body, "status_code": response.status_code, "response": result})
                path.write_text(json.dumps(report, indent=2), encoding="utf-8")
                response.raise_for_status()
                if isinstance(result, dict) and result.get("error"):
                    raise RuntimeError(result["error"])
                return result
            if args.resume:
                first = report["steps"][0]["response"]
                quote_id = UUID(report["created_quote"]["id"])
            else:
                first = call("1 — exact creation request", "POST", "/api/v1/chat",
                             {"message": "Create a quote for Ahmed Industries for 20 ergonomic chairs."})
                with SessionLocal() as db:
                    new = set(db.scalars(select(Quote.id).where(Quote.customer_id == customer_id))) - before
                if len(new) != 1:
                    raise AssertionError(f"Expected exactly one real new quote; found {len(new)}.")
                quote_id = new.pop()
                report["created_quote"] = snapshot(quote_id)
            text = first["response"].replace("\u2011", "-")
            if str(quote_id) not in text and report["created_quote"]["quote_number"] not in text:
                raise AssertionError("The creation response did not contain a usable quote identifier.")
            thread_id = first["thread_id"]
            second = call("2 — exact 15% request", "POST", "/api/v1/chat", {
                "message": f"Apply a 15% discount to quote {quote_id}.", "thread_id": thread_id})
            pending = call("3 — approvals after 15%", "GET", "/api/v1/approvals")
            if second["approval_required"]:
                approval_id = second["approval_id"]
            else:
                if threshold < 15:
                    raise AssertionError("Discount above the customer threshold bypassed approval.")
                report["steps"].append({"step": "4 — exact 15% approval", "result": "Not applicable: 15% does not exceed this customer's automatic limit."})
                report["quote_after_15_percent"] = snapshot(quote_id)
                extra = call("Supplement — 16% approval request", "POST", "/api/v1/chat", {
                    "message": f"Apply a 16% discount to quote {quote_id}.", "thread_id": thread_id})
                if not extra["approval_required"]:
                    raise AssertionError("The 16% request did not pause for approval.")
                approval_id = extra["approval_id"]
                pending = call("Supplement — approvals after 16%", "GET", "/api/v1/approvals")
            if not any(row["id"] == approval_id for row in pending):
                raise AssertionError("The new approval is absent from the pending API list.")
            report["quote_before_approval"] = snapshot(quote_id)
            call("4 / supplement — manager approval", "POST", f"/api/v1/approvals/{approval_id}/approve",
                 {"comment": "Manual verification of conversational quote creation and discount approval."})
            report["quote_after_approval"] = snapshot(quote_id)
            from decimal import Decimal
            after = report["quote_after_approval"]
            expected_percent = Decimal("15") if second["approval_required"] else Decimal("16")
            assert Decimal(after["discount_percent"]) == expected_percent
            assert Decimal(after["total"]) == calculate_quote_total(Decimal(after["subtotal"]), expected_percent)
            assert after["status"] == "approved"
    except Exception as exc:
        report["error"] = str(exc)
        raise
    finally:
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Actual HTTP responses recorded in {path}.")
        from agents.memory.checkpointer import close_checkpointer
        close_checkpointer()


if __name__ == "__main__":
    main()
