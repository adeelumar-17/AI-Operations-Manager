'''
This module defines the CustomerRepository class, which provides methods for interacting with the Customer model in the database. The repository allows searching for customers based on a query string and retrieving a customer by their unique identifier (UUID).
Classes:
    CustomerRepository: A class that provides methods for interacting with the Customer model.
Methods:
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

    def search(self, query: str) -> list[Customer]:
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

        return list(self.session.scalars(statement).all())

    def get_by_id(self, customer_id: UUID) -> Customer | None:
        return self.session.get(Customer, customer_id)