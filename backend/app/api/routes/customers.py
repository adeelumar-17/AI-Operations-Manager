'''
This module defines the API routes for customer management. It provides endpoints for listing and searching customer accounts, as well as retrieving individual customer account profiles and tier information.
Classes:
    None (FastAPI router module).
Methods:
    list_customers: GET endpoint to list all customer accounts or filter customers by search query.
    get_customer: GET endpoint to retrieve details for a specific customer by their unique identifier.
'''

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_db, get_current_user
from backend.app.db.repositories.customer_repository import CustomerRepository

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("")
def list_customers(
    query: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Search or list customers."""
    repo = CustomerRepository(db)
    customers = repo.search(query) if query else repo.list_all(limit=limit)

    return [
        {
            "id": str(c.id),
            "name": c.name,
            "email": c.email,
            "company_name": c.company_name,
            "tier": getattr(c, "tier", "regular"),
        }
        for c in customers
    ]


@router.get("/{customer_id}")
def get_customer(
    customer_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get customer by ID."""
    repo = CustomerRepository(db)
    customer = repo.get_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found.")
    return {
        "id": str(customer.id),
        "name": customer.name,
        "email": customer.email,
        "company_name": customer.company_name,
        "tier": getattr(customer, "tier", "regular"),
    }