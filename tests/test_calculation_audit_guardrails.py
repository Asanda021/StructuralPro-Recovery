import math

import pytest

from core.takeoff.modules.advanced import calculate_advanced_item
from core.takeoff.modules.building import calculate_building_item
from core.takeoff.modules.civil import calculate_civil_item
from core.takeoff.modules.electrical import calculate_electrical_item
from core.takeoff.modules.mechanical import calculate_mechanical_item
from core.takeoff.assembly import calculate_assembly


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_building_calculators_reject_non_finite_dimensions(bad):
    with pytest.raises(ValueError, match="finite"):
        calculate_building_item("column", width=bad, depth=0.3, height=3, count=1)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_advanced_calculators_reject_non_finite_dimensions(bad):
    with pytest.raises(ValueError, match="finite"):
        calculate_advanced_item("footing_concrete", length=bad, width=2, thickness=0.5)


@pytest.mark.parametrize("calculator, kwargs", [
    (calculate_civil_item, {"item": "excavation", "length": float("nan"), "width": 2, "depth": 1}),
    (calculate_mechanical_item, {"item": "pipe", "length": float("inf")}),
    (calculate_electrical_item, {"item": "cable", "length": float("-inf")}),
])
def test_discipline_calculators_reject_non_finite_inputs(calculator, kwargs):
    item = kwargs.pop("item")
    with pytest.raises(ValueError, match="finite"):
        calculator(item, **kwargs)


def test_assembly_rejects_non_finite_inputs():
    with pytest.raises(ValueError, match="finite"):
        calculate_assembly("joist_foam_roof_assembly", length=float("nan"), width=10)


def test_wall_openings_larger_than_gross_area_are_rejected_not_clamped():
    with pytest.raises(ValueError, match="openings cannot exceed gross wall area"):
        calculate_building_item("wall", length=4, height=3, openings=13)


def test_facade_openings_larger_than_gross_area_are_rejected_not_clamped():
    with pytest.raises(ValueError, match="openings cannot exceed gross facade area"):
        calculate_advanced_item("facade", length=4, height=3, openings=13)


def test_backfill_deductions_larger_than_excavation_are_rejected_not_clamped():
    with pytest.raises(ValueError, match="deductions cannot exceed excavation"):
        calculate_civil_item("backfill", excavation=10, deductions=11)


def test_hollow_core_void_volume_larger_than_slab_is_rejected():
    with pytest.raises(ValueError, match="void volume cannot exceed gross slab"):
        calculate_building_item(
            "hollow_core_roof", length=10, width=10, thickness=0.2,
            void_diameter=1, void_count=100,
        )


def test_uboot_void_volume_larger_than_slab_is_rejected():
    with pytest.raises(ValueError, match="void volume cannot exceed gross slab"):
        calculate_building_item(
            "uboot_roof", length=10, width=10, thickness=0.2,
            void_length=0.5, void_width=0.5, void_height=0.3, void_count=1000,
        )


def test_valid_wall_opening_subtraction_remains_deterministic():
    result = calculate_building_item("wall", length=4, height=3, openings=2)
    assert result.quantity == pytest.approx(10.0)


def test_valid_backfill_deduction_remains_deterministic():
    result = calculate_civil_item("backfill", excavation=10, deductions=2)
    assert result.quantity == pytest.approx(8.0)


def test_wall_count_multiplies_net_area_for_each_identical_wall():
    result = calculate_building_item("wall", length=4, height=3, openings=2, count=3)
    assert result.quantity == pytest.approx(30)


@pytest.mark.parametrize("count", [True, 1.5])
def test_building_rejects_ambiguous_element_count(count):
    with pytest.raises(ValueError):
        calculate_building_item("column", width=.3, depth=.4, height=3, count=count)


def test_engine_rejects_overflowing_calculated_quantity():
    from core.takeoff.engine import TakeoffEngine
    with pytest.raises(ValueError, match="متناهی"):
        TakeoffEngine().calculate("building", "column", width=1e200, depth=1e200, height=3)


@pytest.mark.parametrize("calculator,item,params", [
    (calculate_advanced_item, "footing_concrete", {"length": True, "width": 2, "thickness": .5}),
    (calculate_civil_item, "excavation", {"length": True, "width": 2, "depth": 1}),
    (calculate_mechanical_item, "pipe", {"length": True}),
    (calculate_electrical_item, "cable", {"length": True}),
])
def test_all_existing_disciplines_reject_boolean_dimensions(calculator, item, params):
    with pytest.raises(ValueError, match="numeric"):
        calculator(item, **params)
