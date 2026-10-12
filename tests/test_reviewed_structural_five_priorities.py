"""Whole-structure review contracts: beams, columns, tie beams and foundations.

The suite exercises the real public Store/TakeoffEngine API. Tests do not
assert Windows UI behavior and do not require packaged releases.
"""
import copy
import hashlib

import pytest

from core.drawings.member_evidence import explicit_member_dimensions, index_member_evidence
from core.takeoff.reviewed_components import cut_length, net_concrete, net_formwork, reviewed_steel
from core.takeoff.reviewed_structural import (
    empty_member, preview_member, ReviewedStructuralWorkflow, KINDS,
)
from core.takeoff.engine import TakeoffEngine
from core.projects.store import ProjectStore


def approved(kind="column", ident="C1", *, floor="L1"):
    record = empty_member(kind, floor, ident)
    record["source"] = {"mode": "manual", "source_id": f"manual:{floor}:{kind}:{ident}"}
    dims = {"column": {"width": .4, "depth": .5, "height": 3, "count": 2},
            "tie_beam": {"length": 5, "width": .3, "depth": .5, "count": 1},
            "isolated_footing": {"length": 2, "width": 2, "thickness": .5, "count": 1},
            "strip_footing": {"length": 12, "width": .8, "thickness": .6, "count": 1},
            "mat_footing": {"length": 12, "width": 10, "thickness": .7, "count": 1}}[kind]
    record["geometry"] = {**dims, "intersections": [], "source_ref": "approved-plan",
                          "approved_by": "structural-reviewer"}
    record["formwork"] = {"status": "confirmed", "approved_by": "structural-reviewer",
                          "area_scope": "total_group", "area_scope_ref": "approved-formwork-schedule",
                          "surfaces": [{"id": "face-east", "net_area_m2": 2.4,
                                        "source_ref": "approved-section"}]}
    for group in record["rebars"]:
        record["rebars"][group] = {"status": "not_applicable",
                                  "reason": "explicitly excluded by reviewed schedule",
                                  "approved_by": "structural-reviewer",
                                  "source_ref": f"reviewed-schedule:{group}"}
    return record


@pytest.mark.parametrize("kind,expected", [
    ("column", 1.2), ("tie_beam", .75), ("isolated_footing", 2.0),
    ("strip_footing", 5.76), ("mat_footing", 84.0),
])
def test_five_structural_concrete_volumes_use_existing_engine(kind, expected):
    draft = approved(kind)
    report = preview_member(draft, TakeoffEngine())
    assert report["ready"], report["blockers"]
    concrete = next(r for r in report["rows"] if r["code"] == "concrete")
    assert concrete["quantity"] == pytest.approx(expected)
    assert next(r for r in report["rows"] if r["code"] == "formwork")["quantity"] == 2.4


def test_rebar_parts_hooks_lap_anchorage_without_guessed_coefficients():
    length, evidence = cut_length({
        "source_ref": "detail C1-3", "approved_by": "checker",
        "length_parts_m": [
            {"kind": "straight", "length_m": 3, "source_ref": "section"},
            {"kind": "hook", "length_m": .25, "source_ref": "bend-detail"},
            {"kind": "lap", "length_m": .4, "source_ref": "lap-schedule"},
            {"kind": "anchorage", "length_m": .15, "source_ref": "anchor-detail"},
        ],
    })
    assert length == pytest.approx(3.8)
    assert evidence["method"] == "approved_parts"


@pytest.mark.parametrize("record", [
    {"source_ref": "detail", "approved_by": "checker",
     "cut_length_m": 4, "length_parts_m": [{"kind": "straight", "length_m": 4, "source_ref": "X"}]},
    {"source_ref": "detail", "approved_by": "checker",
     "length_parts_m": [{"kind": "hook", "length_m": .2, "source_ref": "X"}]},
    {"source_ref": "detail", "approved_by": "checker",
     "length_parts_m": [{"kind": "straight", "length_m": 3, "source_ref": ""}]},
    {"source_ref": "detail", "approved_by": "checker", "cut_length_m": float("nan")},
    {"source_ref": "detail", "approved_by": "checker", "cut_length_m": -5},
])
def test_reject_invalid_cut_component_evidence(record):
    with pytest.raises(ValueError):
        cut_length(record)


def test_verified_steel_is_engine_quantity_not_formula_duplicate():
    draft = approved()
    draft["rebars"]["longitudinal"] = {
        "status": "confirmed", "source_ref": "column-C1", "approved_by": "checker",
        "count_scope": "total_group", "count_scope_ref": "C1/all-columns-bar-schedule",
        "segments": [{"source_ref": "C1/long", "approved_by": "checker",
                      "count": 8, "unit_weight_kg_m": 2.47,
                      "unit_weight_source": "reviewed-bar-table",
                      "length_parts_m": [
                          {"kind": "straight", "length_m": 3, "source_ref": "C1/elevation"},
                          {"kind": "lap", "length_m": .6, "source_ref": "C1/laps"}]}]}
    result = preview_member(draft, TakeoffEngine())
    assert result["ready"], result["blockers"]
    assert next(r for r in result["rows"] if r["code"] == "rebar")["quantity"] == pytest.approx(71.136)


def test_unreviewed_group_is_not_zero_and_blocks_boq():
    draft = approved()
    draft["rebars"]["ties"] = {"status": "needs_review"}
    out = preview_member(draft, TakeoffEngine())
    assert not out["ready"]
    assert not any(r["source_id"].endswith("ties") for r in out["rows"])


def test_formwork_faces_cannot_repeat_and_unreviewed_cannot_commit():
    draft = approved()
    draft["formwork"]["surfaces"].append(copy.deepcopy(draft["formwork"]["surfaces"][0]))
    assert not preview_member(draft, TakeoffEngine())["ready"]
    draft = approved()
    draft["formwork"] = {"status": "unreviewed"}
    assert not preview_member(draft, TakeoffEngine())["ready"]


def test_concrete_intersections_are_explicit_and_unique():
    assert net_concrete(2, [{"id": "joint-1", "volume_m3": .3,
                             "source_ref": "drawing-1", "approved_by": "checker"}])[0] == pytest.approx(1.7)
    with pytest.raises(ValueError):
        net_concrete(1, [{"id": "joint", "volume_m3": .6, "source_ref": "a", "approved_by": "x"},
                         {"id": "joint", "volume_m3": .2, "source_ref": "b", "approved_by": "y"}])
    with pytest.raises(ValueError):
        net_concrete(1, [{"id": "joint", "volume_m3": 1.01, "source_ref": "a", "approved_by": "x"}])


def test_no_not_applicable_without_reviewer_reference_and_reason():
    data = approved("isolated_footing", "F1")
    data["rebars"]["bottom_x"] = {"status": "not_applicable", "reason": ""}
    assert not preview_member(data, TakeoffEngine())["ready"]


def test_sqlite_roundtrip_then_atomic_boq_commit_and_duplicate_block(tmp_path):
    p = tmp_path / "projects.db"
    store = ProjectStore(p)
    store.save("P1", {"id": "P1", "name": "بررسی", "takeoffs": [], "boq": []})
    wf = ReviewedStructuralWorkflow(store, TakeoffEngine())
    first = wf.save_draft("P1", approved("column", "C1"))
    assert first["revision"] == 1
    store.close()
    store = ProjectStore(p)
    wf = ReviewedStructuralWorkflow(store, TakeoffEngine())
    assert wf.get("P1", "column", "L1", "C1")["revision"] == 1
    result = wf.commit("P1", "column", "L1", "C1", expected_revision=1)
    assert result["status"] == "committed"
    assert store.get("P1")["boq"]
    with pytest.raises(ValueError):
        wf.commit("P1", "column", "L1", "C1", expected_revision=1)
    store.close()


def test_missing_group_commit_stays_atomic(tmp_path):
    store = ProjectStore(tmp_path / "projects.db")
    store.save("P1", {"id": "P1", "name": "بررسی", "takeoffs": [], "boq": []})
    wf = ReviewedStructuralWorkflow(store, TakeoffEngine())
    bad = approved("strip_footing", "F2")
    bad["rebars"]["bottom_y"] = {"status": "unreviewed"}
    wf.save_draft("P1", bad)
    with pytest.raises(ValueError, match="متره ناقص"):
        wf.commit("P1", "strip_footing", "L1", "F2", expected_revision=1)
    project = store.get("P1")
    assert project["boq"] == [] and project["takeoffs"] == []
    store.close()


def test_stale_revision_rejected_before_boq(tmp_path):
    store = ProjectStore(tmp_path / "projects.db")
    store.save("P1", {"id": "P1", "name": "بررسی", "takeoffs": [], "boq": []})
    wf = ReviewedStructuralWorkflow(store, TakeoffEngine())
    wf.save_draft("P1", approved())
    with pytest.raises(RuntimeError, match="تعارض نسخه"):
        wf.commit("P1", "column", "L1", "C1", expected_revision=0)
    assert not store.get("P1")["boq"]
    store.close()


def test_duplicate_concrete_intersection_across_column_and_footing(tmp_path):
    store = ProjectStore(tmp_path / "projects.db")
    store.save("P1", {"id": "P1", "name": "بررسی", "takeoffs": [], "boq": []})
    wf = ReviewedStructuralWorkflow(store, TakeoffEngine())
    deduction = {"id": "joint-C1-F1", "volume_m3": .1, "source_ref": "section",
                 "approved_by": "checker"}
    for kind, ident in [("column", "C1"), ("isolated_footing", "F1")]:
        draft = approved(kind, ident)
        draft["geometry"]["intersections"] = [copy.deepcopy(deduction)]
        wf.save_draft("P1", draft)
    wf.commit("P1", "column", "L1", "C1", expected_revision=1)
    with pytest.raises(ValueError, match="قبلاً"):
        wf.commit("P1", "isolated_footing", "L1", "F1", expected_revision=1)
    store.close()


def test_revised_source_resets_existing_approvals(tmp_path):
    store = ProjectStore(tmp_path / "projects.db")
    store.save("P1", {"id": "P1", "name": "بررسی", "takeoffs": [], "boq": []})
    wf = ReviewedStructuralWorkflow(store, TakeoffEngine())
    first = approved()
    wf.save_draft("P1", first)
    changed = copy.deepcopy(first)
    changed["source"]["source_id"] = "other-drawing-source"
    with pytest.raises(ValueError, match="منبع تغییر"):
        wf.save_draft("P1", changed, expected_revision=1)
    store.close()


def test_actual_drawing_file_hash_checked(tmp_path):
    store = ProjectStore(tmp_path / "projects.db")
    store.save("P1", {"id": "P1", "name": "بررسی", "takeoffs": [], "boq": []})
    wf = ReviewedStructuralWorkflow(store, TakeoffEngine())
    path = tmp_path / "sample.dxf"
    path.write_bytes(b"untouched source")
    d = approved()
    d["source"] = {"mode": "drawing", "source_id": "C1-region", "page": 1,
                   "drawing_path": str(path), "selected_region": [10, 20, 30, 40],
                   "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    wf.save_draft("P1", d)
    path.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="اثر انگشت"):
        wf.commit("P1", "column", "L1", "C1", expected_revision=1)
    store.close()


@pytest.mark.parametrize("kind,tag,line,wanted", [
    ("beam", "B1", "B1 طول=5m عرض=30cm عمق=50cm", "depth"),
    ("column", "C1", "C1 عرض=40cm عمق=50cm ارتفاع=3m", "height"),
    ("tie_beam", "TB1", "TB1 طول=10m عرض=30cm عمق=50cm", "length"),
    ("isolated_footing", "F1", "F1 طول=2m عرض=2m ضخامت=50cm", "thickness"),
])
def test_explicit_member_geometry_never_guesses_units(kind, tag, line, wanted):
    out = explicit_member_dimensions(line, kind, tag)
    assert out is not None and out[wanted] > 0


def test_unlabeled_or_wrong_member_schedule_remains_unknown():
    assert explicit_member_dimensions("F1 2x2x.5", "isolated_footing", "F1") is None
    assert explicit_member_dimensions("F10 طول=2m عرض=2m ضخامت=.5m",
                                      "isolated_footing", "F1") is None


def test_pdf_multi_page_evidence_unlocated_and_review_required():
    class Pages:
        page_count = 2
        def text(self, page):
            return {1: "C1 پلان", 2: "C1 عرض=40cm عمق=50cm ارتفاع=3m"}[page]
    result = index_member_evidence("column", "C1", drawing_sha256="a"*64, pdf_engine=Pages())
    assert len(result["candidates"]) == 2
    assert result["candidates"][1]["proposed_geometry"]["height"] == 3
    assert result["candidates"][1]["page"] == 2
    assert not result["candidates"][1]["located"]
    assert not result["ready_for_boq"]


def test_pdf_out_of_scope_and_ambiguity_not_approved():
    class Pages:
        page_count = 1
        def text(self, page):
            return "B1 طول=5m عرض=30cm عمق=50cm\nB1 طول=6m عرض=30cm عمق=50cm"
    out = index_member_evidence("beam", "B1", drawing_sha256="b"*64, pdf_engine=Pages())
    assert len(out["candidates"]) == 2
    assert not out["quantity_approved"]


def test_manual_import_does_not_masquerade_as_drawing_hash():
    data = approved()
    data["source"]["detail_evidence"] = {"kind": "pdf", "page": 1}
    assert not preview_member(data, TakeoffEngine())["ready"]


def test_beam_shared_rebar_length_parts_concrete_joints_and_form_faces():
    from core.takeoff.beam_detail import empty_beam, preview_beam
    d = empty_beam("L1", "B1")
    d["source"] = {"mode": "manual", "source_id": "manual:P1:L1:B1"}
    d["geometry"] = {"length": 5, "width": .3, "depth": .5, "count": 1,
                     "approved_by": "engineer", "source_ref": "B1/section",
                     "intersections": [{"id": "beam-column-joint-1", "volume_m3": .1,
                                        "approved_by": "engineer", "source_ref": "B1/joint"}]}
    d["formwork"] = {"approved_by": "engineer", "source_ref": "B1/face-detail",
                     "surfaces": [{"id": "left", "net_area_m2": 3, "source_ref": "B1/detail"},
                                  {"id": "right", "net_area_m2": 3, "source_ref": "B1/detail"}]}
    for kind in d["bars"]:
        d["bars"][kind] = {"status": "not_applicable", "reason": "reviewed absent",
                           "approved_by": "engineer", "source_ref": "B1/schedule"}
    d["bars"]["longitudinal"] = {
        "status": "confirmed", "approved_by": "engineer",
        "source_ref": "B1/long-detail", "count": 4,
        "unit_weight_kg_m": 2.47, "unit_weight_source": "approved-bar-table",
        "length_parts_m": [
            {"kind": "straight", "length_m": 5, "source_ref": "B1/plan"},
            {"kind": "anchorage", "length_m": .5, "source_ref": "B1/anchor"},
        ],
    }
    report = preview_beam(d, TakeoffEngine())
    assert report["ready"], report["blockers"]
    assert next(row for row in report["rows"] if row["code"] == "beam")["quantity"] == pytest.approx(.65)
    assert next(row for row in report["rows"] if row["code"] == "formwork")["quantity"] == 6
    assert next(row for row in report["rows"] if row["source_id"].endswith("longitudinal"))["quantity"] == pytest.approx(54.34)


def test_beam_conflicting_scalar_and_detailed_deductions_are_rejected():
    from core.takeoff.beam_detail import empty_beam, preview_beam
    d = empty_beam("L1", "B1")
    d["source"] = {"mode": "manual", "source_id": "manual:B1"}
    d["geometry"] = {"length": 5, "width": .3, "depth": .5, "count": 1,
                     "approved_by": "engineer", "source_ref": "B1/section",
                     "deductions_m3": .2,
                     "intersections": [{"id": "joint", "volume_m3": .1,
                                        "source_ref": "B1/joint", "approved_by": "engineer"}]}
    assert not preview_beam(d, TakeoffEngine())["ready"]


def test_domain_foundation_and_column_reject_non_finite_values():
    from core.engineering.domains.foundations import foundation_quantities
    from core.engineering.domains.concrete import concrete_quantities
    for bad in (float("nan"), float("inf"), float("-inf"), True):
        with pytest.raises(ValueError):
            foundation_quantities("isolated", length=bad, width=2, depth=.5, count=1)
        with pytest.raises(ValueError):
            concrete_quantities("column", length=bad, width=.4, depth=.5, count=1)


def test_domain_result_must_be_finite():
    from core.engineering.domains.models import DomainQuantity
    with pytest.raises(ValueError):
        DomainQuantity("foundation", "footing", float("nan"), "m3", "L×W×D").validate()


def test_drawing_has_to_link_its_real_selected_region(tmp_path):
    path = tmp_path / "detail.dxf"
    path.write_bytes(b"valid drawing")
    draft = approved()
    draft["source"] = {"mode": "drawing", "source_id": "C1-1", "page": 1,
                       "drawing_path": str(path),
                       "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                       "selected_region": [1, 2, 0, 4]}
    report = preview_member(draft, TakeoffEngine())
    assert not report["ready"]
    assert any("ناحیه" in block for block in report["blockers"])


@pytest.mark.parametrize("kind,ident,axis,spacing,count,first,last", [
    ("column", "C1", 3.0, .2, 15, .1, 2.9),
    ("tie_beam", "TB1", 5.0, .2, 25, .1, 4.9),
])
def test_column_tie_or_grade_beam_stirrup_requires_real_stations(
    kind, ident, axis, spacing, count, first, last
):
    draft = approved(kind, ident)
    group = "ties" if kind == "column" else "stirrups"
    draft["geometry"]["count"] = 1  # one physical member per station plan
    schedule = {"name": "تمام طول", "start_m": 0, "end_m": axis,
                "spacing_m": spacing, "first_bar_m": first, "last_bar_m": last,
                "count": count, "cut_length_m": 1.3, "unit_weight_kg_m": .395,
                "unit_weight_source": "approved-tables", "source_ref": f"{ident}/schedule",
                "approved_by": "checker"}
    draft["rebars"][group] = {"status": "confirmed", "approved_by": "checker",
                              "source_ref": f"{ident}/schedule", "segments": [schedule]}
    report = preview_member(draft, TakeoffEngine())
    assert report["ready"], report["blockers"]
    row = next(r for r in report["rows"] if r["source_id"].endswith(group))
    assert row["quantity"] == pytest.approx(count * 1.3 * .395)
    # A confirmed count with missing physical stations is *not* proof.
    del schedule["first_bar_m"]
    assert not preview_member(draft, TakeoffEngine())["ready"]


def test_ambiguous_repeat_member_rebar_and_formwork_totals_block():
    d = approved("column", "C1")  # concrete member count is 2
    del d["formwork"]["area_scope"]
    assert not preview_member(d, TakeoffEngine())["ready"]
    d = approved("column", "C1")
    d["rebars"]["longitudinal"] = {
        "status": "confirmed", "approved_by": "checker", "source_ref": "C1/long",
        "segments": [{"count": 8, "approved_by": "checker", "source_ref": "C1/long",
                      "unit_weight_kg_m": .395, "unit_weight_source": "tables",
                      "cut_length_m": 3.5}],
    }
    assert not preview_member(d, TakeoffEngine())["ready"]
    d["rebars"]["longitudinal"]["count_scope"] = "total_group"
    d["rebars"]["longitudinal"]["count_scope_ref"] = "C1/all-identical-columns"
    assert preview_member(d, TakeoffEngine())["ready"]


def test_two_column_tie_schedule_cannot_pass_as_one():
    d = approved("column", "C1")
    d["rebars"]["ties"] = {
        "status": "confirmed", "approved_by": "checker", "source_ref": "C1/ties",
        "count_scope": "total_group", "count_scope_ref": "C1/schedule",
        "segments": [{"name": "کل ستون", "start_m": 0, "end_m": 3,
                      "spacing_m": .2, "first_bar_m": .1, "last_bar_m": 2.9,
                      "count": 15, "cut_length_m": 1.3, "unit_weight_kg_m": .395,
                      "unit_weight_source": "tables", "approved_by": "checker",
                      "source_ref": "C1/ties"}],
    }
    assert not preview_member(d, TakeoffEngine())["ready"]
