'''
This module defines the API routes for order management and fulfillment tracking. It provides endpoints for retrieving order details, itemized totals, and status progression.
Classes:
    None (FastAPI router module).
Methods:
    get_order: GET endpoint to retrieve details for a specific order by its unique identifier.
'''

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_db, get_current_user
from backend.app.db.repositories.order_repository import OrderRepository

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.get("/{order_id}")
def get_order(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Retrieve order details."""
    repo = OrderRepository(db)
    order = repo.get_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    return {
        "id": str(order.id),
        "order_number": order.order_number,
        "customer_id": str(order.customer_id),
        "status": order.status,
        "total": float(order.total) if order.total else 0.0,
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }
