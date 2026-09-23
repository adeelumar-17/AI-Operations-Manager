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
import re


@dataclass(frozen=True)
class AuthorizationResult:
    approval_required: bool
    reason: str | None = None


def check_discount_authorization(
    discount_percent: Decimal,
    approval_threshold: Decimal,
) -> AuthorizationResult:
    if not discount_percent.is_finite() or not approval_threshold.is_finite():
        raise ValueError("Discount and threshold must be finite.")
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
    if not refund_amount.is_finite() or not approval_threshold.is_finite():
        raise ValueError("Refund and threshold must be finite.")
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


def customer_tier(customer) -> str:
    """Read the explicit legacy tier marker, never infer a tier with an LLM."""
    notes = getattr(customer, "notes", None) or ""
    return "preferred" if re.match(r"^\s*Preferred customer tier\b", notes, re.I) else "regular"


def discount_limit(customer) -> Decimal:
    return Decimal("15") if customer_tier(customer) == "preferred" else Decimal("10")
