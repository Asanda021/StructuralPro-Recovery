"""Exact, fail-closed Decimal operations shared by existing report projections.

This module only prepares read-only reporting values. It is not a second BOQ,
measurement or pricing engine and never rounds an approved source amount.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, localcontext


def decimal_value(value, *, field="amount", non_negative=False):
    """Parse an existing numeric value without a binary-float intermediate."""
    if value is None:
        result = Decimal(0)
    elif isinstance(value, bool) or value == "":
        raise ValueError(f"{field} must be numeric")
    else:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError(f"{field} must be numeric") from exc
    if not result.is_finite():
        raise ValueError(f"{field} must be finite")
    if non_negative and result < 0:
        raise ValueError(f"{field} must be non-negative")
    return result


def exact_sum(values, *, field="amount"):
    """Sum existing decimals with enough context precision to retain all digits.

    Python's default Decimal precision (28) can round large subtotals. The
    requested precision spans the largest integer position and smallest decimal
    position in the actual input, plus guard digits for carry.
    """
    numbers = [decimal_value(value, field=field) for value in values]
    if not numbers:
        return Decimal(0)
    low = min(value.as_tuple().exponent for value in numbers)
    high = max(value.adjusted() for value in numbers)
    with localcontext() as ctx:
        ctx.prec = max(28, high - low + len(str(len(numbers))) + 2)
        return sum(numbers, Decimal(0))
