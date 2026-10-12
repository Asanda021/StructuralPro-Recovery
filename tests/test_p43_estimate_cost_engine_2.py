from decimal import Decimal
import pytest

from core.estimate.estimate_cost_engine_v2 import (
    EstimateLine, CostRate, build_estimate, compare_scenarios,
)


def line(code="C01", category="material", qty="10", line_id="L1"):
    return EstimateLine(line_id, code, "Concrete", category, "m3", Decimal(qty), "Q-1")


def rate(code="C01", category="material", value="100", unit="m3", currency="IRR"):
    return CostRate(code, category, unit, Decimal(value), currency, "PRICE-1", "2026.1", "OFFICIAL/P1")


def test_material_labor_machinery_breakdown_is_explicit():
    rows = (
        line("C01", "material", "10"),
        EstimateLine("LAB1", "LAB", "Labor", "labor", "hr", Decimal("4"), "Q-2"),
        EstimateLine("M1", "MACH", "Machine", "machinery", "hr", Decimal("2"), "Q-3"),
    )
    rates = (
        rate("C01", "material", "100"),
        rate("LAB", "labor", "50", "hr"),
        rate("MACH", "machinery", "75", "hr"),
    )
    result = build_estimate(rows, rates, scenario="base")
    assert result.breakdown["material"] == Decimal("1000")
    assert result.breakdown["labor"] == Decimal("200")
    assert result.breakdown["machinery"] == Decimal("150")
    assert result.grand_total == Decimal("1350")


def test_missing_rate_fails_closed():
    with pytest.raises(LookupError):
        build_estimate((line(),), (), scenario="base")


def test_unit_and_category_are_exact():
    with pytest.raises(LookupError):
        build_estimate((line(),), (rate(unit="kg"),), scenario="base")
    with pytest.raises(LookupError):
        build_estimate((line(category="labor"),), (rate(),), scenario="base")


def test_duplicate_ids_and_rates_fail():
    with pytest.raises(ValueError):
        build_estimate((line(), line("C02")), (rate(),), scenario="base")
    with pytest.raises(ValueError):
        build_estimate((line(),), (rate(), rate()), scenario="base")


def test_mixed_currency_scenarios_are_rejected():
    a = build_estimate((line(),), (rate(),), scenario="base")
    b = build_estimate((line(),), (rate(currency="USD"),), scenario="usd")
    with pytest.raises(ValueError):
        compare_scenarios(a, b)


def test_scenario_comparison_is_explicit_and_deterministic():
    a = build_estimate((line(),), (rate(),), scenario="base")
    b = build_estimate((line(qty="12"),), (rate(),), scenario="high-quantity")
    result = compare_scenarios(a, b)
    assert result["scenarios"][0]["grand_total"] == Decimal("1000")
    assert result["scenarios"][1]["grand_total"] == Decimal("1200")
    assert a.fingerprint == build_estimate((line(),), (rate(),), scenario="base").fingerprint


def test_negative_quantity_or_rate_fails_closed():
    with pytest.raises(ValueError):
        build_estimate((line(qty="-1"),), (rate(),), scenario="base")
    with pytest.raises(ValueError):
        build_estimate((line(),), (rate(value="-1"),), scenario="base")


def test_unused_foreign_currency_rate_does_not_reject_estimate():
    result = build_estimate(
        (line(),),
        (rate(), rate(code="USD-ONLY", currency="USD")),
        scenario="base",
    )
    assert result.currency == "IRR"
    assert result.grand_total == Decimal("1000")


def test_mixed_currency_on_used_lines_is_rejected():
    rows = (
        line("C01", "material", "2", "L1"),
        EstimateLine("L2", "LAB", "Labor", "labor", "hr", Decimal("1"), "Q-2"),
    )
    with pytest.raises(ValueError, match="exactly one currency"):
        build_estimate(
            rows,
            (rate(), rate(code="LAB", category="labor", unit="hr", currency="USD")),
            scenario="mixed",
        )


def test_empty_estimate_is_rejected_explicitly():
    with pytest.raises(ValueError, match="at least one estimate line"):
        build_estimate((), (rate(),), scenario="empty")
