from decimal import Decimal
import pytest

from core.estimate.boq_estimate_cost_control_v1 import (
    BOQLine, CostEntry, RateLine, build_estimate, control_costs,
    estimate_fingerprint, total_estimate,
)


def boq(q="10"):
    return BOQLine("L1", "C01", "Concrete", "m3", Decimal(q), "DRAW-1", "R1")


def rate(r="100"):
    return RateLine("C01", "m3", Decimal(r), "IRR", "PRICE-1", "2026.1", "DOC/P1")


def test_estimate_is_deterministic_and_transparent():
    lines = build_estimate((boq(),), (rate(),))
    assert lines[0].amount == Decimal("1000")
    assert total_estimate(lines, "IRR") == Decimal("1000")
    assert estimate_fingerprint(lines) == estimate_fingerprint(lines)


def test_missing_price_fails_closed():
    with pytest.raises(LookupError):
        build_estimate((boq(),), ())


def test_unit_mismatch_fails_closed():
    with pytest.raises(ValueError):
        build_estimate((boq(),), (RateLine("C01", "kg", Decimal("1"), "IRR", "P", "V", "REF"),))


def test_duplicate_boq_ids_fail():
    with pytest.raises(ValueError):
        build_estimate((boq(), boq()), (rate(),))


def test_mixed_currency_is_rejected():
    lines = build_estimate((boq(),), (rate(),))
    changed = lines[0].__class__(**{**lines[0].__dict__, "currency": "IRT"})
    with pytest.raises(ValueError):
        total_estimate((changed,), "IRR")


def test_cost_control_is_explicit():
    result = control_costs(
        Decimal("1000"),
        (CostEntry("E1", "L1", Decimal("250"), "IRR", "INV-1"),),
        "IRR",
    )
    assert result.actual == Decimal("250")
    assert result.remaining == Decimal("750")


def test_duplicate_cost_entry_fails():
    entry = CostEntry("E1", "L1", Decimal("1"), "IRR", "INV-1")
    with pytest.raises(ValueError):
        control_costs(Decimal("2"), (entry, entry), "IRR")


def test_negative_values_fail_closed():
    with pytest.raises(ValueError):
        build_estimate((boq("-1"),), (rate(),))
