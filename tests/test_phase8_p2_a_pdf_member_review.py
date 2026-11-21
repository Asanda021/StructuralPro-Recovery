"""Source-independent structural PDF review fixtures."""
from copy import deepcopy
from hashlib import sha256
import json

import pymupdf
import pytest

from core.drawings.pdf_auto_intake import inspect_pdf_sheet_set
from core.drawings.pdf_sheet_scope_registration import classify_sheet_title
from core.drawings.pdf_vector_type_labels import _C, _ONE, _TWO


def _glyph(page, points, x, y, width, height):
    page.draw_polyline([(x + a * width, y + b * height) for a, b in points])


def _grid(page, title):
    page.insert_text((32, 32), title)
    xs, ys = (120, 280, 430), (100, 220, 340)
    for x in xs:
        page.draw_line((x, ys[0]), (x, ys[-1]))
    for y in ys:
        page.draw_line((xs[0], y), (xs[-1], y))


def column_set(tmp_path):
    source = tmp_path / "synthetic-sheets.pdf"
    with pymupdf.open() as pdf:
        _grid(pdf.new_page(width=620, height=460), "Axis Plan")
        page = pdf.new_page(width=620, height=460)
        _grid(page, "Column Type Plan")
        for x, typed in [(120, "1"), (280, "2"), (430, "2")]:
            page.draw_rect((x - 3, 97, x + 3, 103))
            _glyph(page, _C, x + 7, 105, 6, 9)
            digit, width = (_ONE, 1.5) if typed == "1" else (_TWO, 5.7)
            _glyph(page, digit, x + 16, 105, width, 9)
        page = pdf.new_page(width=620, height=460)
        page.insert_text((28, 32), "Column details")
        page.insert_text((44, 110), "C-1")
        page.insert_text((44, 210), "C-2")
        page.draw_rect((64, 78, 265, 130))
        page.draw_rect((64, 178, 265, 230))
        pdf.save(source)
    return source


def review_data(source):
    return {
        "schema_version": 1,
        "source_sha256": sha256(source.read_bytes()).hexdigest(),
        "groups": [
            {"type_tag": "C1",
             "plan": [{"page": 2, "grid_row": 1, "grid_column": 1, "printed_id": "A01",
                       "bbox_pt": [112, 115, 126, 125]}],
             "detail": {"page": 3, "bbox_pt": [33, 65, 272, 136], "printed_count": 1,
                        "marks": [{"printed_id": "A01", "bbox_pt": [225, 88, 246, 99]}]}},
            {"type_tag": "C2",
             "plan": [{"page": 2, "grid_row": 1, "grid_column": 2, "printed_id": "A02",
                       "bbox_pt": [270, 115, 283, 125]},
                      {"page": 2, "grid_row": 1, "grid_column": 3, "printed_id": "A03",
                       "bbox_pt": [422, 115, 437, 125]}],
             "detail": {"page": 3, "bbox_pt": [33, 165, 272, 236], "printed_count": 2,
                        "marks": [{"printed_id": "A02", "bbox_pt": [225, 189, 246, 200]},
                                  {"printed_id": "A04", "bbox_pt": [226, 206, 245, 219]}]}},
        ],
    }


def test_same_document_plan_axis_type_detail_and_printed_id_conflict(tmp_path):
    source = column_set(tmp_path)
    report = inspect_pdf_sheet_set([source], member_review=review_data(source))
    graph = report["detail_evidence_graph"]
    assert sum(e["relationship"] == "COLUMN_AXIS_CORROBORATION" for e in graph["edges"]) == 3
    assert sum(e["relationship"] == "COLUMN_DETAIL_TYPE_REFERENCE" for e in graph["edges"]) == 3
    observed = {r["type_tag"]: r for r in graph["member_review_groups"]}
    assert observed["C1"]["status"] == "CORROBORATED_DRAWN_IDS"
    assert observed["C2"]["status"] == "BLOCKED_PRINTED_MEMBER_ID_CONFLICT"
    assert observed["C2"]["shared_printed_ids"] == ["A02"]
    assert observed["C2"]["plan_only_printed_ids"] == ["A03"]
    assert observed["C2"]["detail_only_printed_ids"] == ["A04"]
    assert graph["quantity_approval_count"] == 0
    assert graph["physical_member_count"] is None and graph["floor_repetition_multiplier"] is None
    rows = [n for n in graph["nodes"] if n["kind"] == "INSTANCE_CANDIDATE"]
    assert len(rows) == 3
    assert all(n["quantity_status"] == "NO_QUANTITY" and n["physical_member_verified"] is False for n in rows)
    assert len({n["node_id"] for n in rows}) == 3


def test_count_only_cannot_bind_member_ids_and_bad_review_rolls_back(tmp_path):
    source = column_set(tmp_path)
    review = review_data(source)
    review["groups"][0]["detail"]["marks"] = []
    rows = inspect_pdf_sheet_set([source], member_review=review)["detail_evidence_graph"]["member_review_groups"]
    assert rows[0]["status"] == "TYPE_COUNT_ONLY"
    assert rows[0]["shared_printed_ids"] == []
    invalid = deepcopy(review)
    invalid["source_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="hash"):
        inspect_pdf_sheet_set([source], member_review=invalid)
    invalid = deepcopy(review)
    invalid["groups"][0]["plan"][0]["bbox_pt"] = [500, 400, 780, 900]
    with pytest.raises(ValueError, match="location|bounds"):
        inspect_pdf_sheet_set([source], member_review=invalid)


def test_nonstructural_floor_labels_are_retained_as_non_beam(tmp_path):
    source = tmp_path / "layer-layout.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=620, height=460)
        page.insert_text((32, 32), "Floor Preparation Plan")
        page.insert_text((100, 100), "B1")
        page.draw_rect((80, 80, 180, 150))
        pdf.save(source)
    report = inspect_pdf_sheet_set([source])
    assert classify_sheet_title("Floor Preparation Plan")["sheet_kind"] == "floor_preparation_plan"
    assert not report["member_type_candidates"]
    graph = report["detail_evidence_graph"]
    records = [n for n in graph["nodes"] if n.get("type_tag") == "B1"]
    assert records and all(n["family"] == "architecture_finishes" for n in records)
    assert not [n for n in graph["nodes"] if n["kind"] == "INSTANCE_CANDIDATE"]


def test_printed_dimensions_stay_distinct_and_unitless_mark_stays_blocked(tmp_path):
    source = tmp_path / "synthetic_dimensions.pdf"
    with pymupdf.open() as pdf:
        for values in (("B1 L=8.40m", "B2 L=770"), ("B1 L=0.40m", "F1 L=7.700")):
            page = pdf.new_page(width=620, height=460)
            for index, text in enumerate(values):
                page.insert_text((35, 80 + index * 120), text)
        pdf.save(source)
    tested = inspect_pdf_sheet_set([source])
    by_tag = {mark["tag"]: mark for mark in tested["member_type_candidates"] if mark["tag"] != "B1"}
    assert by_tag["B2"]["dimension_m"] is None and by_tag["F1"]["dimension_m"] is None
    assert {m["dimension_m"] for m in tested["member_type_candidates"] if m["tag"] == "B1"} == {"8.40", "0.40"}
    assert {m["status"] for m in tested["member_type_candidates"] if m["tag"] == "B1"} == {"BLOCKED_CROSS_SHEET_CONFLICT"}
    assert tested["quantity_approval_count"] == 0


def test_packet_cannot_reuse_member_mark_on_several_plan_pages(tmp_path):
    source = column_set(tmp_path)
    review = review_data(source)
    review["groups"][1]["plan"][1]["page"] = 1
    with pytest.raises(ValueError, match="one plan page"):
        inspect_pdf_sheet_set([source], member_review=review)


def test_member_review_ui_shows_ids_and_keeps_previous_graph_on_stale_receipt(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QFileDialog

    from app.graphical_takeoff import GraphicalTakeoffDialog
    from core.platform.application import StructuralProApp

    source = column_set(tmp_path)
    receipt = tmp_path / "source-reading.json"
    review = review_data(source)
    receipt.write_text(json.dumps(review), encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *args: ([str(source)], ""))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(receipt), ""))
    app = QApplication.instance() or QApplication([])
    service = StructuralProApp(tmp_path / "store")
    service.create_project("Synthetic ID review", "QA")
    digest = service.store.current_digest("QA")
    workspace = GraphicalTakeoffDialog(app_service=service, project_id="QA")
    try:
        workspace.select_pdf_sheet_set()
        workspace._pdf_auto_review_dialog.graph_review.member_review_button.click()
        current = workspace._pdf_auto_review_dialog
        panel = current.graph_review
        panel.sections.setCurrentIndex(panel._section_keys.index("member_review_groups"))
        view = panel.tables["member_review_groups"]
        view.setCurrentIndex(view.model().index(1, 0))
        assert "BLOCKED_PRINTED_MEMBER_ID_CONFLICT" in panel.details.toPlainText()
        assert "A03" in panel.details.toPlainText() and "A04" in panel.details.toPlainText()
        review["source_sha256"] = "a" * 64
        receipt.write_text(json.dumps(review), encoding="utf-8")
        panel.member_review_button.click()
        assert workspace._pdf_auto_review_dialog is current
        assert "hash" in panel.member_review_status.text()
        assert service.store.current_digest("QA") == digest
        assert workspace.session.items == []
    finally:
        workspace.close()
        app.processEvents()
        service.store.close()
