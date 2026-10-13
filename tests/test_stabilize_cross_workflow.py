"""Cross-workflow integration regressions for the common reviewed BOQ gate."""
from __future__ import annotations

import copy
import pytest
from core.projects.store import ProjectStore
from core.takeoff.engine import TakeoffEngine
from core.takeoff.reviewed_structural import (
    empty_member, ReviewedStructuralWorkflow,
)
from core.takeoff.reviewed_aec import (
    empty_system, SPECS, ReviewedAECWorkflow,
)


def _column(source_id="manual:column:C1", *, joint=None):
    record = empty_member("column", "L1", "C1")
    record["source"] = {"mode": "manual", "source_id": source_id}
    record["geometry"] = {"width": .3, "depth": .4, "height": 3, "count": 1,
                          "source_ref": "C1:section", "approved_by": "checker",
                          "intersections": []}
    if joint:
        record["geometry"]["intersections"] = [
            {"id": joint, "volume_m3": .1, "source_ref": "C1-joint",
             "approved_by": "checker"}]
    record["formwork"] = {"status": "confirmed", "approved_by": "checker",
                          "surfaces": [{"id": "east", "net_area_m2": 1.0,
                                        "source_ref": "C1:section"}]}
    for kind in record["rebars"]:
        record["rebars"][kind] = {"status": "not_applicable",
                                  "reason": "omitted by reviewed source schedule",
                                  "approved_by": "checker",
                                  "source_ref": f"C1:{kind}"}
    return record


def _wall(source_id="manual:wall:W1"):
    record = empty_system("block_wall", "L1", "W1")
    record["source"] = {"mode": "manual", "source_id": source_id}
    for group in SPECS["block_wall"].components:
        record["components"][group] = {
            "status": "not_applicable", "reason": "not present on reviewed plan",
            "source_ref": f"W1:{group}", "approved_by": "checker"}
    for group, unit in (("blocks", "عدد"), ("mortar", "m3")):
        record["components"][group] = {
            "status": "confirmed", "approved_by": "checker",
            "items": [{"line_id": group, "mode": "measured",
                       "domain": "building", "item_code": group,
                       "quantity": 6 if group == "blocks" else .3,
                       "unit": unit, "formula": "approved manual measurement",
                       "description": "مصالح دیوار", "source_ref": f"W1:{group}",
                       "measurement_ref": f"plan:W1:{group}"}]}
    return record


def _workflows(tmp_path):
    store = ProjectStore(tmp_path / "engineer.sqlite")
    store.save("P1", {"id": "P1", "name": "نمونه یکپارچگی",
                      "takeoffs": [], "boq": []})
    engine = TakeoffEngine()
    return store, ReviewedStructuralWorkflow(store, engine), ReviewedAECWorkflow(store, engine)


def test_structural_and_architectural_items_coexist_without_duplicate_sources(tmp_path):
    store, structural, aec = _workflows(tmp_path)
    structural.save_draft("P1", _column())
    aec.save_draft("P1", _wall())
    structural.commit("P1", "column", "L1", "C1", expected_revision=1)
    aec.commit("P1", "block_wall", "L1", "W1", expected_revision=1)
    project = store.get("P1")
    assert len(project["takeoffs"]) == 4
    assert len({r["source_id"] for r in project["takeoffs"]}) == 4
    assert {"m3", "m2", "عدد"}.issubset({r["unit"] for r in project["boq"]})
    store.close()


def test_same_physical_source_cannot_be_reused_across_structural_and_aec(tmp_path):
    store, structural, aec = _workflows(tmp_path)
    structural.save_draft("P1", _column(source_id="region:1"))
    with pytest.raises(ValueError, match="تکرار"):
        aec.save_draft("P1", _wall(source_id="region:1"))
    assert not store.get("P1")["takeoffs"]
    store.close()


def test_existing_committed_source_cannot_be_reused_in_other_domain(tmp_path):
    store, structural, aec = _workflows(tmp_path)
    structural.save_draft("P1", _column(source_id="region:1"))
    structural.commit("P1", "column", "L1", "C1", expected_revision=1)
    with pytest.raises(ValueError):
        aec.save_draft("P1", _wall(source_id="region:1"))
    assert len(store.get("P1")["takeoffs"]) == 2
    store.close()


def test_geometry_and_material_stale_approval_cannot_be_committed(tmp_path):
    store, structural, aec = _workflows(tmp_path)
    before = _wall()
    aec.save_draft("P1", before)
    modified = copy.deepcopy(before)
    modified["components"]["blocks"]["items"][0]["quantity"] += 3
    with pytest.raises(ValueError, match="تغییر"):
        aec.save_draft("P1", modified, expected_revision=1)
    modified["components"]["blocks"]["status"] = "needs_review"
    aec.save_draft("P1", modified, expected_revision=1)
    with pytest.raises(ValueError):
        aec.commit("P1", "block_wall", "L1", "W1", expected_revision=2)
    store.close()
