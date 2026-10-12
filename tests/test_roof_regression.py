import pytest

from core.takeoff.modules.advanced import calculate_advanced_item
from core.takeoff.modules.building import calculate_building_item


def test_all_concrete_roof_families_are_deterministic():
    cases = [
        (
            "solid_slab_roof",
            dict(length=10, width=12, thickness=0.20, count=1),
            24.0,
            "m3",
        ),
        (
            "joist_block_roof",
            dict(
                length=10, width=10, topping_thickness=0.05,
                joist_spacing=0.50, joist_width=0.10, joist_depth=0.20, count=1,
            ),
            9.2,
            "m3",
        ),
        (
            "hollow_core_roof",
            dict(
                length=10, width=5, thickness=0.20,
                void_diameter=0.10, void_count=20, count=1,
            ),
            8.429203673,
            "m3",
        ),
        (
            "waffle_roof",
            dict(
                length=10, width=10, top_thickness=0.06,
                spacing_x=0.60, spacing_y=0.60,
                rib_width=0.12, rib_depth=0.18, count=1,
            ),
            12.48,
            "m3",
        ),
        (
            "uboot_roof",
            dict(
                length=10, width=10, thickness=0.28,
                void_length=0.50, void_width=0.25, void_height=0.20,
                void_count=100, count=1,
            ),
            25.5,
            "m3",
        ),
        (
            "cobiax_roof",
            dict(
                length=10, width=10, thickness=0.28,
                void_length=0.50, void_width=0.25, void_height=0.20,
                void_count=100, count=1,
            ),
            25.5,
            "m3",
        ),
    ]
    for item, params, expected, unit in cases:
        result = calculate_building_item(item, **params)
        assert result.unit == unit
        assert result.quantity == pytest.approx(expected, rel=1e-9, abs=1e-9)


@pytest.mark.parametrize(
    ("item", "params", "field"),
    [
        ("solid_slab_roof", dict(length=10, width=12, thickness=0), "thickness"),
        ("joist_block_roof", dict(
            length=10, width=10, topping_thickness=0.05,
            joist_spacing=0, joist_width=0.1, joist_depth=0.2,
        ), "joist_spacing"),
        ("waffle_roof", dict(
            length=10, width=10, top_thickness=0.06,
            spacing_x=0.6, spacing_y=0,
            rib_width=0.12, rib_depth=0.18,
        ), "spacing_y"),
        ("uboot_roof", dict(
            length=10, width=10, thickness=0.28,
            void_length=0.5, void_width=0.25, void_height=0.2,
            void_count=-1,
        ), "void_count"),
    ],
)
def test_roof_calculations_fail_closed_on_invalid_geometry(item, params, field):
    with pytest.raises(ValueError, match=field):
        calculate_building_item(item, **params)


def test_uboot_void_volume_larger_than_gross_slab_is_rejected():
    with pytest.raises(ValueError, match="void volume cannot exceed gross slab volume"):
        calculate_building_item(
            "uboot_roof",
            length=1,
            width=1,
            thickness=0.10,
            void_length=1,
            void_width=1,
            void_height=1,
            void_count=100,
        )


def test_steel_roof_families_use_explicit_inputs():
    cases = [
        ("steel_roof_deck_area", dict(length=10, width=12), 120.0, "m2"),
        ("steel_roof_deck_weight", dict(length=10, width=12, sheet_weight=10), 1200.0, "kg"),
        ("steel_roof_composite_deck", dict(length=10, width=12, sheet_weight=10), 1200.0, "kg"),
        ("kromit_roof", dict(joist_length=6, joist_unit_weight=12, joist_count=20), 1440.0, "kg"),
        ("steel_truss_roof", dict(steel_length=100, unit_weight=12), 1200.0, "kg"),
        ("steel_sandwich_roof", dict(length=10, width=12), 120.0, "m2"),
    ]
    for item, params, expected, unit in cases:
        result = calculate_advanced_item(item, **params)
        assert result.unit == unit
        assert result.quantity == pytest.approx(expected)


@pytest.mark.parametrize(
    ("item", "params", "field"),
    [
        ("steel_roof_deck_area", dict(length=10, width=0), "width"),
        ("steel_roof_deck_weight", dict(length=10, width=12, sheet_weight=0), "sheet_weight"),
        ("kromit_roof", dict(joist_length=6, joist_unit_weight=12, joist_count=0), "joist_count"),
        ("steel_truss_roof", dict(steel_length=100, unit_weight=0), "unit_weight"),
    ],
)
def test_steel_roof_calculations_fail_closed_on_invalid_geometry(item, params, field):
    with pytest.raises(ValueError, match=field):
        calculate_advanced_item(item, **params)
