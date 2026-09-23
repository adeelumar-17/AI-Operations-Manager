'''
This module defines custom exceptions for the business service layer of the application. These exceptions are used to handle various error scenarios that may occur during the execution of business logic, such as when a requested domain object does not exist, when input violates a business rule, when requested quantity cannot be fulfilled, or when an entity cannot move to the requested status.
Classes:
    ServiceError: Base exception for business-service failures.
    NotFoundError: Raised when a requested domain object does not exist.
    ValidationError: Raised when input violates a business rule.
    InsufficientStockError: Raised when requested quantity cannot be fulfilled.
    InvalidStatusTransitionError: Raised when an entity cannot move to the requested status.
'''
class ServiceError(Exception):
    """Base exception for business-service failures."""


class NotFoundError(ServiceError):
    """Raised when a requested domain object does not exist."""


class ValidationError(ServiceError):
    """Raised when input violates a business rule."""


class InsufficientStockError(ServiceError):
    """Raised when requested quantity cannot be fulfilled."""


class InvalidStatusTransitionError(ServiceError):
    """Raised when an entity cannot move to the requested status."""


class ApprovalRequired(ServiceError):
    """A validated proposed action that must be reviewed before execution."""

    def __init__(self, action_type: str, payload: dict, reason: str):
        super().__init__(reason)
        self.action_type = action_type
        self.payload = payload
        self.reason = reason
