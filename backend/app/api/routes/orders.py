'''
This module defines the API routes for order management and fulfillment tracking. It provides endpoints for listing all orders, retrieving order details, itemized totals, and status progression.
Classes:
    None (FastAPI router module).
Methods:
    _format_order: Internal helper to serialize an Order SQLAlchemy model into a standardized dictionary.
    list_orders: GET endpoint to list all orders with optional status filtering.
    get_order: GET endpoint to retrieve details for a specific order by its unique identifier.
'''

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.app.api.dependencies import get_db, get_current_user
from backend.app.db.models.order import Order

router = APIRouter(prefix="/orders", tags=["Orders"])


def _format_order(order) -> dict:
    return {
        "id": str(order.id),
        "order_number": order.order_number,
        "customer_id": str(order.customer_id),
        "customer_name": order.customer.name if order.customer else "Customer",
        "status": order.status,
        "total": float(order.total) if order.total else 0.0,
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }


@router.get("")
def list_orders(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all orders, optionally filtered by status."""
    if status and status not in {"all", "pending", "processing", "shipped", "delivered", "cancelled"}:
        raise HTTPException(status_code=422, detail="Invalid order status.")
    stmt = select(Order).options(joinedload(Order.customer)).order_by(Order.created_at.desc())
    if status and status != "all":
        stmt = stmt.where(Order.status == status)
    orders = db.scalars(stmt).all()
    return [_format_order(o) for o in orders]


@router.get("/{order_id}")
def get_order(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Retrieve order details."""
    stmt = select(Order).options(joinedload(Order.customer)).where(Order.id == order_id)
    order = db.scalars(stmt).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    return _format_order(order)
