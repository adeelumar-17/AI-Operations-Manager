'''
This module defines the InventoryService, which provides methods for managing and tracking inventory items. It includes functionality for adding, updating, and removing inventory items, as well as checking stock levels and generating reports.
Classes:
    FulfillmentResult: Represents the result of a fulfillment feasibility check, including whether the requested quantity can be fulfilled, requested quantity, available quantity, and shortage quantity.
    InventoryService: Provides methods for managing and tracking inventory items and executing stock operations.
Methods:
    check_fulfillment_feasibility: Checks if a requested quantity can be fulfilled based on available stock.
    check_stock: Validates if a specific product has enough stock to fulfill a requested quantity.
    list_low_stock: Lists all products whose stock level is at or below their reorder threshold.
    update_inventory: Atomically updates product stock quantity and records a ledger entry in the inventory table.
'''
from dataclasses import dataclass
from uuid import UUID

from backend.app.services.exceptions import (
    InsufficientStockError,
    NotFoundError,
    ValidationError,
)


@dataclass(frozen=True)
class FulfillmentResult:
    feasible: bool
    requested_quantity: int
    available_quantity: int
    shortage_quantity: int


def check_fulfillment_feasibility(
    available_quantity: int,
    requested_quantity: int,
) -> FulfillmentResult:
    if available_quantity < 0:
        raise ValueError("Available quantity cannot be negative.")

    if requested_quantity <= 0:
        raise ValueError("Requested quantity must be greater than zero.")

    shortage_quantity = max(
        requested_quantity - available_quantity,
        0,
    )

    return FulfillmentResult(
        feasible=shortage_quantity == 0,
        requested_quantity=requested_quantity,
        available_quantity=available_quantity,
        shortage_quantity=shortage_quantity,
    )


class InventoryService:
    def __init__(
        self,
        product_repository,
        inventory_repository,
    ):
        self.product_repository = product_repository
        self.inventory_repository = inventory_repository

    def check_stock(
        self,
        product_id: UUID,
        requested_quantity: int,
    ) -> bool:
        if requested_quantity <= 0:
            raise ValidationError(
                "Requested quantity must be greater than zero."
            )

        product = self.product_repository.get_by_id(product_id)

        if product is None:
            raise NotFoundError(f"Product {product_id} was not found.")

        result = check_fulfillment_feasibility(
            available_quantity=product.stock_quantity,
            requested_quantity=requested_quantity,
        )

        return result.feasible

    def check_fulfillment_feasibility(
        self,
        available_quantity: int,
        requested_quantity: int,
    ) -> FulfillmentResult:
        return check_fulfillment_feasibility(available_quantity, requested_quantity)

    def list_low_stock(self):
        return self.product_repository.list_low_stock()

    def update_inventory(
        self,
        product_id: UUID,
        change_quantity: int,
        reason: str,
        reference_type: str | None = None,
        reference_id: UUID | None = None,
    ):
        if change_quantity == 0:
            raise ValidationError("Inventory change cannot be zero.")

        product = self.product_repository.get_by_id(product_id)

        if product is None:
            raise NotFoundError(f"Product {product_id} was not found.")

        resulting_balance = product.stock_quantity + change_quantity

        if resulting_balance < 0:
            raise InsufficientStockError(
                f"Product {product_id} does not have enough stock."
            )

        product.stock_quantity = resulting_balance
        self.product_repository.save(product)

        return self.inventory_repository.record_change(
            product_id=product_id,
            change_quantity=change_quantity,
            reason=reason,
            resulting_balance=resulting_balance,
            reference_type=reference_type,
            reference_id=reference_id,
        )