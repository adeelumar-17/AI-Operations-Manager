'''
what the file does?
This module provides LangChain-compatible inventory tools for the operations agent, wrapping InventoryService to allow checking stock levels, updating inventory balances, validating order fulfillment feasibility, and listing low-stock products.

Classes:
    None (LangChain tool definition module)

Methods:
    _make_inventory_service: Helper factory creating an InventoryService instance with a fresh DB session.
    _find_product: Resolves a product by UUID, SKU, or fuzzy search across names and SKUs.
    check_stock: Tool to check available, reserved, and total inventory for a product by UUID or SKU.
    update_inventory: Tool to adjust inventory quantities (restock, cycle count, or deduction).
    check_fulfillment_feasibility: Tool to determine whether a multi-item order can be fulfilled given current stock.
    get_low_stock_products: Tool returning all products at or below their reorder thresholds.
'''

import json
from typing import Annotated
from uuid import UUID

from langchain_core.tools import tool

from backend.app.db.database import SessionLocal
from backend.app.db.repositories.inventory_repository import InventoryRepository
from backend.app.db.repositories.product_repository import ProductRepository
from backend.app.services.inventory_service import InventoryService


def _make_inventory_service() -> tuple[InventoryService, object]:
    session = SessionLocal()
    service = InventoryService(
        product_repository=ProductRepository(session),
        inventory_repository=InventoryRepository(session),
    )
    return service, session


def _find_product(repo: ProductRepository, identifier: str):
    """Find a product by UUID, exact SKU, or fuzzy name/SKU."""
    if not identifier:
        return None
    val_str = str(identifier).strip()
    # 1. Try UUID
    try:
        val_uuid = UUID(val_str)
        product = repo.get_by_id(val_uuid)
        if product:
            return product
    except (ValueError, AttributeError):
        pass

    # 2. Try exact SKU
    product = repo.get_by_sku(val_str)
    if product:
        return product

    # 3. Try search by name or SKU
    matches = repo.search_by_name_or_sku(val_str)
    if matches:
        return matches[0]

    return None


@tool
def check_stock(
    product_id: Annotated[str, "Product UUID, SKU (e.g. 'SKU-1234'), or product name to check"],
    requested_quantity: Annotated[int, "Number of units requested. If 0 or omitted, returns current available stock level."] = 0,
) -> str:
    """Check stock availability for a product or query current stock levels.

    Accepts a product UUID, SKU (e.g. 'SKU-1234'), or product name.
    If requested_quantity is > 0, checks if stock is sufficient to fulfill that quantity.
    If requested_quantity is 0 (or not specified), returns current available stock and reorder threshold.
    """
    service, session = _make_inventory_service()
    try:
        from backend.app.services.inventory_service import check_fulfillment_feasibility
        product = _find_product(service.product_repository, product_id)
        if product is None:
            return f"Product '{product_id}' not found."

        # If checking current stock level without a specific purchase quantity
        if requested_quantity is None or requested_quantity <= 0:
            return (
                f"Current stock for '{product.name}' (SKU: {product.sku}):\n"
                f"  Available stock: {product.stock_quantity} units\n"
                f"  Reorder threshold: {product.reorder_threshold} units\n"
                f"  Unit price: ${float(product.unit_price):.2f}"
            )

        result = check_fulfillment_feasibility(
            available_quantity=product.stock_quantity,
            requested_quantity=requested_quantity,
        )
        if result.feasible:
            return (
                f"✓ Stock OK for '{product.name}' (SKU: {product.sku})\n"
                f"  Requested: {requested_quantity} | Available: {result.available_quantity}"
            )
        else:
            return (
                f"✗ Insufficient stock for '{product.name}' (SKU: {product.sku})\n"
                f"  Requested: {requested_quantity} | Available: {result.available_quantity} | "
                f"Shortage: {result.shortage_quantity}"
            )
    except Exception as e:
        return f"Error checking stock: {e}"
    finally:
        session.close()


@tool
def update_inventory(
    product_id: Annotated[str, "Product UUID, SKU (e.g. 'SKU-3001'), or product name to update"],
    change_quantity: Annotated[int, "Number of units to add (positive, e.g. 20 for restock) or remove (negative)"],
    reason: Annotated[str, "Reason for change: 'restock', 'manual_adjustment', 'order_fulfilled', 'order_cancelled', or 'return'"] = "restock",
) -> str:
    """Add or adjust stock for a product in inventory.

    Use when the user asks to add units, restock, or adjust inventory levels.
    """
    service, session = _make_inventory_service()
    try:
        product = _find_product(service.product_repository, product_id)
        if product is None:
            return f"Product '{product_id}' not found."

        valid_reasons = ("restock", "manual_adjustment", "order_fulfilled", "order_cancelled", "return")
        normalized_reason = reason.lower().strip()
        if normalized_reason not in valid_reasons:
            normalized_reason = "restock" if change_quantity > 0 else "manual_adjustment"

        old_quantity = product.stock_quantity
        service.update_inventory(
            product_id=product.id,
            change_quantity=change_quantity,
            reason=normalized_reason,
        )
        session.commit()
        new_quantity = old_quantity + change_quantity
        action_verb = "Added" if change_quantity > 0 else "Deducted"
        return (
            f"✓ Successfully {action_verb.lower()} {abs(change_quantity)} units for '{product.name}' (SKU: {product.sku}).\n"
            f"  Previous stock: {old_quantity} | New stock: {new_quantity} | Reason: {normalized_reason}"
        )
    except Exception as e:
        session.rollback()
        return f"Error updating inventory: {e}"
    finally:
        session.close()


@tool
def check_fulfillment_feasibility(
    items: Annotated[
        str,
        "JSON list of items to check, e.g. [{\"product_id\": \"uuid-or-sku\", \"quantity\": 10}]",
    ],
) -> str:
    """Check if an entire order (multiple products and quantities) can be fulfilled.

    Pass a JSON array of {product_id, quantity} objects (product_id can be UUID, SKU, or name).
    Returns per-product stock status and an overall feasibility verdict.
    """
    service, session = _make_inventory_service()
    try:
        item_list = json.loads(items)
        lines = ["Fulfillment feasibility check:"]
        all_feasible = True
        for item in item_list:
            raw_id = item.get("product_id") or item.get("sku") or item.get("product")
            qty = int(item.get("quantity", 0))
            product = _find_product(service.product_repository, raw_id)
            if product is None:
                lines.append(f"  ✗ Product '{raw_id}': NOT FOUND")
                all_feasible = False
                continue
            from backend.app.services.inventory_service import check_fulfillment_feasibility as cff
            result = cff(available_quantity=product.stock_quantity, requested_quantity=qty)
            if result.feasible:
                lines.append(f"  ✓ {product.name} (SKU: {product.sku}): OK ({product.stock_quantity} available, {qty} requested)")
            else:
                lines.append(
                    f"  ✗ {product.name} (SKU: {product.sku}): INSUFFICIENT "
                    f"({product.stock_quantity} available, {qty} requested, shortage: {result.shortage_quantity})"
                )
                all_feasible = False
        lines.append(f"\nOverall: {'FEASIBLE ✓' if all_feasible else 'NOT FEASIBLE ✗'}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error checking fulfillment feasibility: {e}"
    finally:
        session.close()


@tool
def get_low_stock_products() -> str:
    """List all products whose current stock is at or below their reorder threshold.

    Use when the user asks about low inventory, what needs restocking, or
    before committing to large orders.
    """
    service, session = _make_inventory_service()
    try:
        products = service.list_low_stock()
        if not products:
            return "All products are sufficiently stocked."
        lines = [f"Low-stock products ({len(products)}):"]
        for p in products:
            lines.append(
                f"  - {p.name} (SKU: {p.sku}) | "
                f"Stock: {p.stock_quantity} | Reorder threshold: {p.reorder_threshold}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving low-stock list: {e}"
    finally:
        session.close()

@tool
def get_all_products() -> str:
    """List every product in the catalog, regardless of stock level.

    Use when the user asks to see all products, the full catalog, or
    "what do we sell" — as opposed to get_low_stock_products, which only
    shows items needing reorder.
    """
    service, session = _make_inventory_service()
    try:
        products = service.product_repository.list_all()
        if not products:
            return "No products found in the catalog."
        lines = [f"Full product catalog ({len(products)} items):"]
        for p in products:
            lines.append(
                f"  - {p.name} (SKU: {p.sku}) | "
                f"Stock: {p.stock_quantity} | Price: ${float(p.unit_price):.2f} | Category: {p.category}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving product catalog: {e}"
    finally:
        session.close()