import pytest

from core.takeoff.assembly_templates import AssemblyTemplateLibrary
from core.platform.application import StructuralProApp


def test_finish_catalog_keeps_each_operation_as_a_separate_item():
    library = AssemblyTemplateLibrary()
    expected = {
        "gypsum_scratch", "gypsum_finish", "cement_render", "wall_tile",
        "wall_paint", "waterproofing_wall", "facade_finish", "floor_tile",
        "floor_screed", "ceiling_paint", "false_ceiling",
        "waterproofing_floor", "skirting",
    }
    assert expected <= {template.code for template in library.list()}


@pytest.mark.parametrize(
    ("code", "inputs", "expected"),
    [
        ("gypsum_scratch", {"count": 1, "length": 10, "height": 3, "openings": 2}, 28),
        ("gypsum_finish", {"count": 1, "length": 10, "height": 3, "openings": 2}, 28),
        ("cement_render", {"count": 1, "length": 10, "height": 3, "openings": 2}, 28),
        ("wall_tile", {"count": 1, "length": 10, "height": 3, "openings": 2}, 28),
        ("wall_paint", {"count": 1, "length": 10, "height": 3, "openings": 2}, 28),
        ("waterproofing_wall", {"count": 1, "length": 10, "height": 3, "openings": 2}, 28),
        ("facade_finish", {"count": 1, "length": 10, "height": 3, "openings": 2}, 28),
        ("floor_tile", {"count": 1, "length": 6, "width": 4, "openings": 2}, 22),
        ("floor_screed", {"count": 1, "length": 6, "width": 4, "openings": 2}, 22),
        ("ceiling_paint", {"count": 1, "length": 6, "width": 4, "openings": 2}, 22),
        ("false_ceiling", {"count": 1, "length": 6, "width": 4, "openings": 2}, 22),
        ("waterproofing_floor", {"count": 1, "length": 6, "width": 4, "openings": 2}, 22),
        ("skirting", {"count": 1, "length": 40, "deductions": 8}, 32),
    ],
)
def test_finish_operation_calculates_net_quantity_with_explicit_deductions(code, inputs, expected):
    result = AssemblyTemplateLibrary().expand(code, inputs)
    assert result.complete
    assert len(result.components) == 1
    assert result.components[0].quantity == pytest.approx(expected)
    assert result.components[0].unit == ("m" if code == "skirting" else "m²")
    assert "بازشو" in result.components[0].formula or "کسرشده" in result.components[0].formula or "کسر" in result.components[0].formula


def test_finish_material_quantity_requires_explicit_rate_unit_and_spec_reference():
    library = AssemblyTemplateLibrary()
    base = {"count": 1, "length": 10, "height": 3, "openings": 2}
    with pytest.raises(ValueError, match="واحد مصرف"):
        library.expand("wall_tile", {**base, "consumption_per_m2_per_layer": 4})
    with pytest.raises(ValueError, match="مرجع مشخصات"):
        library.expand("wall_tile", {**base, "layers": 2, "consumption_per_m2_per_layer": 4, "consumption_unit": "kg"})
    with pytest.raises(ValueError, match="تعداد لایه"):
        library.expand("wall_tile", {
            **base, "consumption_per_m2_per_layer": 4, "consumption_unit": "kg",
            "material_spec_ref": "آزمون مصنوعی: دیتاشیت T-01",
        })
    result = library.expand("wall_tile", {
        **base, "layers": 2, "consumption_per_m2_per_layer": 4,
        "consumption_unit": "kg", "material_spec_ref": "آزمون مصنوعی: دیتاشیت T-01",
        "waste_factor": 0.1,
    })
    assert [component.code for component in result.components] == [
        "wall_tile_work", "wall_tile_procurement", "wall_tile_material",
    ]
    assert [component.quantity for component in result.components] == pytest.approx([28, 30.8, 224])
    assert result.components[2].source == "آزمون مصنوعی: دیتاشیت T-01"
    assert "لایه" in result.components[2].formula


def test_finish_surface_is_not_guessed_when_required_geometry_is_missing():
    result = AssemblyTemplateLibrary().expand(
        "wall_paint", {"count": 1, "length": 10, "height": 3}
    )
    assert not result.complete
    assert result.missing_inputs == ("openings",)
    assert result.components == ()


def test_invalid_finish_dimensions_and_layers_fail_closed():
    library = AssemblyTemplateLibrary()
    with pytest.raises(ValueError):
        library.expand("floor_tile", {"count": 1, "length": 6, "width": 4, "openings": 25})
    with pytest.raises(ValueError, match="عدد صحیح مثبت"):
        library.expand("wall_paint", {
            "count": 1, "length": 10, "height": 3, "openings": 0, "layers": 1.5,
        })


def test_finish_assembly_persists_distinct_work_and_material_rows_to_boq(tmp_path):
    app = StructuralProApp(tmp_path)
    app.create_project("پروژه آزمون مصنوعی نازک‌کاری", "finish-project")
    result = app.add_assembly_takeoff(
        "finish-project", "wall_tile",
        {
            "count": 1, "length": 10, "height": 3, "openings": 2,
            "layers": 2, "consumption_per_m2_per_layer": 4, "consumption_unit": "kg",
            "material_spec_ref": "نمونه آزمون مصنوعی: SPEC-T01", "waste_factor": 0.1,
        },
        floor_id="طبقه ۱ / فضای آزمون", location_id="سرویس ۱۰۱",
        description="کاشی دیوار سرویس — داده آزمون مصنوعی",
    )
    project = app.open_project("finish-project")
    assert len(result["rows"]) == 3
    assert len(project["takeoffs"]) == 3
    assert len(project["boq"]) == 1
    assert {row["system"] for row in project["takeoffs"]} == {"طبقه ۱ / فضای آزمون"}
    assert {row["quantities"][0]["code"] for row in project["takeoffs"]} == {
        "wall_tile_work", "wall_tile_procurement", "wall_tile_material",
    }
    by_component = {row["quantities"][0]["code"]: row["quantities"][0]["amount"]
                    for row in project["takeoffs"]}
    assert by_component == pytest.approx({
        "wall_tile_work": 28.0, "wall_tile_procurement": 30.8,
        "wall_tile_material": 224.0,
    })


def test_five_floor_synthetic_finish_takeoff_keeps_floor_and_item_provenance(tmp_path):
    app = StructuralProApp(tmp_path)
    app.create_project("ساختمان پنج‌طبقه — نمونه آزمون مصنوعی", "five-floor-finish")
    library = AssemblyTemplateLibrary()
    wall_inputs = {"count": 1, "length": 10, "height": 3, "openings": 2}
    floor_inputs = {"count": 1, "length": 6, "width": 4, "openings": 2}
    linear_inputs = {"count": 1, "length": 40, "deductions": 8}
    item_inputs = {
        "gypsum_scratch": wall_inputs,
        "gypsum_finish": wall_inputs,
        "cement_render": wall_inputs,
        "wall_tile": wall_inputs,
        "wall_paint": wall_inputs,
        "waterproofing_wall": wall_inputs,
        "facade_finish": wall_inputs,
        "floor_tile": floor_inputs,
        "floor_screed": floor_inputs,
        "ceiling_paint": floor_inputs,
        "false_ceiling": floor_inputs,
        "waterproofing_floor": floor_inputs,
        "skirting": linear_inputs,
    }
    for floor_number in range(1, 6):
        for code, inputs in item_inputs.items():
            app.add_assembly_takeoff(
                "five-floor-finish", code, inputs,
                floor_id=f"طبقه {floor_number} / فضای آزمون مصنوعی",
                location_id="اتاق آزمون ثابت",
                description=f"{code} — داده آزمون مصنوعی",
            )

    project = app.open_project("five-floor-finish")
    assert len(project["takeoff_assemblies"]) == 65
    assert len(project["takeoffs"]) == 65
    assert project["boq"]
    by_floor = {}
    by_item = {}
    for row in project["takeoffs"]:
        by_floor.setdefault(row["system"], 0)
        by_floor[row["system"]] += row["quantities"][0]["amount"]
        item = row["params"]["assembly_code"]
        by_item.setdefault(item, 0)
        by_item[item] += row["quantities"][0]["amount"]
    assert len(by_floor) == 5
    assert set(by_item) == set(item_inputs)
    assert by_item["wall_tile"] == pytest.approx(140)
    assert by_item["floor_tile"] == pytest.approx(110)
    assert by_item["skirting"] == pytest.approx(160)


@pytest.mark.parametrize("field", [
    "count", "length", "openings", "layers", "waste_factor",
    "consumption_per_m2_per_layer",
])
def test_boolean_values_are_rejected_for_finish_measurement_inputs(field):
    inputs = {"count": 1, "length": 10, "height": 3, "openings": 0}
    if field in {"count", "length", "openings"}:
        inputs[field] = True
    else:
        inputs.update({"layers": 1, "waste_factor": 0.05,
                       "consumption_per_m2_per_layer": 2,
                       "consumption_unit": "kg", "material_spec_ref": "SPEC-TEST"})
        inputs[field] = True
    with pytest.raises(ValueError):
        AssemblyTemplateLibrary().expand("wall_tile", inputs)
