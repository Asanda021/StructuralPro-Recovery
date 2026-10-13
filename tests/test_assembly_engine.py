from core.takeoff.assembly import calculate_assembly


def test_block_wall_assembly_breaks_into_real_components_without_hidden_coefficients():
    r = calculate_assembly(
        "block_wall",
        length=10, height=3, thickness=.20, openings=0,
        block_length=.40, block_height=.20, block_thickness=.20,
        joint_thickness=.01, cement_parts=1, sand_parts=4,
        block_waste_factor=.05, mortar_waste_factor=.03,
    )
    assert r.complete
    assert [c.code for c in r.components] == [
        "wall_area", "block", "mortar", "cement", "sand"
    ]
    assert r.components[0].quantity == 30
    assert r.components[1].quantity == 366
    assert r.components[2].quantity > 0
    assert "پرت" in r.components[1].formula


def test_block_wall_requests_only_specification_that_is_actually_missing():
    r = calculate_assembly(
        "block_wall",
        length=10, height=3, thickness=.20, openings=0,
        block_length=.40, block_height=.20, block_thickness=.20,
        joint_thickness=.01, cement_parts=1,
    )
    assert not r.complete
    assert r.missing_inputs == ("sand_parts",)


def test_joist_foam_assembly_is_one_operation_with_independent_components():
    r = calculate_assembly(
        "joist_foam_roof_assembly",
        length=10, width=12, count=1,
        topping_thickness=.05, joist_spacing=.5,
        joist_width=.10, joist_depth=.20, joist_count=25,
        foam_length=.50, foam_width=.25, foam_height=.20, foam_count=960,
        mesh_unit_weight=2.5, mesh_unit_weight_source="approved-plan",
    )
    assert r.complete
    assert [c.code for c in r.components] == [
        "concrete", "joist", "foam", "reinforcement_mesh"
    ]
    assert round(r.components[0].quantity, 6) == 6.0
    assert r.components[1].quantity == 25
    assert r.components[2].quantity == 960
    assert r.components[3].quantity == 300


def test_joist_foam_does_not_invent_reinforcement_specification():
    r = calculate_assembly(
        "joist_foam_roof_assembly",
        length=10, width=12, count=1,
        topping_thickness=.05, joist_spacing=.5,
        joist_width=.10, joist_depth=.20, joist_count=25,
        foam_length=.50, foam_width=.25, foam_height=.20, foam_count=960,
    )
    assert r.complete
    assert r.missing_inputs == ()
    assert not any(c.code == "reinforcement_mesh" for c in r.components)


def test_assembly_keeps_components_independently_auditable():
    r = calculate_assembly(
        "joist_foam_roof_assembly",
        length=10, width=12, count=1,
        topping_thickness=.05, joist_spacing=.5,
        joist_width=.10, joist_depth=.20, joist_count=25,
        foam_length=.50, foam_width=.25, foam_height=.20, foam_count=960,
        mesh_unit_weight=2.5, mesh_unit_weight_source="approved-plan",
    )
    for c in r.components:
        assert c.code and c.title and c.unit and c.formula


def test_block_waste_does_not_change_built_mortar_volume():
    base = dict(length=10, height=3, thickness=.20, openings=0,
        block_length=.40, block_height=.20, block_thickness=.20,
        joint_thickness=.01, cement_parts=1, sand_parts=4,
        mortar_waste_factor=0)
    a = calculate_assembly("block_wall", **base, block_waste_factor=0)
    b = calculate_assembly("block_wall", **base, block_waste_factor=.10)
    assert a.components[2].quantity == b.components[2].quantity
    assert b.components[1].quantity >= a.components[1].quantity


def test_joist_count_can_be_explicitly_overridden_for_real_layout():
    r = calculate_assembly(
        "joist_foam_roof_assembly",
        length=10, width=12, count=1,
        topping_thickness=.05, joist_spacing=.5,
        joist_width=.10, joist_depth=.20, joist_count=24,
        foam_length=.50, foam_width=.25, foam_height=.20, foam_count=960,
    )
    assert r.complete
    assert r.components[1].quantity == 24
    assert round(r.components[0].quantity, 6) == 6.0



def test_infill_cannot_be_billed_from_theoretical_ceil_layout():
    import pytest
    with pytest.raises(ValueError, match="joist_count"):
        calculate_assembly("joist_foam_roof_assembly",
                           length=10, width=12, count=1,
                           topping_thickness=.05, joist_spacing=.5,
                           joist_width=.1, joist_depth=.2,
                           foam_length=.5, foam_width=.25, foam_height=.2,
                           foam_count=960)


def test_roof_concrete_never_includes_precast_joist_volume_without_in_situ_details():
    r = calculate_assembly("joist_block_roof_assembly",
                           length=10, width=12, count=1,
                           topping_thickness=.05, joist_spacing=.5,
                           joist_width=.1, joist_depth=.2, joist_count=24,
                           block_length=.5, block_width=.25, block_height=.2,
                           block_count=960)
    assert [x.code for x in r.components] == ["concrete", "joist", "block"]
    assert r.components[0].quantity == 6.0
    assert r.components[1].quantity == 24
    assert r.components[2].quantity == 960


def test_cast_in_place_ribs_require_all_three_real_inputs():
    import pytest
    params=dict(length=10,width=12,count=1,topping_thickness=.05,
                joist_spacing=.5,joist_width=.1,joist_depth=.2,
                joist_count=24,foam_length=.5,foam_width=.25,
                foam_height=.2,foam_count=900)
    with pytest.raises(ValueError, match="هر سه"):
        calculate_assembly("joist_foam_roof_assembly", **params,cast_rib_count=3)
    r=calculate_assembly("joist_foam_roof_assembly", **params,
                         cast_rib_count=3,cast_rib_length_m=10,cast_rib_area_m2=.02)
    assert next(x for x in r.components if x.code=="cast_rib_concrete").quantity==.6


def test_mesh_requires_approved_unit_weight_reference():
    import pytest
    params=dict(length=10,width=12,count=1,topping_thickness=.05,
                joist_spacing=.5,joist_width=.1,joist_depth=.2,
                joist_count=24,foam_length=.5,foam_width=.25,
                foam_height=.2,foam_count=900)
    with pytest.raises(ValueError, match="مرجع"):
        calculate_assembly("joist_foam_roof_assembly", **params,
                           mesh_unit_weight=2.5)
