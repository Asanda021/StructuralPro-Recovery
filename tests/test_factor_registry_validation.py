import math

import pytest

from core.pricing.factors import FactorRegistry, FactorSet


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), "nan", "inf", -1.000001])
def test_factor_registry_rejects_nonfinite_and_below_minus_one_rates(value):
    with pytest.raises(ValueError, match="factor rate"):
        FactorRegistry([FactorSet(1405, "پیمان", {"overhead": value})])


def test_factor_registry_accepts_explicit_finite_rates_and_full_discount():
    registry = FactorRegistry([FactorSet(1405, "پیمان", {"discount": -1, "overhead": 0.1})])
    assert registry.rates(1405, "پیمان") == {"discount": -1.0, "overhead": 0.1}


def test_factor_registry_rejects_blank_set_and_factor_names():
    with pytest.raises(ValueError, match="set name"):
        FactorRegistry([FactorSet(1405, "  ", {"overhead": 0.1})])
    with pytest.raises(ValueError, match="factor name"):
        FactorRegistry([FactorSet(1405, "پیمان", {" ": 0.1})])


def test_factor_registry_normalizes_names_and_prevents_mutable_aliases():
    source = {"overhead": 0.1}
    item = FactorSet(1405, " پیمان ", source)
    registry = FactorRegistry([item])
    source["overhead"] = float("inf")
    assert registry.rates(1405, "پیمان") == {"overhead": 0.1}
    returned = registry.rates(1405, "پیمان")
    returned["overhead"] = 99
    assert registry.rates(1405, "پیمان") == {"overhead": 0.1}


def test_factor_registry_rejects_duplicate_normalized_names():
    with pytest.raises(ValueError, match="duplicate factor"):
        FactorRegistry([FactorSet(1405, "پیمان", {"overhead": 0.1, " overhead ": 0.2})])


def test_factor_registry_retains_audit_metadata():
    registry = FactorRegistry([FactorSet(1405, "پیمان", {"overhead": 0.1}, source="contract", effective_date="1405-01-01")])
    detail = registry.describe(1405, "پیمان")
    assert detail["source"] == "contract"
    assert detail["effective_date"] == "1405-01-01"


def test_get_cannot_mutate_validated_registry_state():
    registry = FactorRegistry([FactorSet(1405, "پیمان", {"overhead": 0.1})])
    returned = registry.get(1405, "پیمان")
    returned.factors["overhead"] = float("nan")
    returned.factors["injected"] = float("inf")
    assert registry.rates(1405, "پیمان") == {"overhead": 0.1}
    assert registry.describe(1405, "پیمان")["factors"] == {"overhead": 0.1}


@pytest.mark.parametrize("year", [1405.5, "1405.5", True, float("inf"), float("nan")])
def test_fractional_or_nonfinite_years_are_not_coerced(year):
    with pytest.raises(ValueError, match="invalid year"):
        FactorRegistry([FactorSet(year, "پیمان", {"overhead": 0.1})])
