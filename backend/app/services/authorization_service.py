'''
This module provides functions to check if certain actions, such as applying a discount or issuing a refund, require approval based on predefined business rules. The `ApprovalDecision` dataclass encapsulates the result of the authorization check, indicating whether approval is required and providing a reason if applicable.
Classes:
    ApprovalDecision: A dataclass to represent the result of an authorization check.
Methods:
    check_discount_authorization: Checks if a discount requires approval based on the discount percentage and a maximum allowed percentage.
    check_refund_authorization: Checks if a refund requires approval based on the refund amount and a maximum allowed amount.
'''

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class AuthorizationResult:
    approval_required: bool
    reason: str | None = None


def check_discount_authorization(
    discount_percent: Decimal,
    approval_threshold: Decimal,
) -> AuthorizationResult:
    if discount_percent < Decimal("0"):
        raise ValueError("Discount percentage cannot be negative.")

    if discount_percent > Decimal("100"):
        raise ValueError("Discount percentage cannot exceed 100.")

    if approval_threshold < Decimal("0"):
        raise ValueError("Approval threshold cannot be negative.")

    if discount_percent > approval_threshold:
        return AuthorizationResult(
            approval_required=True,
            reason=(
                f"Discount of {discount_percent}% exceeds the "
                f"approval threshold of {approval_threshold}%."
            ),
        )

    return AuthorizationResult(approval_required=False)


def check_refund_authorization(
    refund_amount: Decimal,
    approval_threshold: Decimal,
) -> AuthorizationResult:
    if refund_amount < Decimal("0"):
        raise ValueError("Refund amount cannot be negative.")

    if approval_threshold < Decimal("0"):
        raise ValueError("Approval threshold cannot be negative.")

    if refund_amount > approval_threshold:
        return AuthorizationResult(
            approval_required=True,
            reason=(
                f"Refund amount of {refund_amount} exceeds the "
                f"approval threshold of {approval_threshold}."
            ),
        )

    return AuthorizationResult(approval_required=False)