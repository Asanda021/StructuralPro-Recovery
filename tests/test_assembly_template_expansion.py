import pytest

from core.takeoff.assembly_templates import AssemblyTemplateLibrary
from core.takeoff.assembly import calculate_assembly


def test_column_assembly_is_deterministic_and_has_no_implicit_waste():
    result = calculate_assembly("concrete_column", count=4, width=0.4, depth=0.4, height=3)
    assert result.complete
    assert result.components[0].quantity == pytest.approx(1.92)
    assert result.components[0].unit == "m³"
    assert "waste_factor" not in result.inputs_used


def test_beam_assembly_only_adds_explicit_formwork_and_rebar_specification():
    result = calculate_assembly("concrete_beam", count=2, length=5, width=0.3, depth=0.5,
                                formwork_sides=2, rebar_kg_per_m3=120)
    by_code = {item.code: item for item in result.components}
    assert by_code["concrete"].quantity == pytest.approx(1.5)
    assert by_code["formwork"].quantity == pytest.approx(13)
    assert by_code["reinforcement"].quantity == pytest.approx(180)
    assert "صریحاً" in by_code["formwork"].warning


def test_slab_assembly_subtracts_openings_before_volume():
    result = calculate_assembly("concrete_slab", count=2, length=5, width=4,
                                thickness=0.15, openings=1)
    by_code = {item.code: item for item in result.components}
    assert by_code["net_area"].quantity == pytest.approx(39)
    assert by_code["concrete"].quantity == pytest.approx(5.85)


def test_rebar_waste_is_only_applied_when_explicitly_supplied():
    base = calculate_assembly("rebar", count=10, length=12, unit_weight=0.888)
    wasted = calculate_assembly("rebar", count=10, length=12, unit_weight=0.888, waste_factor=0.05)
    assert base.components[0].quantity == pytest.approx(106.56)
    assert wasted.components[0].quantity == pytest.approx(111.888)


def test_floor_finish_uses_explicit_geometry_and_consumption():
    result = calculate_assembly("floor_finish", count=2, length=5, width=4, openings=1,
                                consumption_per_m2=3, consumption_unit="kg")
    by_code = {item.code: item for item in result.components}
    assert by_code["finish_area"].quantity == pytest.approx(39)
    assert by_code["finish_material"].quantity == pytest.approx(117)
    assert by_code["finish_material"].unit == "kg"


@pytest.mark.parametrize("kwargs", [
    {"count": 1, "width": 0, "depth": 0.4, "height": 3},
    {"count": 1, "width": 0.4, "depth": 0.4, "height": float("inf")},
])
def test_invalid_column_geometry_fails_closed(kwargs):
    with pytest.raises(ValueError):
        calculate_assembly("concrete_column", **kwargs)


def test_openings_cannot_exceed_gross_slab_or_wall_area():
    with pytest.raises(ValueError, match="بازشوها"):
        calculate_assembly("concrete_slab", count=1, length=2, width=2, thickness=0.1, openings=5)
    with pytest.raises(ValueError, match="بازشوها"):
        calculate_assembly("block_wall", length=2, height=2, thickness=0.2, openings=5)


def test_assembly_template_library_requires_explicit_count_and_openings():
    library = AssemblyTemplateLibrary()
    incomplete = library.expand("concrete_slab", {"length": 5, "width": 4, "thickness": 0.15})
    assert not incomplete.complete
    assert incomplete.missing_inputs == ("count", "openings")
    complete = library.expand("concrete_slab", {
        "count": 1, "length": 5, "width": 4, "thickness": 0.15, "openings": 0
    })
    assert complete.complete
    assert next(x for x in complete.components if x.code == "concrete").quantity == pytest.approx(3)


def test_template_library_search_and_duplicate_guard():
    library = AssemblyTemplateLibrary()
    assert library.get("concrete_column").title_fa == "ستون بتنی"
    assert len(library.list()) == len({x.code for x in library.list()})


def test_assembly_engine_requires_explicit_counts_and_openings():
    with pytest.raises(ValueError, match="count"):
        calculate_assembly("concrete_slab", length=5, width=4, thickness=0.15, openings=0)
    with pytest.raises(ValueError, match="openings"):
        calculate_assembly("concrete_slab", count=1, length=5, width=4, thickness=0.15)
    with pytest.raises(ValueError, match="count"):
        calculate_assembly("excavation", length=5, width=4, depth=2, count=1.5)


def test_assembly_engine_rejects_fractional_counts():
    with pytest.raises(ValueError, match="integer"):
        calculate_assembly("concrete_column", count=1.5, width=0.4, depth=0.4, height=3)


def test_assembly_rejects_non_finite_outputs_and_inconsistent_block_thickness():
    with pytest.raises(ValueError, match="متناهی"):
        calculate_assembly("concrete_column", count=1, width=1e308, depth=1e308, height=1e308)
    with pytest.raises(ValueError, match="ضخامت بلوک"):
        calculate_assembly(
            "block_wall", length=2, height=2, thickness=0.2, openings=0,
            block_length=0.4, block_height=0.2, block_thickness=0.3,
            joint_thickness=0.01, cement_parts=1, sand_parts=4,
        )
