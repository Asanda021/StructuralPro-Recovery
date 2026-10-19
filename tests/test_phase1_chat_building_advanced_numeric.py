"""Phase 1: boundary regressions of the legacy Building/Advanced engines.

Run on real imported production modules. Prevent nonzero-to-zero conversion,
overflowed results, and count rounding. No engineering acceptance is implied.
"""
import pytest

from core.takeoff.modules.building import calculate_building_item
from core.takeoff.modules.advanced import calculate_advanced_item
from core.takeoff.modules import building, advanced


@pytest.mark.parametrize("route,params", [
    ("wall", {"length": 2, "height": 3, "openings": "1e-400"}),
    ("tile", {"length": 2, "height": 3, "waste": "1e-400"}),
    ("rebar", {"length": 2, "unit_weight": 2, "count": 1,
               "bend_length": "1e-400", "hook_length": 0, "lap_length": 0,
               "diameter_mm": 16, "detail_ref": "SYNTHETIC-REBAR-DETAIL"}),
])
def test_building_nonzero_input_must_not_silently_underflow(route, params):
    with pytest.raises(ValueError, match="underflow"):
        calculate_building_item(route, **params)


@pytest.mark.parametrize("route,params", [
    ("excavation", {"length": "1e-400", "width": 2, "depth": 3}),
    ("facade", {"length": 2, "height": 3, "openings": "1e-400"}),
    ("steel", {"length": 3, "unit_weight": "1e-400"}),
])
def test_advanced_nonzero_input_must_not_silently_underflow(route, params):
    with pytest.raises(ValueError, match="underflow"):
        calculate_advanced_item(route, **params)


@pytest.mark.parametrize("route,params", [
    ("excavation", {"length": "1e-200", "width": "1e-200", "depth": 1}),
    ("facade", {"length": "1e-200", "height": "1e-200", "openings": 0}),
    ("steel", {"length": "1e-200", "unit_weight": "1e-200"}),
])
def test_advanced_nonzero_product_must_not_silently_underflow(route, params):
    with pytest.raises(ValueError, match="underflow"):
        calculate_advanced_item(route, **params)


@pytest.mark.parametrize("route,params", [
    ("column", {"width": "1e308", "depth": 2, "height": 3}),
    ("wall", {"length": "1e308", "height": 2}),
    ("rebar", {"length": "1e308", "unit_weight": 3}),
])
def test_building_direct_module_does_not_return_infinity(route, params):
    with pytest.raises(ValueError, match="finite"):
        calculate_building_item(route, **params)


@pytest.mark.parametrize("route,params", [
    ("excavation", {"length": "1e308", "width": 2, "depth": 3}),
    ("steel_roof_deck_weight", {"length": "1e308", "width": 2,
                                "sheet_weight": 3}),
    ("facade", {"length": "1e308", "height": 2, "openings": 0}),
])
def test_advanced_direct_module_does_not_return_infinity(route, params):
    with pytest.raises(ValueError, match="finite"):
        calculate_advanced_item(route, **params)


@pytest.mark.parametrize("route,params", [
    ("door", {"count": "9007199254740993"}),
    ("door", {"count": "1.5"}),
    ("roof_insulation", {"length": 3, "width": 2,
                         "layers": "9007199254740993"}),
])
def test_building_nonexact_counts_are_not_rounded(route, params):
    with pytest.raises(ValueError, match="integer"):
        calculate_building_item(route, **params)


@pytest.mark.parametrize("route,params", [
    ("steel", {"length": 2, "unit_weight": 4,
               "count": "9007199254740993"}),
    ("kromit_roof", {"joist_length": 2, "joist_unit_weight": 3,
                     "joist_count": "9007199254740993"}),
    ("steel", {"length": 2, "unit_weight": 4, "count": "1.5"}),
])
def test_advanced_nonexact_counts_are_not_rounded(route, params):
    with pytest.raises(ValueError, match="integer"):
        calculate_advanced_item(route, **params)


@pytest.mark.parametrize("name", ["count", "void_count", "joist_count",
                                  "layers", "rib_count_x", "rib_count_y",
                                  "intersection_count"])
def test_building_integer_geometry_count_exact(name):
    with pytest.raises(ValueError, match="integer"):
        building._n("9007199254740993", name)


@pytest.mark.parametrize("route,params,quantity,unit", [
    ("wall", {"length": 2, "height": 3, "openings": 1, "count": 2}, 10, "m2"),
    ("beam", {"width": .3, "depth": .4, "length": 3, "count": 2}, .72, "m3"),
    ("rebar", {"length": 2, "unit_weight": .617, "count": 3}, 3.702, "kg"),
    ("wall", {"length": 2, "height": 3, "openings": 6}, 0, "m2"),
    ("tile", {"length": 2, "height": 3, "waste": 0}, 0, "m2"),
    ("door", {"count": "2.0"}, 2, "عدد"),
])
def test_building_existing_quantities_stay_unchanged(route, params, quantity, unit):
    result = calculate_building_item(route, **params)
    assert result.quantity == pytest.approx(quantity)
    assert result.unit == unit


@pytest.mark.parametrize("route,params,quantity,unit", [
    ("excavation", {"length": 3, "width": 2, "depth": 1.5}, 9, "m3"),
    ("footing_formwork", {"perimeter": 4, "height": 2, "count": 3}, 24, "m2"),
    ("facade", {"length": 3, "height": 2, "openings": 6}, 0, "m2"),
    ("steel", {"length": 2, "unit_weight": 0}, 0, "kg"),
    ("steel_roof_deck_weight", {"length": 2, "width": 3,
                                "sheet_weight": 4}, 24, "kg"),
    ("ceiling", {"length": 2, "width": 3, "count": 2}, 12, "m2"),
])
def test_advanced_existing_quantities_stay_unchanged(route, params, quantity, unit):
    result = calculate_advanced_item(route, **params)
    assert result.quantity == pytest.approx(quantity)
    assert result.unit == unit


def test_legitimate_zero_is_not_nonzero_underflow():
    assert advanced._n("0e-500", "openings") == 0
    assert building._n("0e-500", "openings") == 0
