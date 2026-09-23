'''
This module defines the CustomerRepository class, which provides methods for interacting with the Customer model in the database. The repository allows listing all customers, searching for customers based on a query string, and retrieving a customer by their unique identifier (UUID).
Classes:
    CustomerRepository: A class that provides methods for interacting with the Customer model.
Methods:
    list_all: Retrieves all customers, ordered by name, up to an optional limit.
    search: Searches for customers based on a query string.
    get_by_id: Retrieves a customer by their unique identifier (UUID).
'''
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.app.db.models.customer import Customer


class CustomerRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_all(self, limit: int = 50) -> list[Customer]:
        statement = select(Customer).order_by(Customer.name).limit(limit)
        return list(self.session.scalars(statement).all())

    def search(self, query: str, limit: int | None = None) -> list[Customer]:
        statement = (
            select(Customer)
            .where(
                or_(
                    Customer.name.ilike(f"%{query}%"),
                    Customer.email.ilike(f"%{query}%"),
                    Customer.company_name.ilike(f"%{query}%"),
                )
            )
            .order_by(Customer.name)
        )

        if limit is not None:
            statement = statement.limit(limit)
        return list(self.session.scalars(statement).all())

    def get_by_id(self, customer_id: UUID) -> Customer | None:
        return self.session.get(Customer, customer_id)
