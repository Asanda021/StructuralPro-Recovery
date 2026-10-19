"""Fail-closed overflow regressions for the actual mechanical/electrical modules.

Both modules previously allowed finite operands with an infinite PRODUCT.
The unified TakeoffEngine had a downstream finite guard; direct module callers
must never receive a nonfinite calculated physical quantity either.
"""
import pytest
from core.takeoff.modules.mechanical import calculate_mechanical_item
from core.takeoff.modules.electrical import calculate_electrical_item

@pytest.mark.parametrize("route,params", (
    ("pipe", {"length": "1e308", "count": "2"}),
    ("duct", {"length": "1e308", "count": "2"}),
    ("duct_area", {"width": "1e308", "height": "1e308", "length": "2"}),
    ("insulation", {"diameter": "1e308", "length": "2"}),
))
def test_mechanical_overflow_is_blocked_at_module_boundary(route, params):
    with pytest.raises(ValueError, match="derived quantity must be finite"):
        calculate_mechanical_item(route, **params)

@pytest.mark.parametrize("route,params", (
    ("cable", {"length": "1e308", "count": "2"}),
    ("conduit", {"length": "1e308", "count": "2"}),
    ("cable_tray", {"length": "1e308", "count": "2"}),
))
def test_electrical_overflow_is_blocked_at_module_boundary(route, params):
    with pytest.raises(ValueError, match="derived quantity must be finite"):
        calculate_electrical_item(route, **params)

@pytest.mark.parametrize("route,params,expected,unit", (
    ("pipe", {"length": "7.5", "count": "2"}, 15, "m"),
    ("equipment", {"count": "3"}, 3, "عدد"),
    ("duct_area", {"width": ".4", "height": ".25", "length": "12.5"}, 16.25, "m2"),
))
def test_mechanical_valid_existing_quantities_unchanged(route, params, expected, unit):
    result = calculate_mechanical_item(route, **params)
    assert result.quantity == pytest.approx(expected) and result.unit == unit

@pytest.mark.parametrize("route,params,expected,unit", (
    ("cable", {"length": "6.75", "count": "2"}, 13.5, "m"),
    ("panel", {"count": "2"}, 2, "عدد"),
    ("light", {"count": "3"}, 3, "عدد"),
))
def test_electrical_valid_existing_quantities_unchanged(route, params, expected, unit):
    result = calculate_electrical_item(route, **params)
    assert result.quantity == pytest.approx(expected) and result.unit == unit
