"""Reject nonzero measurements silently underflowing to binary64 zero.

On the previous real modules these 9 negative cases failed; after the narrow
fix they pass, while explicit exact zeros still preserve legacy behavior.
These tests cover module boundaries only, not full AEC/SQLite/Qt/Windows.
"""
from decimal import Decimal

import pytest

from core.takeoff.modules.mechanical import calculate_mechanical_item
from core.takeoff.modules.electrical import calculate_electrical_item


@pytest.mark.parametrize("route,kwargs", [
    ("pipe", {"length": "1e-400", "count": 2}),
    ("pipe", {"length": "-1e-400", "count": 2}),
    ("duct_area", {"width": "1e-400", "height": 0.25, "length": 2}),
    ("insulation", {"diameter": Decimal("1e-400"), "length": 3}),
    ("equipment", {"count": "1e-400"}),
])
def test_mechanical_underflow_rejected(route, kwargs):
    with pytest.raises(ValueError, match="underflow"):
        calculate_mechanical_item(route, **kwargs)


@pytest.mark.parametrize("route,kwargs", [
    ("cable", {"length": "1e-400", "count": 2}),
    ("conduit", {"length": "1e-400", "count": 2}),
    ("panel", {"count": Decimal("1e-400")}),
    ("light", {"count": "-1e-400"}),
])
def test_electrical_underflow_rejected(route, kwargs):
    with pytest.raises(ValueError, match="underflow"):
        calculate_electrical_item(route, **kwargs)


@pytest.mark.parametrize("route,kwargs,expected", [
    ("pipe", {"length": "0e-400", "count": 2}, 0),
    ("equipment", {"count": "0.000"}, 0),
])
def test_legitimate_zero_is_not_confused_with_underflow_mechanical(route, kwargs, expected):
    assert calculate_mechanical_item(route, **kwargs).quantity == expected


@pytest.mark.parametrize("route,kwargs,expected", [
    ("cable", {"length": "0e-400", "count": 2}, 0),
    ("panel", {"count": "0.000"}, 0),
])
def test_legitimate_zero_is_not_confused_with_underflow_electrical(route, kwargs, expected):
    assert calculate_electrical_item(route, **kwargs).quantity == expected
