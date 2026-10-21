"""PR #481 recovery acceptance: payable vs material and stable location identity."""

import pytest

from core.platform.application import StructuralProApp


FINISH = {"count": 1, "length": 10, "height": 3, "openings": 2,
          "layers": 2, "consumption_per_m2_per_layer": 4,
          "consumption_unit": "kg", "material_spec_ref": "SPEC-LOCAL-001",
          "waste_factor": 0.1}


def _create(tmp_path):
    app = StructuralProApp(tmp_path)
    app.create_project("ساختمان آزمایشی", "p1")
    return app


def test_missing_location_rejected_with_zero_side_effects(tmp_path):
    app = _create(tmp_path)
    with pytest.raises(ValueError, match="شناسه ثابت محل"):
        app.add_assembly_takeoff("p1", "wall_tile", FINISH, floor_id="اول", approved_by="بازبین مستقل آزمون")
    assert app.open_project("p1")["takeoffs"] == []


def test_same_operation_floor_location_is_not_registered_twice(tmp_path):
    app = _create(tmp_path)
    app.add_assembly_takeoff("p1", "wall_tile", FINISH, floor_id="اول", location_id="حمام", approved_by="بازبین مستقل آزمون")
    with pytest.raises(ValueError, match="تکراری"):
        app.add_assembly_takeoff("p1", "wall_tile", FINISH, floor_id="اول", location_id="حمام", approved_by="بازبین مستقل آزمون")
    project = app.open_project("p1")
    assert len(project["takeoff_assemblies"]) == 1
    assert len(project["takeoffs"]) == 3
    assert len(project["boq"]) == 1


def test_different_floor_location_and_operation_allow_real_distinct_work(tmp_path):
    app = _create(tmp_path)
    for code, floor, location in [
        ("wall_tile", "اول", "حمام"),
        ("wall_tile", "دوم", "حمام"),
        ("wall_tile", "اول", "آشپزخانه"),
        ("wall_paint", "اول", "حمام"),
    ]:
        app.add_assembly_takeoff("p1", code, FINISH, floor_id=floor, location_id=location, approved_by="بازبین مستقل آزمون")
    project = app.open_project("p1")
    assert len(project["takeoffs"]) == 12
    # BOQ keeps distinct floors, aggregates same-floor locations, and traces every source.
    assert len(project["boq"]) == 3
    by_group = {(r["group"], r["item_code"]): r for r in project["boq"]}
    assert {k: r["quantity"] for k, r in by_group.items()} == pytest.approx({
        ("اول", "wall_tile_work"): 56,
        ("دوم", "wall_tile_work"): 28,
        ("اول", "wall_paint_work"): 28,
    })
    payable_ids = {t["source_id"] for t in project["takeoffs"] if t["component_role"] == "work"}
    grouped_ids = [sid for r in project["boq"] for sid in r["source_ids"]]
    assert len(grouped_ids) == len(payable_ids) == 4
    assert set(grouped_ids) == payable_ids
    assert {r["component_role"] for r in project["takeoffs"]} == {"work", "procurement", "material"}


def test_five_floors_round_trip_and_other_work_rebuilds_without_double_count(tmp_path):
    app = _create(tmp_path)
    for floor in range(1, 6):
        app.add_assembly_takeoff("p1", "wall_tile", FINISH, floor_id=f"طبقه {floor}", location_id="حمام", approved_by="بازبین مستقل آزمون")
    app.store.close()
    reopened = StructuralProApp(tmp_path)
    before = reopened.open_project("p1")
    assert len(before["takeoffs"]) == 15
    assert len(before["boq"]) == 5
    assert {r["group"] for r in before["boq"]} == {f"طبقه {i}" for i in range(1, 6)}
    assert sum(r["quantity"] for r in before["boq"]) == pytest.approx(140)
    assert len({sid for r in before["boq"] for sid in r["source_ids"]}) == 5
    assert len([x for x in before["takeoffs"] if x["component_role"] == "material"]) == 5
    # Adding ordinary work rebuilds the entire BOQ; supply/material rows stay outside it.
    reopened.add_takeoff("p1", "building", "slab_volume", length=2, width=2, thickness=1,
                         count=1, source_id="synthetic:pr481:slab:after-reopen")
    after = reopened.open_project("p1")
    assert len(after["boq"]) == 6
    assert {r["item_code"] for r in after["boq"]} == {"wall_tile_work", "slab_volume"}
    assert {r["group"] for r in after["boq"] if r["item_code"] == "wall_tile_work"} == {f"طبقه {i}" for i in range(1, 6)}
    assert sum(r["quantity"] for r in after["boq"] if r["item_code"] == "wall_tile_work") == pytest.approx(140)
    assert len({sid for r in after["boq"] for sid in r["source_ids"]}) == 6
    reopened.store.close()


def test_legacy_finish_rows_without_explicit_role_not_double_counted(tmp_path):
    app = _create(tmp_path)
    app.add_assembly_takeoff("p1", "wall_tile", FINISH, floor_id="اول", location_id="حمام", approved_by="بازبین مستقل آزمون")
    project = app.open_project("p1")
    for row in project["takeoffs"]:
        row.pop("component_role", None)
        for quantity in row["quantities"]:
            quantity.pop("role", None)
    app.store.save("p1", project)
    app.add_takeoff("p1", "building", "slab_volume", length=1, width=1, thickness=1,
                        count=1, source_id="synthetic:pr481:slab:role-control")
    boq = app.open_project("p1")["boq"]
    assert {r["item_code"] for r in boq} == {"wall_tile_work", "slab_volume"}


def test_unknown_explicit_role_fails_closed_on_rebuild(tmp_path):
    app = _create(tmp_path)
    app.add_assembly_takeoff("p1", "wall_tile", FINISH, floor_id="اول", location_id="حمام", approved_by="بازبین مستقل آزمون")
    project = app.open_project("p1")
    project["takeoffs"][0]["quantities"][0]["role"] = "other"
    app.store.save("p1", project)
    with pytest.raises(ValueError, match="نقش جزء متره"):
        app.add_takeoff("p1", "building", "slab_volume", length=1, width=1, thickness=1,
                        count=1, source_id="synthetic:pr481:slab:role-control")
