"""P10–P12: real SQLite, identity, review and BOQ acceptance regressions.

No GUI, CI, network, build or release needed. This suite must be run from the
repository root with the production Python modules (not the isolated stubs).
"""
from __future__ import annotations

import copy
import json
import sqlite3

import pytest

from core.projects.store import ProjectStore
from core.takeoff.boq import build_boq
from core.takeoff.commit_guards import (
    require_source_unused, require_reset_of_changed_approvals,
    validate_commit_rows, rebuild_project_boq,
)


def _q(code="concrete", amount=1.2, unit="m3", price_code=None):
    return {"code": code, "title": code, "amount": amount,
            "unit": unit, "formula": "reviewed", "price_code": price_code,
            "unit_price": None}


def _t(source_id, *, amount=1.2, intersections=None, code="concrete", original=None):
    return {"source_id": source_id, "domain": "building", "system": "L1",
            "params": {"intersections": intersections or []},
            "provenance": {"mode": "manual", "source_id": original or source_id},
            "quantities": [_q(code=code, amount=amount)]}


def _project():
    return {"id": "P1", "name": "نمونه آزمون",
            "takeoffs": [], "boq": []}


def test_sqlite_meta_does_not_pollute_disk_and_cache_matches_cold_read(tmp_path):
    db = tmp_path/"project.db"
    store = ProjectStore(db)
    store.save("P1", _project())
    cached = store.get("P1")
    assert cached["_meta"]["version"] == 1
    first_digest = store.begin_write("P1")
    cached["takeoffs"] = [_t("takeoff-A")]
    store.save("P1", cached, expected_digest=first_digest)
    assert store.get("P1")["_meta"]["version"] == 2
    store.close()
    cn = sqlite3.connect(db)
    row = cn.execute("SELECT payload FROM projects WHERE id='P1'").fetchone()[0]
    cn.close()
    assert "_meta" not in json.loads(row)
    restored = ProjectStore(db)
    assert restored.get("P1")["_meta"]["version"] == 2
    assert restored.get("P1")["takeoffs"][0]["source_id"] == "takeoff-A"
    restored.close()


def test_sqlite_optimistic_write_does_not_erase_concurrent_changes(tmp_path):
    db = tmp_path/"project.db"
    s1 = ProjectStore(db)
    s1.save("P1", _project())
    s2 = ProjectStore(db)
    digest = s1.begin_write("P1")
    new_one = s1.get("P1")
    new_two = s2.get("P1")
    new_one["name"] = "ویرایش اول"
    new_two["name"] = "ویرایش دوم"
    s1.save("P1", new_one, expected_digest=digest)
    with pytest.raises(RuntimeError, match="changed since write began"):
        s2.save("P1", new_two, expected_digest=digest)
    assert s2.db.execute("SELECT 1").fetchone()[0] == 1  # transaction rolled back
    assert s1.get("P1")["name"] == "ویرایش اول"
    assert s1.revisions("P1")[-1]["version"] == 2
    s1.close()
    s2.close()


def test_failed_json_save_keeps_sqlite_consistent(tmp_path):
    s = ProjectStore(tmp_path/"p.db")
    s.save("P1", _project())
    d = s.begin_write("P1")
    invalid = _project()
    invalid["invalid"] = float("nan")
    with pytest.raises(ValueError):
        s.save("P1", invalid, expected_digest=d)
    assert s.get("P1")["id"] == "P1"
    assert len(s.revisions("P1")) == 1
    s.close()


def test_boq_price_code_mismatch_never_aggregates():
    rows = [
        {"source_id": "one", "source": "one", "item_code": "rebar",
         "price_code": "USER-01", "description": "آرماتور", "quantity": 5,
         "unit": "kg", "unit_price": 10},
        {"source_id": "two", "source": "two", "item_code": "rebar",
         "price_code": "USER-02", "description": "آرماتور", "quantity": 7,
         "unit": "kg", "unit_price": 10},
    ]
    out = build_boq(rows)
    assert len(out) == 2
    assert {item["price_code"] for item in out} == {"USER-01", "USER-02"}


def test_boq_identical_price_code_but_different_description_never_aggregates():
    rows = [
        {"source_id": "one", "source": "one", "item_code": "rebar",
         "price_code": "USER-01", "description": "میلگرد بالا", "quantity": 5,
         "unit": "kg", "unit_price": 10},
        {"source_id": "two", "source": "two", "item_code": "rebar",
         "price_code": "USER-01", "description": "میلگرد پایین", "quantity": 7,
         "unit": "kg", "unit_price": 10},
    ]
    assert len(build_boq(rows)) == 2


@pytest.mark.parametrize("invalid", [None, True, False, float("nan"), float("inf")])
def test_boq_invalid_or_missing_quantity_is_rejected(invalid):
    with pytest.raises(ValueError):
        build_boq([{"source_id": "one", "item_code": "concrete",
                    "quantity": invalid, "unit": "m3", "description": "بتن"}])


@pytest.mark.parametrize("registry", [
    "beam_detail_register", "reviewed_structural_members", "reviewed_aec_systems"
])
def test_source_collision_across_each_registry_is_detected(registry):
    project = _project()
    project[registry] = {"one": {"data": {
        "source": {"mode": "manual", "source_id": "same-measurement"}}}}
    with pytest.raises(ValueError, match="تکرار"):
        require_source_unused(project, "same-measurement",
                              exclude=("some-other-registry", "other"))
    require_source_unused(project, "same-measurement", exclude=(registry, "one"))


def test_source_id_used_in_committed_provenance_cannot_be_reused():
    project = _project()
    project["takeoffs"] = [_t("derived-row", original="same-source")]
    with pytest.raises(ValueError):
        require_source_unused(project, "same-source")


def test_repeated_intersection_between_two_members_is_rejected():
    project = _project()
    project["takeoffs"] = [_t("previous", intersections=[{
        "id": "joint-C1-F1", "volume_m3": .2, "source_ref": "design-A"}])]
    new = _t("proposed", intersections=[{
        "id": "joint-C1-F1", "volume_m3": .2, "source_ref": "design-A"}])
    with pytest.raises(ValueError, match="کسر حجم"):
        validate_commit_rows(project, [new], source_id="new-scope")


def test_identical_new_takeoff_sources_in_single_commit_are_rejected():
    project = _project()
    with pytest.raises(ValueError):
        validate_commit_rows(project, [_t("same"), _t("same")], source_id="one")


def test_duplicate_previous_takeoff_sources_block_any_commit():
    project = _project()
    project["takeoffs"] = [_t("old"), _t("old")]
    with pytest.raises(ValueError):
        validate_commit_rows(project, [_t("new")], source_id="new-scope")


def test_shared_conversion_keeps_quantities_and_price_metadata():
    project = _project()
    proposed = [_t("a", code="concrete"), _t("b", code="rebar", amount=10)]
    validated = validate_commit_rows(project, proposed, source_id="physical-region-1")
    takeoffs, boq = rebuild_project_boq(project, validated)
    assert len(takeoffs) == 2
    assert {r["item_code"] for r in boq} == {"concrete", "rebar"}
    assert all(r["unit_price"] is None for r in boq)


@pytest.mark.parametrize("group", ["bars", "rebars", "components"])
def test_any_approved_detail_change_needs_explicit_new_review_revision(group):
    before = {group: {"x": {"status": "confirmed", "approved_by": "checker",
                           "count": 10, "source_ref": "drawing"}}}
    after = copy.deepcopy(before)
    after[group]["x"]["count"] = 11
    with pytest.raises(ValueError, match="تغییر"):
        require_reset_of_changed_approvals(before, after)
    after[group]["x"]["status"] = "needs_review"
    require_reset_of_changed_approvals(before, after)


def test_approved_geometry_and_formwork_edits_require_reset():
    old = {
        "geometry": {"length": 5, "approved_by": "checker", "source_ref": "A"},
        "formwork": {"surfaces": [{"net_area_m2": 5}], "approved_by": "checker"},
    }
    new = copy.deepcopy(old)
    new["geometry"]["length"] = 6
    with pytest.raises(ValueError):
        require_reset_of_changed_approvals(old, new)
    new["geometry"]["approved_by"] = ""
    new["formwork"]["surfaces"][0]["net_area_m2"] = 6
    with pytest.raises(ValueError):
        require_reset_of_changed_approvals(old, new)
    new["formwork"]["approved_by"] = ""
    require_reset_of_changed_approvals(old, new)



def test_second_connection_refreshes_cache_after_external_commit(tmp_path):
    db = tmp_path / "project.db"
    writer = ProjectStore(db)
    writer.save("P1", _project())
    reader = ProjectStore(db)
    assert reader.get("P1")["_meta"]["version"] == 1
    updated = writer.get("P1")
    updated["name"] = "نسخه جدید"
    writer.save("P1", updated, expected_digest=writer.begin_write("P1"))
    assert reader.get("P1")["name"] == "نسخه جدید"
    assert reader.get("P1")["_meta"]["version"] == 2
    writer.close()
    reader.close()


def test_same_waffle_void_source_cannot_be_billed_twice():
    project = _project()
    project["takeoffs"] = [_t("roof-A")]
    project["takeoffs"][0]["params"]["deduction"] = {
        "id": "void:roof-one-same-pocket", "quantity_m3": .5,
        "source_ref": "drawing-1"}
    incoming = _t("roof-B")
    incoming["params"]["deduction"] = {
        "id": "void:roof-one-same-pocket", "quantity_m3": .5,
        "source_ref": "drawing-1"}
    with pytest.raises(ValueError, match="کسر حجم"):
        validate_commit_rows(project, [incoming], source_id="roof-B-source")


def test_rebuild_boq_preserves_explicit_cost_factor_without_defaulting():
    project = _project()
    line = _t("costed")
    q = line["quantities"][0]
    q["price_code"] = "USER-1405-01"
    q["unit_price"] = 200
    q["factor"] = 1.17
    takeoffs, boq = rebuild_project_boq(project, [line])
    assert takeoffs[0]["quantities"][0]["factor"] == 1.17
    assert boq[0]["factor"] == 1.17
    assert boq[0]["total"] == pytest.approx(1.2 * 200 * 1.17)



def test_reviewed_source_collision_ignores_unassigned_draft_but_not_identity_whitespace():
    project = _project()
    project["reviewed_aec_systems"] = {
        "unfinished": {"data": {"source": {}, "components": {}}},
        "wall": {"data": {"source": {"source_id": "  manual:L1:W1  "}}},
    }
    with pytest.raises(ValueError, match="تکرار"):
        require_source_unused(project, "manual:L1:W1")
    # An incomplete, unassigned draft must not disable unrelated measurements.
    require_source_unused(project, "manual:L1:W2")


def test_committed_provenance_identity_with_whitespace_cannot_be_reused():
    project = _project()
    project["takeoffs"] = [_t("aec:wall:1", original=" manual:wall:1 ")]
    with pytest.raises(ValueError):
        require_source_unused(project, "manual:wall:1")


def test_existing_takeoff_source_whitespace_collision_rejected_in_new_commit():
    project = _project()
    project["takeoffs"] = [_t("  manual:row:1 ")]
    with pytest.raises(ValueError):
        validate_commit_rows(project, [_t("manual:row:1")], source_id="manual:row:2")


def test_whitespace_only_or_noncanonical_new_source_never_enters_boq():
    project = _project()
    for sid in ("  ", " source:1 ", "", "\n\t"):
        with pytest.raises(ValueError):
            validate_commit_rows(project, [_t(sid)], source_id="another:source")


def test_intersection_deductions_collide_across_whitespace_variations():
    project = _project()
    project["takeoffs"] = [_t("one", intersections=[{
        "id": "  joint:C1-F1 ", "volume_m3": .4,
        "source_ref": "detail", "approved_by": "reviewer"}])]
    candidate = _t("two", intersections=[{
        "id": "joint:C1-F1", "volume_m3": .4,
        "source_ref": "detail", "approved_by": "reviewer"}])
    with pytest.raises(ValueError, match="کسر حجم"):
        validate_commit_rows(project, [candidate], source_id="drawing:two")


def test_valid_separate_intersections_are_allowed_across_two_sources():
    project = _project()
    project["takeoffs"] = [_t("one", intersections=[{
        "id": "joint:C1-F1", "volume_m3": .1, "source_ref": "detail"}])]
    candidate = _t("two", intersections=[{
        "id": "joint:C1-F2", "volume_m3": .1, "source_ref": "detail"}])
    assert len(validate_commit_rows(project, [candidate], source_id="drawing:two")) == 1



def test_explicit_zero_waste_is_valid_but_omitted_waste_is_not():
    from core.takeoff.explicit_inputs import require_explicit_measurement_params
    with pytest.raises(ValueError, match="waste"):
        require_explicit_measurement_params(
            "building", "tile", {"length": 4, "height": 2, "openings": 0}
        )
    require_explicit_measurement_params(
        "building", "tile", {"length": 4, "height": 2, "openings": 0, "waste": 0}
    )
    with pytest.raises(ValueError):
        require_explicit_measurement_params("building", "tile", {"waste": -1})
    with pytest.raises(ValueError):
        require_explicit_measurement_params("building", "tile", {"waste": float("nan")})
