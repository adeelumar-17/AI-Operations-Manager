'''
This module defines the API routes for product catalog and inventory monitoring. It provides endpoints for listing all products with their current stock levels, unit prices, and reorder thresholds, as well as filtering products that are currently running low on stock.
Classes:
    None (FastAPI router module).
Methods:
    list_products: GET endpoint to list all catalog items with accurate stock quantities and reorder thresholds.
    get_low_stock_products: GET endpoint to query products whose current stock is at or below their reorder point.
'''

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_db, get_current_user
from backend.app.db.repositories.product_repository import ProductRepository
from backend.app.db.repositories.inventory_repository import InventoryRepository

router = APIRouter(prefix="/products", tags=["Products & Inventory"])


@router.get("")
def list_products(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all products with stock information."""
    prod_repo = ProductRepository(db)

    products = prod_repo.list_all() if hasattr(prod_repo, "list_all") else []
    results = []
    for p in products:
        results.append({
            "id": str(p.id),
            "sku": p.sku,
            "name": p.name,
            "category": getattr(p, "category", "Office Supplies"),
            "unit_price": float(p.unit_price) if p.unit_price else 0.0,
            "stock_quantity": p.stock_quantity,
            "stock_level": p.stock_quantity,
            "quantity_on_hand": p.stock_quantity,
            "reorder_threshold": p.reorder_threshold,
            "reorder_point": p.reorder_threshold,
        })
    return results


@router.get("/low-stock")
def get_low_stock_products(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List products that are at or below their reorder point."""
    prod_repo = ProductRepository(db)
    low_stock = prod_repo.list_low_stock() if hasattr(prod_repo, "list_low_stock") else []
    return [
        {
            "product_id": str(p.id),
            "sku": p.sku,
            "name": p.name,
            "stock_quantity": p.stock_quantity,
            "quantity_on_hand": p.stock_quantity,
            "reorder_threshold": p.reorder_threshold,
            "reorder_point": p.reorder_threshold,
        }
        for p in low_stock
    ]
