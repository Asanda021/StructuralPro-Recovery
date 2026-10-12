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
        joist_width=.10, joist_depth=.20,
        foam_length=.50, foam_width=.25, foam_height=.20,
        mesh_unit_weight=2.5,
    )
    assert r.complete
    assert [c.code for c in r.components] == [
        "concrete", "joist", "foam", "reinforcement_mesh"
    ]
    assert round(r.components[0].quantity, 6) == 11.0
    assert r.components[1].quantity == 25
    assert r.components[2].quantity == 960
    assert r.components[3].quantity == 300


def test_joist_foam_does_not_invent_reinforcement_specification():
    r = calculate_assembly(
        "joist_foam_roof_assembly",
        length=10, width=12, count=1,
        topping_thickness=.05, joist_spacing=.5,
        joist_width=.10, joist_depth=.20,
        foam_length=.50, foam_width=.25, foam_height=.20,
    )
    assert r.complete
    assert r.missing_inputs == ()
    assert not any(c.code == "reinforcement_mesh" for c in r.components)


def test_assembly_keeps_components_independently_auditable():
    r = calculate_assembly(
        "joist_foam_roof_assembly",
        length=10, width=12, count=1,
        topping_thickness=.05, joist_spacing=.5,
        joist_width=.10, joist_depth=.20,
        foam_length=.50, foam_width=.25, foam_height=.20,
        mesh_unit_weight=2.5,
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
        foam_length=.50, foam_width=.25, foam_height=.20,
    )
    assert r.complete
    assert r.components[1].quantity == 24
    assert round(r.components[0].quantity, 6) == 10.8
