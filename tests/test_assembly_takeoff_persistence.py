import pytest

from core.platform.application import StructuralProApp


def test_confirmed_assembly_components_persist_to_takeoffs_and_boq(tmp_path):
    app = StructuralProApp(tmp_path)
    app.create_project("پروژه قالب ترکیبی", "assembly-p1")
    result = app.add_assembly_takeoff(
        "assembly-p1", "concrete_beam",
        {"count": 2, "length": 5, "width": 0.3, "depth": 0.5,
         "formwork_sides": 2, "rebar_kg_per_m3": 120},
        floor_id="طبقه ۱", description="تیر بتنی محور A",
    )
    assert len(result["rows"]) == 3
    assert len(result["assembly"]["component_source_ids"]) == 3
    project = app.open_project("assembly-p1")
    assert len(project["takeoff_assemblies"]) == 1
    assert len(project["takeoffs"]) == 3
    assert len(project["boq"]) == 3
    assert all(row["assembly_id"] == result["assembly"]["id"] for row in project["takeoffs"])
    by_code = {row["quantities"][0]["code"]: row["quantities"][0] for row in project["takeoffs"]}
    assert by_code["concrete"]["amount"] == pytest.approx(1.5)
    assert by_code["formwork"]["amount"] == pytest.approx(13)
    assert by_code["reinforcement"]["amount"] == pytest.approx(180)


def test_incomplete_or_unknown_assembly_inputs_are_not_persisted(tmp_path):
    app = StructuralProApp(tmp_path)
    app.create_project("پروژه قالب ناقص", "assembly-p2")
    with pytest.raises(ValueError, match="ورودی‌های قالب"):
        app.add_assembly_takeoff(
            "assembly-p2", "concrete_slab",
            {"count": 1, "length": 5, "width": 4, "thickness": 0.15},
            floor_id="طبقه همکف",
        )
    with pytest.raises(ValueError, match="ناشناخته"):
        app.add_assembly_takeoff(
            "assembly-p2", "concrete_column",
            {"count": 1, "width": 0.4, "depth": 0.4, "height": 3, "mystery": 1},
            floor_id="طبقه همکف",
        )
    project = app.open_project("assembly-p2")
    assert project["takeoffs"] == []
    assert project["boq"] == []
    assert project.get("takeoff_assemblies", []) == []


def test_assembly_save_requires_explicit_project_and_floor(tmp_path):
    app = StructuralProApp(tmp_path)
    app.create_project("پروژه طبقه", "assembly-p3")
    inputs = {"count": 1, "width": 0.4, "depth": 0.4, "height": 3}
    with pytest.raises(ValueError, match="طبقه"):
        app.add_assembly_takeoff("assembly-p3", "concrete_column", inputs, floor_id="")
    assert app.open_project("assembly-p3")["takeoffs"] == []
