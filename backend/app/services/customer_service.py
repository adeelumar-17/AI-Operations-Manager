'''
This module defines the CustomerService class, which provides methods for managing customer-related operations in the application. The service interacts with various repositories to perform actions such as searching for customers, retrieving customer details, and fetching order, invoice, and communication histories. The CustomerService class serves as a bridge between the application's business logic and the underlying data storage, encapsulating the necessary operations to manage customer data effectively.
Classes:
    CustomerService: A class that provides methods for managing customer-related operations.
Methods:
    search_customers: Searches for customers based on a query string.
    get_customer: Retrieves customer details by customer ID.
    get_order_history: Fetches the order history for a specific customer.
    get_invoice_history: Fetches the invoice history for a specific customer.
    get_communication_history: Fetches the communication history for a specific customer.
    get_customer_history: Retrieves a comprehensive history of a customer's interactions, including orders, invoices, and communications.
'''
from uuid import UUID

from backend.app.services.exceptions import NotFoundError, ValidationError


class CustomerService:
    def __init__(
        self,
        customer_repository,
        order_repository,
        invoice_repository,
        communication_repository,
    ):
        self.customer_repository = customer_repository
        self.order_repository = order_repository
        self.invoice_repository = invoice_repository
        self.communication_repository = communication_repository

    def search_customers(self, query: str):
        normalized_query = query.strip()

        if not normalized_query:
            raise ValidationError("Customer search query cannot be empty.")

        return self.customer_repository.search(normalized_query)

    def get_customer(self, customer_id: UUID):
        customer = self.customer_repository.get_by_id(customer_id)

        if customer is None:
            raise NotFoundError(
                f"Customer {customer_id} was not found."
            )

        return customer

    def get_order_history(self, customer_id: UUID):
        self.get_customer(customer_id)

        return self.order_repository.list_by_customer(customer_id)

    def get_invoice_history(self, customer_id: UUID):
        self.get_customer(customer_id)

        return self.invoice_repository.list_by_customer(customer_id)

    def get_communication_history(self, customer_id: UUID):
        self.get_customer(customer_id)

        return self.communication_repository.list_by_customer(customer_id)

    def get_customer_history(self, customer_id: UUID) -> dict:
        self.get_customer(customer_id)

        return {
            "orders": self.order_repository.list_by_customer(customer_id),
            "invoices": self.invoice_repository.list_by_customer(customer_id),
            "communications": (
                self.communication_repository.list_by_customer(customer_id)
            ),
        }