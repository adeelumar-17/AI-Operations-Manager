from decimal import Decimal

import pytest

from backend.app.services.authorization_service import (
    check_discount_authorization,
    check_refund_authorization,
)


def test_discount_at_threshold_does_not_require_approval():
    result = check_discount_authorization(
        discount_percent=Decimal("10"),
        approval_threshold=Decimal("10"),
    )

    assert result.approval_required is False
    assert result.reason is None


def test_discount_below_threshold_does_not_require_approval():
    result = check_discount_authorization(
        discount_percent=Decimal("9.99"),
        approval_threshold=Decimal("10"),
    )

    assert result.approval_required is False
    assert result.reason is None


def test_discount_above_threshold_requires_approval():
    result = check_discount_authorization(
        discount_percent=Decimal("10.01"),
        approval_threshold=Decimal("10"),
    )

    assert result.approval_required is True
    assert result.reason is not None


def test_refund_below_threshold_does_not_require_approval():
    result = check_refund_authorization(
        refund_amount=Decimal("499.99"),
        approval_threshold=Decimal("500"),
    )

    assert result.approval_required is False
    assert result.reason is None


def test_refund_at_threshold_does_not_require_approval():
    result = check_refund_authorization(
        refund_amount=Decimal("500"),
        approval_threshold=Decimal("500"),
    )

    assert result.approval_required is False


def test_refund_above_threshold_requires_approval():
    result = check_refund_authorization(
        refund_amount=Decimal("500.01"),
        approval_threshold=Decimal("500"),
    )

    assert result.approval_required is True
    assert result.reason is not None


def test_negative_discount_is_rejected():
    with pytest.raises(ValueError):
        check_discount_authorization(
            discount_percent=Decimal("-1"),
            approval_threshold=Decimal("10"),
        )


def test_negative_refund_is_rejected():
    with pytest.raises(ValueError):
        check_refund_authorization(
            refund_amount=Decimal("-1"),
            approval_threshold=Decimal("500"),
        )