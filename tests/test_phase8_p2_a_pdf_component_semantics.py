"""Synthetic source-bound component and symbol dispositions."""
from hashlib import sha256

import pytest

pymupdf = pytest.importorskip("pymupdf")

from core.drawings.pdf_auto_intake import inspect_pdf_sheet_set


def _sheet(pdf, title, labels=()):
    page = pdf.new_page(width=500, height=420)
    page.insert_text((30, 32), title)
    for x, y, label in labels:
        page.insert_text((x, y), label)
    return page


def _read(pdf, tmp_path):
    source = tmp_path / "synthetic.pdf"
    pdf.save(source)
    pdf.close()
    digest = sha256(source.read_bytes()).hexdigest()
    return inspect_pdf_sheet_set([source]), digest


def _marks(report):
    return {(row["page"], row["type_tag"]): row
            for row in report["detail_object_index"]["detail_candidates"]
            if row["kind"] == "EXPLICIT_TEXT_TYPE_MARK"}


def test_floor_preparation_b_does_not_create_a_beam_reference(tmp_path):
    doc = pymupdf.open()
    floor = _sheet(doc, "Floor Preparation Plan", [(41, 96, "B4")])
    floor.draw_rect(pymupdf.Rect(32, 85, 135, 148))
    detail = _sheet(doc, "Beam Detail B4")
    detail.draw_rect(pymupdf.Rect(34, 61, 145, 122))
    result, digest = _read(doc, tmp_path)
    marks = _marks(result)
    assert marks[1, "B4"]["family_candidates"] == ["architecture_finishes"]
    assert marks[2, "B4"]["family_candidates"] == ["beam"]
    assert result["detail_object_index"]["potential_same_document_type_references"] == []
    witness, = marks[1, "B4"]["source_word_witnesses"]
    assert witness["source_token"] == "B4" and witness["witness_id"].startswith("PDF001:p1:word")
    assert marks[1, "B4"]["source_pdf_sha256"] == digest
    assert marks[1, "B4"]["family_basis"] == "FLOOR_PREPARATION_MARK_CONTEXT"
    assert marks[1, "B4"]["financially_payable"] is False


def test_grade_beam_context_requires_the_plan_and_preserves_repeated_text(tmp_path):
    doc = pymupdf.open()
    _sheet(doc, "Excavation Plan", [(40, 92, "T-7"), (280, 123, "T-7")])
    _sheet(doc, "Foundation Plan", [(44, 90, "T-7")])
    _sheet(doc, "Reinforcement Plan", [(45, 95, "T-7")])
    result, _ = _read(doc, tmp_path)
    marks = _marks(result)
    assert [marks[p, "T7"]["family_candidates"] for p in (1, 2, 3)] == [["grade_beam"], ["grade_beam"], []]
    assert marks[1, "T7"]["family_basis"] == "FOUNDATION_PHASE_MARK_CONTEXT"
    assert len({w["witness_id"] for w in marks[1, "T7"]["source_word_witnesses"]}) == 2
    ref, = result["detail_object_index"]["potential_same_document_type_references"]
    assert ref["pages"] == [1, 2] and ref["physical_member_count"] is None
    assert result["operator_component_review"]["quantity_approval_count"] == 0
    assert any(row["candidate_family"] == "grade_beam" and row["page"] == 1
               for row in result["multidiscipline_gap_register"]["coverage_rows"])


def test_frame_and_title_words_are_kept_separate_from_two_detail_candidates(tmp_path):
    doc = pymupdf.open()
    page = _sheet(doc, "Beam Detail B4", [(284, 219, "Column Detail C3")])
    page.draw_rect(pymupdf.Rect(8, 8, 492, 411))
    page.draw_rect(pymupdf.Rect(43, 60, 102, 117))
    page.draw_rect(pymupdf.Rect(290, 245, 354, 302))
    result, digest = _read(doc, tmp_path)
    ledger = result["operator_component_review"]
    components = ledger["operator_components"]
    frame, = [x for x in components if x["stroke_topology_role"] == "FRAME_CANDIDATE"]
    assert frame["classification_status"] == "NON_MEMBER"
    assert frame["classification_reason"] == "PAGE_ENCLOSING_FRAME"
    candidates = [x for x in components if x["classification_status"] == "CLASSIFIED_CANDIDATE"]
    assert {tuple(x["classification_families"]) for x in candidates} == {("beam",), ("column",)}
    assert all(x["classification_title"]["source_token"] and x["source_pdf_sha256"] == digest for x in candidates)
    assert len({op for x in components for op in x["source_operator_ids"]}) == 3
    assert len(ledger["region_classifications"]) == 16
    assert all(row["financially_payable"] is False and row["physical_member_verified"] is False
               for row in [*components, *ledger["region_classifications"]])


def test_dimension_like_open_stroke_and_orthogonal_grid_do_not_inherit_detail(tmp_path):
    doc = pymupdf.open()
    page = _sheet(doc, "Beam Detail B4", [(40, 71, "350")])
    page.draw_line((38, 58), (142, 58))
    for x in (280, 308, 336):
        page.draw_line((x, 140), (x, 208))
    for y in (144, 174, 204):
        page.draw_line((269, y), (355, y))
    result, digest = _read(doc, tmp_path)
    ledger = result["operator_component_review"]
    open_line, = [x for x in ledger["operator_components"] if x["stroke_topology_role"] == "OPEN_CHAIN"]
    assert open_line["classification_reason"] == "OPEN_CHAIN_ROLE_REQUIRES_REVIEW"
    assert open_line["proposed_title_anchor_id"] is None
    grid, = [x for x in ledger["operator_components"] if x["stroke_topology_role"] == "TABLE_OR_PLAN_GRID"]
    assert grid["classification_reason"] == "TABLE_OR_GRID_CONTENT_REQUIRES_REVIEW"
    assert grid["source_pdf_sha256"] == digest
    assert all(row["classification_status"] != "CLASSIFIED_CANDIDATE" for row in ledger["operator_components"])


def test_unknown_title_with_ductile_text_does_not_infer_mep(tmp_path):
    doc = pymupdf.open()
    page = _sheet(doc, "Ductile detail for review")
    page.draw_rect(pymupdf.Rect(42, 57, 126, 133))
    result, _ = _read(doc, tmp_path)
    title, = [x for x in result["detail_object_index"]["detail_candidates"] if x["kind"] == "EXPLICIT_DETAIL_TITLE"]
    assert title["family_candidates"] == [] and title["status"] == "BLOCKED_UNKNOWN_DETAIL_FAMILY"
    assert not any(row["candidate_family"] == "mechanical"
                   for row in result["multidiscipline_gap_register"]["coverage_rows"])
    ledger = result["operator_component_review"]
    assert all(row["classification_status"] != "CLASSIFIED_CANDIDATE" for row in ledger["operator_components"])
    assert ledger["quantity_approval_count"] == 0


def test_repeated_type_on_separate_scales_keeps_distinct_candidates(tmp_path):
    doc = pymupdf.open()
    page = _sheet(doc, "Beam Detail B4", [(270, 210, "Beam Detail B4")])
    page.draw_rect(pymupdf.Rect(43, 60, 80, 101))
    page.draw_rect(pymupdf.Rect(275, 235, 429, 381))
    result, _ = _read(doc, tmp_path)
    rows = result["operator_component_review"]["operator_components"]
    assert len(rows) == 2
    assert all(row["classification_status"] == "CLASSIFIED_CANDIDATE" for row in rows)
    assert len({row["classification_title"]["source_id"] for row in rows}) == 2
    assert len({op for row in rows for op in row["source_operator_ids"]}) == 2
    mark = _marks(result)[1, "B4"]
    assert len(mark["source_word_witnesses"]) == 2
    assert all(row["physical_member_count"] is None and not row["financially_payable"] for row in rows)


@pytest.mark.parametrize("corrupt_source", [False, True])
def test_ocr_text_remains_witness_only_and_wrong_pdf_sha_is_rejected(tmp_path, monkeypatch, corrupt_source):
    from core.drawings import pdf_auto_intake

    def recognize(page, *, document_id, page_number, source_sha256, **kwargs):
        witness = {
            "document_id": document_id, "page": page_number, "source_word_index": 1,
            "witness_id": f"{document_id}:p{page_number}:ocrword000001",
            "source_sha256": "e" * 64 if corrupt_source else source_sha256,
            "status": "OCR_TYPE_MARK_UNVERIFIED", "source_quality": "RENDERED_OCR_NOT_VERIFIED",
            "bbox_pt": [43, 53, 53, 58], "raw_token": "B4", "type_tag": "B4",
            "financially_payable": False,
        }
        return {"status": "INDEXED_RENDERED_OCR_TYPE_CANDIDATES", "type_word_witness_count": 1,
                "all_ocr_words_examined": True, "type_word_witnesses": [witness]}

    monkeypatch.setattr(pdf_auto_intake, "recover_page_rendered_type_words", recognize)
    monkeypatch.setattr(pdf_auto_intake, "should_recover_rendered_labels", lambda _: True)
    doc = pymupdf.open()
    page = _sheet(doc, "Formwork Plan")
    page.draw_rect(pymupdf.Rect(42, 61, 109, 118))
    source = tmp_path / "synthetic_ocr.pdf"
    doc.save(source)
    doc.close()
    if corrupt_source:
        with pytest.raises(ValueError, match="Foreign.*text witness"):
            inspect_pdf_sheet_set([source], rendered_ocr=True)
        return
    result = inspect_pdf_sheet_set([source], rendered_ocr=True)
    ledger = result["operator_component_review"]
    word, = ledger["classification_text_witnesses"]
    assert word["method"] == "RENDERED_OCR" and word["source_pdf_sha256"] == sha256(source.read_bytes()).hexdigest()
    assert any(word["source_id"] in row["source_type_word_ids"] for row in ledger["region_classifications"])
    record, = ledger["operator_components"]
    assert record["classification_families"] == [] and record["classification_status"] == "AMBIGUOUS"
    assert record["physical_member_verified"] is False and record["financially_payable"] is False


def test_existing_qt_review_filters_source_dispositions_and_exposes_mark(tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from app.pdf_detail_graph_review import PDFDetailGraphReview

    qt = QApplication.instance() or QApplication([])
    doc = pymupdf.open()
    page = _sheet(doc, "Foundation Plan", [(45, 92, "T-7")])
    page.draw_rect(pymupdf.Rect(80, 76, 154, 128))
    result, digest = _read(doc, tmp_path)
    widget = PDFDetailGraphReview(result)
    try:
        key = "component_source_regions"
        widget.sections.setCurrentIndex(widget._section_keys.index(key))
        widget.filters[key].setText("مبهم")
        model = widget.tables[key].model()
        assert 0 < model.rowCount() < 16
        widget.tables[key].setCurrentIndex(model.index(0, 0))
        assert "تأیید مهندسی نشده" in widget.details.toPlainText()
        key = "component_text_candidates"
        widget.sections.setCurrentIndex(widget._section_keys.index(key))
        widget.filters[key].setText("grade_beam")
        model = widget.tables[key].model()
        assert model.rowCount() == 1
        selected = model.index(0, 0)
        assert not selected.flags() & Qt.ItemFlag.ItemIsEditable
        widget.tables[key].setCurrentIndex(selected)
        details = widget.details.toPlainText()
        assert all(text in details for text in ("T-7", "PDF001:p1:word", digest, "تأیید مهندسی نشده"))
    finally:
        widget.close()
        qt.processEvents()
