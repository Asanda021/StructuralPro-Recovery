"""Synthetic checks of occurrence decisions and non-financial quantities."""
from copy import deepcopy
import json

import pytest

from core.drawings.pdf_auto_intake import inspect_pdf_sheet_set
from test_phase8_p2_a_pdf_combined_graph import registry, sheets
from test_phase8_p2_a_pdf_member_review import column_set, review_data


def _conflicting_review(source):
    review = review_data(source)
    review["groups"][0]["detail"]["marks"] = []
    review["groups"][1]["detail"]["marks"][1]["printed_id"] = "A01"
    return review


def test_conflicting_schedule_blocks_all_participants_even_under_other_plan_type(tmp_path):
    source = column_set(tmp_path)
    record = inspect_pdf_sheet_set([source], member_review=_conflicting_review(source))["detail_evidence_graph"]
    rows = {r["printed_member_id"]: r for r in record["occurrence_reviews"]}
    assert set(rows) == {"A01", "A02", "A03"}
    assert rows["A01"]["type_tag"] == "C1"
    for row in rows.values():
        assert row["status"] == "BLOCKED"
        assert row["decision_code"] == "DESIGN_AUTHORITY_REQUIRED"
        assert row["reason_code"] == "C2_PRINTED_SCHEDULE_CONFLICT"
        assert row["quantity_status"] == "NO_QUANTITY" and row["member_quantity"] is None
        assert row["quantity_approval_count"] == 0
        assert {a["page"] for a in row["conflicting_anchors"]} == {2, 3}
        assert all(a["source_sha256"] for a in row["conflicting_anchors"])
        assert row["axis_node_ids"] and row["target_id"]
    assert record["temporary_quantity_count"] == 0


def test_review_overwrite_and_current_registration_do_not_clear_conflict(tmp_path):
    from core.drawings.pdf_member_review import require_preserved_occurrence_conflicts

    source = column_set(tmp_path)
    earlier = _conflicting_review(source)
    clean = deepcopy(earlier)
    clean["groups"][1]["detail"]["marks"][1]["printed_id"] = "A03"
    with pytest.raises(ValueError, match="اصلاحیه"):
        require_preserved_occurrence_conflicts(earlier, clean)
    assert require_preserved_occurrence_conflicts(earlier, deepcopy(earlier)) is None
    doc_register = registry((source, "SYNTHETIC", "R9", "CURRENT"))
    graph = inspect_pdf_sheet_set([source], revision_registry=doc_register, member_review=earlier)["detail_evidence_graph"]
    assert {r["reason_code"] for r in graph["occurrence_reviews"]} == {"C2_PRINTED_SCHEDULE_CONFLICT"}
    assert graph["quantity_approval_count"] == graph["temporary_quantity_count"] == 0


def _explicit_set(tmp_path, *, length="300 CM", width="400 MM", scale="1:20", duplicate=False, detail_type="C8"):
    p = sheets(tmp_path, "plan.pdf", [{
        "text": [(28, 28, "SHEET S-61 | REV R2"), (28, 54, "COLUMN PLAN"),
                 (180, 180, "INSTANCE J17 TYPE C8 GRID B/7 LEVEL L09"),
                 (30, 335, "FOR INSTANCE J17 DETAIL K-4 / S-73")],
        "boxes": [(180, 116, 244, 164)],
    }])
    a = sheets(tmp_path, "axis.pdf", [{
        "text": [(28, 28, "SHEET S-62 | REV R2"), (28, 54, "AXIS PLAN"),
                 (60, 95, "GRID B/7")],
    }])
    s = sheets(tmp_path, "section.pdf", [{
        "text": [(28, 28, "SHEET S-63 | REV R2"), (28, 54, "SECTION A-A"),
                 (60, 95, "LEVEL L09"),
                 (60, 140, f"COLUMN RANGE J17 GRID B/7 LEVEL L09 FROM 1.2 M TO 4.2 M LENGTH {length} COUNT 1")],
    }])
    points_per_m = 72 / (0.0254 * 20)
    d = sheets(tmp_path, "detail.pdf", [{
        "text": [(28, 28, "SHEET S-73 | REV R2"),
                 (175, 185, f"DETAIL K-4 COLUMN {detail_type}"), (175, 205, f"SCALE {scale}"),
                 (28, 252, f"COLUMN DIM J17 TYPE C8 WIDTH {width}"),
                 (28, 274, "COLUMN DIM J17 TYPE C8 DEPTH 0.50 M"),
                 (28, 302, "COLUMN SPEC J17 TYPE C8 RECTANGULAR CONCRETE CONNECTIONS INCLUDED DEDUCTIONS 0.04 M3")],
        "boxes": [(175, 90, 175 + 0.4 * points_per_m, 90 + 0.50 * points_per_m)],
    }])
    paths = [p, a, s, d]
    if duplicate:
        paths.append(sheets(tmp_path, "duplicate-plan.pdf", [{
            "text": [(28, 28, "SHEET S-81 | REV R2"), (28, 54, "COLUMN PLAN"),
                     (180, 180, "INSTANCE J17 TYPE C8 GRID B/7 LEVEL L09")],
            "boxes": [(180, 116, 244, 164)],
        }]))
    return paths


def _run_explicit(paths, *, register=True):
    source_register = registry(*[(p, "SYNTHETIC", "R2", "CURRENT") for p in paths]) if register else None
    return inspect_pdf_sheet_set(paths, revision_registry=source_register)["detail_evidence_graph"]


def test_rectangular_occurrence_with_complete_anchored_dimensions_has_nonfinancial_preview(tmp_path):
    graph = _run_explicit(_explicit_set(tmp_path))
    row, = graph["occurrence_reviews"]
    assert row["status"] == "COMPLETE_NONFINANCIAL"
    assert row["missing_evidence"] == []
    assert row["quantity_status"] == "TEMPORARY_NONFINANCIAL" and row["member_quantity"] == "0.56"
    assert row["quantity_unit"] == "m3" and row["financially_payable"] is False
    assert row["physical_member_verified"] is True
    assert row["quantity_formula"]
    assert row["axis_node_ids"] and row["target_id"]
    assert len({a["source_sha256"] for a in row["anchors"]}) == 4
    assert graph["fully_evidenced_member_count"] == graph["temporary_quantity_count"] == 1
    assert graph["quantity_approval_count"] == 0 and graph["floor_repetition_multiplier"] is None


@pytest.mark.parametrize("option,missing", [
    ({"width": "400"}, "MEASUREMENT_UNIT"),
    ({"scale": "1:40"}, "LOCAL_SCALE_CALIBRATION"),
    ({"length": "310 CM"}, "INSTALLATION_LEVEL_RANGE"),
    ({"duplicate": True}, "FLOOR_AND_OVERLAP_SCOPE"),
])
def test_incompatible_or_missing_evidence_vetoes_preview(tmp_path, option, missing):
    graph = _run_explicit(_explicit_set(tmp_path, **option))
    row, = graph["occurrence_reviews"]
    assert row["status"] != "COMPLETE_NONFINANCIAL" and missing in row["missing_evidence"]
    assert row["member_quantity"] is None and graph["temporary_quantity_count"] == 0


def test_unregistered_pdf_cannot_approve_an_otherwise_complete_occurrence(tmp_path):
    graph = _run_explicit(_explicit_set(tmp_path), register=False)
    row, = graph["occurrence_reviews"]
    assert "GOVERNING_REVISION" in row["missing_evidence"]
    assert row["member_quantity"] is None and graph["quantity_approval_count"] == 0


def test_reopening_operator_receipt_cannot_reassign_seen_conflict_in_qt(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QFileDialog

    from app.graphical_takeoff import GraphicalTakeoffDialog
    from core.platform.application import StructuralProApp

    app = QApplication.instance() or QApplication([])
    source = column_set(tmp_path)
    original = _conflicting_review(source)
    packet = tmp_path / "witness.json"
    packet.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *a: ([str(source)], ""))
    service = StructuralProApp(tmp_path / "store")
    service.create_project("Synthetic review", "QA")
    previous = service.store.current_digest("QA")
    window = GraphicalTakeoffDialog(app_service=service, project_id="QA")
    try:
        window.select_pdf_sheet_set()
        window._attach_pdf_member_review(packet, window._pdf_auto_report)
        retained = window._pdf_auto_report
        replacement = deepcopy(original)
        replacement["groups"][1]["detail"]["marks"][1]["printed_id"] = "A03"
        packet.write_text(json.dumps(replacement), encoding="utf-8")
        with pytest.raises(ValueError, match="اصلاحیه"):
            window._attach_pdf_member_review(packet, retained)
        assert window._pdf_auto_report is retained
        assert {r["status"] for r in retained["detail_evidence_graph"]["occurrence_reviews"]} == {"BLOCKED"}
        assert service.store.current_digest("QA") == previous and window.session.items == []
    finally:
        window.close()
        app.processEvents()
        service.store.close()


def test_structural_sheet_reviews_are_visible_and_do_not_create_occurrences(tmp_path):
    source = sheets(tmp_path, "synthetic-structural.pdf", [
        {"text": [(25, 29, "Excavation Plan"), (100, 120, "F2")]},
        {"text": [(25, 29, "Foundation Plan"), (100, 120, "F2"), (250, 120, "F2")]},
        {"text": [(25, 29, "Beam Layout Plan")], "boxes": [(120, 150, 400, 175)]},
        {"text": [(25, 29, "Floor Preparation Plan"), (100, 120, "B1")]},
    ])
    graph = inspect_pdf_sheet_set([source])["detail_evidence_graph"]
    open_cases = graph["structural_plan_reviews"]
    assert sum(w["role"] == "FOUNDATION_TYPE_MARK_REVIEW" for w in open_cases) == 3
    mismatch, = [w for w in open_cases if w["role"] == "FOUNDATION_MARK_COUNT_DISCREPANCY"]
    assert mismatch["type_tag"] == "F2"
    assert mismatch["source_id"] != mismatch["target_id"]
    assert all(w["anchors"][0]["page"] != 4 and w["financially_payable"] is False for w in open_cases)
    assert any(w["family"] == "beam" and w["anchors"][0]["page"] == 3 for w in open_cases)
    assert not graph["occurrence_reviews"] and graph["temporary_quantity_count"] == 0


def test_occurrence_requires_printed_revision_on_page_that_supplies_callout(tmp_path):
    _, axis, section, detail = _explicit_set(tmp_path)
    plan = sheets(tmp_path, "scoped-plan.pdf", [{
        "text": [(28, 28, "SHEET S-61 | REV R2"), (28, 54, "COLUMN PLAN"),
                 (180, 180, "INSTANCE J17 TYPE C8 GRID B/7 LEVEL L09")],
        "boxes": [(180, 116, 244, 164)],
    }])
    callout = sheets(tmp_path, "unprinted-revision.pdf", [{
        "text": [(28, 28, "SHEET S-64"), (28, 54, "SECTION A-A"),
                 (180, 180, "INSTANCE J17 TYPE C8 GRID B/7 LEVEL L09"),
                 (30, 335, "FOR INSTANCE J17 DETAIL K-4 / S-73")],
    }])
    g = _run_explicit([plan, axis, section, detail, callout])
    row, = g["occurrence_reviews"]
    assert any(a["kind"] == "CALLOUT" and a["document_id"] == "PDF005" for a in row["anchors"])
    assert "GOVERNING_REVISION" in row["missing_evidence"]
    assert row["member_quantity"] is None and g["temporary_quantity_count"] == 0


def _review_region(path, *, sample_id="P-01", bbox=(170, 100, 251, 171), refs=("PDF001:p1:d1:s1",)):
    from hashlib import sha256

    return {"sample_id": sample_id, "document_id": "PDF001", "page": 1,
            "source_sha256": sha256(path.read_bytes()).hexdigest(),
            "bbox_pt": list(bbox), "source_operator_ids": list(refs)}


def test_quantity_review_keeps_raw_points_and_reuses_the_calibrated_preview(tmp_path):
    paths = _explicit_set(tmp_path)
    authority = registry(*[(p, "SYNTHETIC", "R2", "CURRENT") for p in paths])
    region = _review_region(paths[0])
    report = inspect_pdf_sheet_set(paths, revision_registry=authority, quantity_review_regions=[region])
    row, = report["quantity_evidence_review"]["rows"]
    area, = [v for v in row["raw_measurements"] if v["kind"] == "CLOSED_OUTLINE_AREA"]
    assert area["value"] == 64 * 48 and area["unit"] == "pt2"
    assert area["source_operator_ids"] == region["source_operator_ids"]
    assert area["component_id"] and area["parent_component_ids"] and len(area["points_pt"]) == 4
    candidate = row["quantity_candidate"]
    assert row["status"] == "QUANTITY_CANDIDATE" and row["gate_reasons"] == ["ENGINEERING_APPROVAL_REQUIRED"]
    assert candidate["value"] == "0.56" and candidate["unit"] == "m3"
    assert candidate["governing_revision"] == "R2" and len(candidate["evidence"]) > 4
    assert candidate["source_operator_ids"] == region["source_operator_ids"]
    assert candidate["plan_geometry_evidence"]["source_sha256"] == region["source_sha256"]
    assert not row["engineering_approved"] and not row["financially_payable"]
    assert not report["quantity_evidence_review"]["aggregate_permitted"]
    assert report["quantity_approval_count"] == 0


@pytest.mark.parametrize("mode,gate", [
    ("unregistered", "BLOCKED_REVISION"), ("unit", "BLOCKED_UNIT"),
    ("conflicting_scale", "BLOCKED_UNIT"), ("wrong_extent", "BLOCKED_TYPE"),
    ("conflicting_type", "BLOCKED_CONFLICT"),
    ("repeat_same_geometry", "BLOCKED_CONFLICT"),
])
def test_quantity_review_never_routes_around_required_evidence(tmp_path, mode, gate):
    paths = _explicit_set(tmp_path, **({"width": "400"} if mode == "unit" else
                                    {"scale": "1:40"} if mode == "conflicting_scale" else
                                    {"detail_type": "C9"} if mode == "conflicting_type" else {}))
    authority = None if mode == "unregistered" else registry(*[(p, "SYNTHETIC", "R2", "CURRENT") for p in paths])
    bbox = (170, 100, 210, 171) if mode == "wrong_extent" else (170, 100, 251, 171)
    regions = [_review_region(paths[0], bbox=bbox)]
    if mode == "repeat_same_geometry":
        regions.append(_review_region(paths[0], sample_id="P-02", bbox=bbox))
    report = inspect_pdf_sheet_set(paths, revision_registry=authority, quantity_review_regions=regions)
    for row in report["quantity_evidence_review"]["rows"]:
        assert gate in row["gate_reasons"]
        assert row["quantity_candidate"] is None and not row["financially_payable"]
    if mode == "wrong_extent":
        assert report["quantity_evidence_review"]["rows"][0]["raw_measurements"] == []



def test_quantity_review_rejects_foreign_shared_and_duplicate_source_refs(tmp_path):
    from core.drawings.pdf_quantity_evidence import build_pdf_quantity_evidence_review

    p = sheets(tmp_path, "simple.pdf", [{"boxes": [(180, 116, 244, 164)]}])
    report = inspect_pdf_sheet_set([p])
    region = _review_region(p)
    for change in ({"source_sha256": "f" * 64}, {"source_operator_ids": ["PDF001:p1:d99:s1"]},
                   {"source_operator_ids": ["PDF001:p1:d1:s1", "PDF001:p1:d1:s1"]}):
        with pytest.raises(ValueError, match="source selection"):
            build_pdf_quantity_evidence_review(report, [{**region, **change}])
    boundaries = report["operator_component_review"]["boundary_components"]
    boundaries.append(deepcopy(boundaries[0]))
    with pytest.raises(ValueError, match="Shared source operator"):
        build_pdf_quantity_evidence_review(report, [region])


def test_quantity_preview_cannot_be_attached_to_section_geometry(tmp_path):
    paths = _explicit_set(tmp_path)
    other = sheets(tmp_path, "unissued-view.pdf", [{
        "text": [(28, 28, "SHEET S-64"), (28, 54, "SECTION B-B"),
                 (180, 180, "INSTANCE J17 TYPE C8 GRID B/7 LEVEL L09")],
        "boxes": [(180, 116, 244, 164)],
    }])
    paths.append(other)
    authority = registry(*[(p, "SYNTHETIC", "R2", "CURRENT") for p in paths])
    region = _review_region(other, refs=("PDF005:p1:d1:s1",))
    region["document_id"] = "PDF005"
    report = inspect_pdf_sheet_set(paths, revision_registry=authority, quantity_review_regions=[region])
    row, = report["quantity_evidence_review"]["rows"]
    assert row["raw_measurements"]
    assert report["detail_evidence_graph"]["temporary_quantity_count"] == 1
    assert row["quantity_candidate"] is None
    assert "BLOCKED_REVISION" in row["gate_reasons"]


def test_quantity_gate_rejects_ambiguous_component_even_with_a_complete_preview(tmp_path):
    from core.drawings.pdf_quantity_evidence import build_pdf_quantity_evidence_review

    paths = _explicit_set(tmp_path)
    authority = registry(*[(p, "SYNTHETIC", "R2", "CURRENT") for p in paths])
    report = inspect_pdf_sheet_set(paths, revision_registry=authority)
    region = _review_region(paths[0])
    component, = [r for r in report["operator_component_review"]["boundary_components"]
                  if r["source_operator_ids"] == region["source_operator_ids"]]
    component.update(classification_status="AMBIGUOUS", relation_flags=["SHARED_TOPOLOGY_PARENT"])
    row, = build_pdf_quantity_evidence_review(report, [region])["rows"]
    assert row["raw_measurements"] and row["quantity_candidate"] is None
    assert "BLOCKED_TYPE" in row["gate_reasons"]
