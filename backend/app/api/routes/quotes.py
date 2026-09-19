'''
This module defines the API routes for sales quotations. It provides endpoints for listing quotations with optional status filtering (such as pending_approval or approved) and retrieving detailed quote information including itemized line items and discounts.
Classes:
    None (FastAPI router module).
Methods:
    list_quotes: GET endpoint to list sales quotations, optionally filtered by status.
    get_quote: GET endpoint to retrieve detailed information for a specific quotation and its line items.
'''

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_db, get_current_user
from backend.app.db.repositories.quote_repository import QuoteRepository

router = APIRouter(prefix="/quotes", tags=["Quotes"])


@router.get("")
def list_quotes(
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all quotations, optionally filtered by status."""
    repo = QuoteRepository(db)
    quotes = repo.list_all(status=status)
    return [
        {
            "id": str(q.id),
            "quote_number": q.quote_number,
            "customer_id": str(q.customer_id),
            "customer_name": q.customer.name if getattr(q, "customer", None) else None,
            "status": q.status,
            "subtotal": float(q.subtotal) if q.subtotal else 0.0,
            "discount_percent": float(q.discount_percent) if q.discount_percent else 0.0,
            "discount_amount": float(q.discount_amount) if q.discount_amount else 0.0,
            "total": float(q.total) if q.total else 0.0,
            "approval_id": str(q.approval_id) if q.approval_id else None,
            "created_at": q.created_at.isoformat() if q.created_at else None,
            "items": [
                {
                    "product_id": str(item.product_id),
                    "quantity": item.quantity,
                    "unit_price": float(item.unit_price) if item.unit_price else 0.0,
                    "line_total": float(item.line_total) if item.line_total else 0.0,
                }
                for item in q.items
            ],
        }
        for q in quotes
    ]


@router.get("/{quote_id}")
def get_quote(
    quote_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Retrieve quote details and line items."""
    repo = QuoteRepository(db)
    quote = repo.get_with_items(quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found.")

    return {
        "id": str(quote.id),
        "quote_number": quote.quote_number,
        "customer_id": str(quote.customer_id),
        "status": quote.status,
        "subtotal": float(quote.subtotal) if quote.subtotal else 0.0,
        "discount_percent": float(quote.discount_percent) if quote.discount_percent else 0.0,
        "discount_amount": float(quote.discount_amount) if quote.discount_amount else 0.0,
        "total": float(quote.total) if quote.total else 0.0,
        "items": [
            {
                "product_id": str(item.product_id),
                "quantity": item.quantity,
                "unit_price": float(item.unit_price) if item.unit_price else 0.0,
                "line_total": float(item.line_total) if item.line_total else 0.0,
            }
            for item in quote.items
        ],
    }
