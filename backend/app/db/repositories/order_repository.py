'''
This module defines the OrderRepository class, which provides methods for interacting with the Order model in the database. The OrderRepository class is initialized with a SQLAlchemy Session object and provides a method to list orders by customer ID, returning a list of Order objects sorted by creation date in descending order.
Classes: 
    OrderRepository: A class that provides methods for interacting with the Order model.
Methods:
    list_by_customer: Lists orders associated with a specific customer ID, returning them in descending order of creation date.
    create_from_quote: Creates an Order from a Quote.
    get_by_id: Retrieves an Order by its ID.
    get_with_items: Retrieves an Order with its items.
    save: Saves an Order to the database.
'''
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.db.models.order import Order
from backend.app.db.models.order_item import OrderItem
from backend.app.db.models.quote import Quote


class OrderRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_by_customer(self, customer_id: UUID) -> list[Order]:
        statement = (
            select(Order)
            .where(Order.customer_id == customer_id)
            .order_by(Order.created_at.desc())
        )

        return list(self.session.scalars(statement).all())

    def create_from_quote(self, quote: Quote) -> Order:
        order = Order(
            order_number=f"ORD-{quote.quote_number}",
            customer_id=quote.customer_id,
            quote_id=quote.id,
            status="pending",
            subtotal=quote.subtotal,
            total=quote.total,
        )

        order.items = [
            OrderItem(
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=item.unit_price,
                line_total=item.line_total,
            )
            for item in quote.items
        ]

        self.session.add(order)
        self.session.flush()

        return order

    def get_by_id(self, order_id: UUID) -> Order | None:
        statement = select(Order).where(Order.id == order_id)

        result = self.session.scalars(statement).one_or_none()

        return result

    def get_with_items(self, order_id: UUID) -> Order | None:
        statement = (
            select(Order)
            .where(Order.id == order_id)
            .options(
                selectinload(Order.items),
            )
        )

        result = self.session.scalars(statement).one_or_none()

        return result

    def save(self, order: Order) -> Order:
        self.session.add(order)
        self.session.flush()

        return order