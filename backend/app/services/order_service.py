"""
This module defines the OrderService class, which provides business logic for managing orders. The OrderService class is initialized with an order repository and an inventory service, and provides methods for retrieving orders, transitioning order statuses, fulfilling orders, and calculating order subtotals.
Classes:
    OrderService: A class that provides business logic for managing orders.
Methods:
    get_order: Retrieves an order by its ID, raising a NotFoundError if the order does not exist.
    get_order_details: Retrieves an order and its associated items by order ID.
    transition_status: Transitions an order to a new status, raising an InvalidStatusTransitionError if the transition is not allowed.
    fulfill_order: Marks an order as fulfilled, checking inventory and updating stock levels.
    cancel_order: Cancels a pending order, raising an InvalidStatusTransitionError if the order is not pending.
    calculate_order_subtotal: Calculates the subtotal of an order based on its items.
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from backend.app.db.models.order import Order
from backend.app.db.models.order_item import OrderItem
from backend.app.services.exceptions import (
    InsufficientStockError,
    InvalidStatusTransitionError,
    NotFoundError,
)


ALLOWED_TRANSITIONS = {
    "pending": {"processing", "cancelled"},
    "processing": {"shipped"},
    "shipped": {"delivered"},
    "delivered": set(),
    "cancelled": set(),
}

class OrderService:
    def __init__(
        self,
        order_repository,
        inventory_service,
    ):
        self.order_repository = order_repository
        self.inventory_service = inventory_service

    def get_order(self, order_id: UUID) -> Order:
        order = self.order_repository.get_with_items(order_id)

        if order is None:
            raise NotFoundError(f"Order {order_id} was not found.")

        return order

    def get_order_details(self, order_id: UUID) -> dict:
        order = self.get_order(order_id)
        return {"order": order, "items": order.items}

    def transition_status(
        self,
        order_id: UUID,
        new_status: str,
    ) -> Order:
        order = self.get_order(order_id)
        allowed_statuses = ALLOWED_TRANSITIONS.get(order.status, set())

        if new_status not in ALLOWED_TRANSITIONS:
            raise InvalidStatusTransitionError(
                f"Unknown order status: {new_status}."
            )

        if new_status not in allowed_statuses:
            raise InvalidStatusTransitionError(
                f"Cannot move order from {order.status} to {new_status}."
            )

        if new_status == "processing":
            return self.fulfill_order(order_id)

        order.status = new_status
        now = datetime.now(timezone.utc)

        if new_status == "shipped":
            order.shipped_at = now
        elif new_status == "delivered":
            order.delivered_at = now

        return self.order_repository.save(order)

    def fulfill_order(self, order_id: UUID) -> Order:
        order = self.get_order(order_id)
        if order.status != "pending":
            raise InvalidStatusTransitionError(
                f"Order {order_id} is not pending and cannot be fulfilled."
            )

        for item in order.items:
            if not self.inventory_service.check_stock(
                product_id=item.product_id,
                requested_quantity=item.quantity,
            ):
                raise InsufficientStockError(
                    f"Insufficient stock for product {item.product_id}."
                )

        for item in order.items:
            self.inventory_service.update_inventory(
                product_id=item.product_id,
                change_quantity=-item.quantity,
                reason="order_fulfilled",
                reference_type="order",
                reference_id=order.id,
            )

        order.status = "processing"
        return self.order_repository.save(order)

    def cancel_order(self, order_id: UUID) -> Order:
        order = self.get_order(order_id)
        if order.status != "pending":
            raise InvalidStatusTransitionError(
                "Only pending orders can be cancelled."
            )

        order.status = "cancelled"
        return self.order_repository.save(order)

    @staticmethod
    def calculate_order_subtotal(items: list[OrderItem]) -> Decimal:
        return sum(
            (item.line_total for item in items),
            Decimal("0.00"),
        )
