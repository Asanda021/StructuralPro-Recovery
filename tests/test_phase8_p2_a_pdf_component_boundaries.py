"""Synthetic PDF boundary and provenance regressions through production intake."""
from collections import Counter
from hashlib import sha256

import pytest

pymupdf = pytest.importorskip("pymupdf")

from core.drawings.pdf_auto_intake import inspect_pdf_sheet_set


def _page(pdf, text=None):
    page = pdf.new_page(width=500, height=420)
    if text:
        page.insert_text((41, 51), text)
    return page


def _save(pdf, tmp_path, name="synthetic"):
    saved = tmp_path / f"{name}.pdf"
    pdf.save(saved)
    pdf.close()
    return saved


def _report(tmp_path, draw, *, registered=False):
    pdf = pymupdf.open()
    draw(pdf)
    path = _save(pdf, tmp_path)
    digest = sha256(path.read_bytes()).hexdigest()
    register = _current_revision(digest) if registered else None
    return inspect_pdf_sheet_set([path], revision_registry=register), digest


def _ledger(report):
    return report["operator_component_review"]


def _assert_partition(report):
    review = _ledger(report)
    records = review["boundary_components"]
    exact = [operator["source_id"] for page in report["detail_evidence_graph"]["topology_pages"]
             for parent in page["groups"] for operator in parent["source_operators"]]
    apportioned = [ref for component in records for ref in component["source_operator_ids"]]
    assert sorted(apportioned) == sorted(exact) and len(set(apportioned)) == len(exact)
    assert all(row["physical_member_count"] is None and row["quantity_approval_count"] == 0
               and row["financially_payable"] is False
               for row in [*records, *review["component_source_links"]])
    assert report["quantity_approval_count"] == 0
    assert report["physical_member_count"] is None
    assert report["detail_evidence_graph"]["quantity_approval_count"] == 0
    return records


def test_crossing_grid_keeps_two_outlines_in_a_shared_paint_path(tmp_path):
    def draw(pdf):
        page = _page(pdf)
        shape = page.new_shape()
        shape.draw_rect((60, 80, 150, 160))
        shape.draw_rect((162, 80, 252, 160))
        shape.finish()
        shape.commit()
        page.draw_line((20, 115), (280, 115))

    report, digest = _report(tmp_path, draw)
    rows = _assert_partition(report)
    outlines = [x for x in rows if x["boundary_role"] == "CLOSED_OUTLINE"]
    assert len(outlines) == 2
    assert all(row["source_pdf_sha256"] == digest and len(row["source_operator_ids"]) == 1
               and row["source_paths"][0]["paint"] == "s" for row in outlines)
    assert {row["source_paths"][0]["path_index"] for row in outlines} == {1}
    assert all("SHARED_TOPOLOGY_PARENT" in row["relation_flags"] for row in outlines)
    assert all("SHARED_ROUGH_BBOX_GROUP" in row["relation_flags"] for row in outlines)
    assert all(row["classification_status"] == "AMBIGUOUS" for row in outlines)


def test_residual_strokes_split_after_their_connecting_outline_is_claimed(tmp_path):
    def draw(pdf):
        page = _page(pdf)
        page.draw_rect((100, 90, 170, 155))
        page.draw_line((60, 112), (100, 112))
        page.draw_line((170, 127), (211, 127))
        page.draw_line((194, 105), (194, 144))

    report, _ = _report(tmp_path, draw)
    rows = _assert_partition(report)
    parent, = report["detail_evidence_graph"]["topology_pages"][0]["groups"]
    by_operators = {tuple(row["source_operator_ids"]): row for row in rows}
    assert set(by_operators) == {
        ("PDF001:p1:d1:s1",),
        ("PDF001:p1:d2:s1",),
        ("PDF001:p1:d3:s1", "PDF001:p1:d4:s1"),
    }
    assert all(row["parent_component_ids"] == [parent["candidate_id"]] for row in rows)
    assert all(row["classification_status"] == "AMBIGUOUS" for row in rows)
    assert sorted((path["path_index"], path["paint"], path["paint_sequence"])
                  for row in rows for path in row["source_paths"]) == [
        (1, "s", 0), (2, "s", 1), (3, "s", 2), (4, "s", 3),
    ]


def test_explicit_page_frame_and_nested_local_frame_are_not_a_single_detail(tmp_path):
    def draw(pdf):
        p = _page(pdf)
        p.draw_rect((8, 8, 493, 412))
        p.draw_line((400, 412), (400, 380))
        p.draw_rect((49, 61, 351, 320))
        p.draw_rect((90, 100, 137, 150))
        p.draw_rect((205, 182, 262, 239))

    report, _ = _report(tmp_path, draw)
    rows = _assert_partition(report)
    frame, = [r for r in rows if r["boundary_role"] == "PAGE_FRAME"]
    nested, = [r for r in rows if r["boundary_role"] == "ENCLOSING_OUTLINE_REVIEW"]
    assert frame["classification_status"] == "NON_MEMBER" and frame["source_operator_ids"] == ["PDF001:p1:d1:s1"]
    assert nested["classification_status"] == "AMBIGUOUS"
    assert len([r for r in rows if r["boundary_role"] == "CLOSED_OUTLINE"]) == 2
    links = {r["component_id"]: r for r in _ledger(report)["component_source_links"]}
    assert links[frame["component_id"]]["status"] == "EXCLUDED_NON_MEMBER"


def test_repeated_paint_and_open_curve_and_quad_do_not_create_extra_outlines(tmp_path):
    def draw(pdf):
        p = _page(pdf)
        p.draw_rect((42, 63, 112, 123))
        p.draw_rect((42, 63, 112, 123))
        p.draw_line((230, 65), (340, 65))
        p.draw_bezier(pymupdf.Point(250, 119), pymupdf.Point(263, 160),
                      pymupdf.Point(293, 167), pymupdf.Point(304, 119))
        p.draw_quad(pymupdf.Quad(pymupdf.Point(340, 199), pymupdf.Point(410, 199),
                                 pymupdf.Point(410, 199), pymupdf.Point(340, 199)))

    report, _ = _report(tmp_path, draw)
    rows = _assert_partition(report)
    duplicate, = [r for r in rows if r["reason_code"] == "COINCIDENT_PAINT_OUTLINES"]
    assert duplicate["classification_status"] == "AMBIGUOUS" and len(duplicate["source_operator_ids"]) == 2
    quad, = [r for r in rows if r["boundary_role"] == "COLLAPSED_QUAD_STROKE"]
    assert quad["classification_status"] == "BLOCKED" and quad["outline_pt"] == []
    assert quad["source_operator_ids"] == ["PDF001:p1:d5:s1"]
    assert not [r for r in rows if r["classification_status"] == "CANDIDATE"]


@pytest.mark.parametrize("title,expected", [("Axis Plan", "NON_MEMBER"), (None, "AMBIGUOUS")])
def test_explicit_axis_sheet_and_source_grid_are_needed_for_grid_exclusion(tmp_path, title, expected):
    def draw(pdf):
        page = _page(pdf, title)
        for x in (100, 220, 345):
            page.draw_line((x, 90), (x, 318))
        for y in (95, 203, 314):
            page.draw_line((76, y), (380, y))

    report, digest = _report(tmp_path, draw)
    matching, = _assert_partition(report)
    assert matching["source_pdf_sha256"] == digest
    assert matching["classification_status"] == expected
    if expected == "NON_MEMBER":
        assert matching["boundary_role"] == "AXIS_GRID"
    else:
        assert matching["boundary_role"] == "ORTHOGONAL_NETWORK_REVIEW"
    assert len(matching["source_operator_ids"]) == 6


def _draw_typed_detail(page, *, repeated_title=False, repeated_outline=False, type_word=True,
                       scales=False, title_type="B4"):
    if repeated_title:
        page.insert_text((40, 68), "Beam Detail B5")
    page.draw_rect((40, 81, 83 if repeated_outline else 165, 142))
    if repeated_outline:
        page.draw_rect((88, 81, 165, 142))
    if type_word:
        page.insert_text((66, 115), title_type)
    if scales:
        page.insert_text((220, 80), "Scale 1:20")
        page.insert_text((220, 107), "Scale 1:50")
    else:
        page.insert_text((58, 155), "Scale 1:40")


def test_unique_local_type_title_has_operator_custody_without_approval(tmp_path):
    def draw(pdf):
        p = _page(pdf, "Beam Detail B4")
        _draw_typed_detail(p)

    report, digest = _report(tmp_path, draw, registered=True)
    _assert_partition(report)
    link, = [r for r in _ledger(report)["component_source_links"] if r["status"] == "PROPOSED"]
    assert link["source_pdf_sha256"] == digest and link["document_id"] == "PDF001" and link["page"] == 1
    assert link["component_id"].startswith("PDF001:p1:boundary")
    assert link["source_operator_ids"] == ["PDF001:p1:d1:s1"]
    assert link["type_tag"] == "B4" and link["type_source"]["method"] == "NATIVE_TYPE_WORD"
    assert link["title_anchor_id"] and len(link["title_bbox_pt"]) == 4
    assert link["type_source"]["source_id"] != link["title_type_source"]["source_id"]
    assert [w["printed"] for w in link["local_printed_scale_witnesses"]] == ["Scale 1:40"]
    assert link["scale_calibrated"] is link["independently_reviewed"] is False
    assert link["authority_status"] == "CURRENT" and len(link["scale_scope_bbox_pt"]) == 4
    assert link["span_specific_detail_verified"] is False and link["required_evidence"]


def test_stroked_accented_ring_can_be_ink_without_becoming_a_component(tmp_path):
    def draw(pdf):
        from math import cos, pi, sin

        page = _page(pdf)
        # Two loops with identical geometry. Only the first has independent
        # accent and aligned stem context in the original paint order.
        page.draw_polyline([(115, 125), (115, 132), (117, 134)], closePath=False)
        page.draw_polyline([(121, 123), (123, 122), (125, 123)], closePath=False)
        for center in (123, 289):
            points = [(center + 3.75 * cos(i * pi / 8), 130 + 5 * sin(i * pi / 8))
                      for i in range(16)]
            page.draw_polyline([*points, points[0]], closePath=False)
            if center == 123:
                page.draw_polyline([(129, 125), (132, 129), (135, 125)], closePath=False)
                page.draw_line((132, 129), (132, 135))

    report, _ = _report(tmp_path, draw)
    rows = _assert_partition(report)
    reviews = [r for r in rows if r["reason_code"] == "ACCENTED_STROKE_GLYPH_CONTEXT"]
    record, = reviews
    assert record["classification_status"] == "AMBIGUOUS"
    assert len(record["source_operator_ids"]) == len(record["outline_pt"]) == 16
    assert set(record["competing_context_operator_ids"]) == {
        "PDF001:p1:d2:s1", "PDF001:p1:d2:s2", "PDF001:p1:d4:s1",
        "PDF001:p1:d4:s2", "PDF001:p1:d5:s1",
    }
    assert any(r["classification_status"] == "CANDIDATE" and len(r["outline_pt"]) == 16 for r in rows)
    link, = [r for r in _ledger(report)["component_source_links"] if r["component_id"] == record["component_id"]]
    assert link["status"] == "BLOCKED"


@pytest.mark.parametrize("case, expected", [
    ("touching_pair", True), ("both_independent", False), ("wide_gap", False), ("different_height", False),
])
def test_adjacent_outline_keeps_operator_ownership_in_mixed_assembly(tmp_path, case, expected):
    def draw(pdf):
        p = _page(pdf)
        if case != "both_independent":
            p.draw_line((66, 90), (90, 90))
        p.draw_rect((90, 90, 104, 141))
        x = 132 if case == "wide_gap" else 109
        y = 149 if case == "different_height" else 141
        p.draw_rect((x, 90, x + 14, y))

    report, _ = _report(tmp_path, draw)
    rows = _assert_partition(report)
    peer = [r for r in rows if r["reason_code"] == "ADJACENT_CONTOUR_TOUCHES_MIXED_INK"]
    assert bool(peer) is expected
    if peer:
        candidate, = peer
        assert candidate["classification_status"] == "AMBIGUOUS"
        assert candidate["source_operator_ids"] == ["PDF001:p1:d3:s1"]
        assert candidate["competing_context_operator_ids"] == ["PDF001:p1:d2:s1"]
        assert candidate["competing_context_bbox_pt"] == [90, 90, 123, 141]
        other, = [r for r in rows if r["source_operator_ids"] == ["PDF001:p1:d2:s1"]]
        assert other["reason_code"] == "OUTLINE_TOUCHES_OTHER_SOURCE_INK"


def _current_revision(digest):
    return {"schema_version": 1, "documents": [{
        "sha256": digest, "project_id": "SYNTHETIC", "issue_id": "TEST-ISSUE",
        "revision": "R1", "status": "CURRENT", "authority_reference": "Test issue register",
    }]}


@pytest.mark.parametrize("case, reason", [
    ("unregistered", "LOCAL_DETAIL_REVISION_UNVERIFIED"),
    ("foreign", "registry SHA does not match"),
    ("unbound_scale", "SCALE_PRINT_OUTSIDE_LOCAL_VIEW"),
])
def test_proposal_rejects_unbound_revision_and_scale(tmp_path, case, reason):
    doc = pymupdf.open()
    p = _page(doc, "Beam Detail B4")
    p.insert_text((240, 55), "REV R1")
    p.draw_rect((40, 81, 165, 142))
    p.insert_text((66, 115), "B4")
    p.insert_text((145 if case == "unbound_scale" else 58, 155), "Scale 1:40")
    path = _save(doc, tmp_path)
    options = {} if case == "unregistered" else {
        "revision_registry": _current_revision("a" * 64 if case == "foreign" else sha256(path.read_bytes()).hexdigest())
    }
    if case == "foreign":
        with pytest.raises(ValueError, match=reason):
            inspect_pdf_sheet_set([path], **options)
        return
    report = inspect_pdf_sheet_set([path], **options)
    _assert_partition(report)
    row, = _ledger(report)["component_source_links"]
    assert row["status"] in {"BLOCKED", "UNRESOLVED"}
    assert row["reason_code"] == reason
    assert row["type_tag"] == "B4"


@pytest.mark.parametrize("case,reason", [
    ("only_nearby", "NO_INDEPENDENT_TYPE_INSIDE_OUTLINE"),
    ("two_titles", "MULTIPLE_LOCAL_DETAIL_TITLES"),
    ("two_outlines", "TITLE_NEAR_MULTIPLE_OUTLINES"),
    ("other_page", "SAME_TYPE_ON_OTHER_SHEET"),
    ("scales", "MULTIPLE_SCALE_SCOPES"),
])
def test_uncertain_identity_never_chooses_nearest_title(tmp_path, case, reason):
    def draw(pdf):
        p = _page(pdf, "Beam Detail B4")
        _draw_typed_detail(p, repeated_title=case == "two_titles", repeated_outline=case == "two_outlines",
                           type_word=case != "only_nearby", scales=case == "scales")
        if case == "other_page":
            p = _page(pdf, "Beam Detail B4")
            _draw_typed_detail(p)

    report, _ = _report(tmp_path, draw)
    links = _ledger(report)["component_source_links"]
    assert not [r for r in links if r["status"] == "PROPOSED"]
    assert any(r["reason_code"] == reason and r["status"] in {"BLOCKED", "UNRESOLVED"} for r in links)
    _assert_partition(report)


def test_same_name_from_multiple_documents_cannot_supply_local_binding(tmp_path):
    paths = []
    for index in range(2):
        doc = pymupdf.open()
        p = _page(doc, "Beam Detail B4")
        _draw_typed_detail(p)
        p.insert_text((250, 400), f"Synthetic document {index}")
        paths.append(_save(doc, tmp_path, f"one-{index}"))

    report = inspect_pdf_sheet_set(paths)
    rows = _ledger(report)["component_source_links"]
    assert len({r["source_pdf_sha256"] for r in rows}) == 2
    assert all(r["reason_code"] == "SAME_TYPE_IN_OTHER_DOCUMENT" and r["status"] == "BLOCKED" for r in rows)
    _assert_partition(report)
    with pytest.raises(ValueError, match="Duplicate PDF source selection"):
        inspect_pdf_sheet_set([paths[0], paths[0]])
    duplicate = tmp_path / "duplicate-bytes.pdf"
    duplicate.write_bytes(paths[0].read_bytes())
    with pytest.raises(ValueError, match="Duplicate PDF source identity"):
        inspect_pdf_sheet_set([paths[0], duplicate])


def test_outline_inside_intersecting_table_strokes_cannot_claim_its_title(tmp_path):
    def draw(pdf):
        p = _page(pdf, "Beam Detail B4")
        for x in (30, 149, 245):
            p.draw_line((x, 74), (x, 228))
        for y in (78, 153, 224):
            p.draw_line((25, y), (251, y))
        p.draw_rect((43, 89, 120, 136))
        p.insert_text((65, 112), "B4")

    report, _ = _report(tmp_path, draw)
    records = _assert_partition(report)
    island, = [r for r in records if r["boundary_role"] == "CLOSED_OUTLINE"]
    assert island["classification_status"] == "AMBIGUOUS"
    assert island["reason_code"] == "OUTLINE_WITHIN_ORTHOGONAL_NETWORK"
    link, = [r for r in _ledger(report)["component_source_links"] if r["component_id"] == island["component_id"]]
    assert link["status"] == "BLOCKED" and link["local_type_witnesses"]


def test_budget_block_retains_all_known_operator_refs_and_paint_order(tmp_path):
    from core.drawings.pdf_component_boundaries import build_pdf_component_boundary_page
    from core.drawings.pdf_sheet_detail_inventory import inventory_pdf_page_regions

    pdf = pymupdf.open()
    page = _page(pdf)
    page.draw_rect((42, 70, 310, 300))
    page.draw_rect((61, 90, 95, 116))
    page.draw_rect((165, 151, 218, 220))
    summary = inventory_pdf_page_regions(page, document_id="PDF001", page_number=1, include_topology=True)
    records, receipt = build_pdf_component_boundary_page(
        summary["detail_topology"], document_id="PDF001", page=1, digest="a" * 64, sheet_kind=None,
        path_groups={}, paint_sequences=summary["source_paint_sequences"], max_enclosure_checks=1,
    )
    assert receipt["status"] == "BLOCKED" and receipt["reason_code"] == "BLOCKED_BOUNDARY_COMPARISON_BUDGET"
    assert receipt["unaccounted_operator_count"] == 0 and receipt["accounted_operator_count"] == 3
    assert all(r["classification_status"] == "BLOCKED" and not r["outline_pt"] for r in records)
    assert {i for r in records for i in r["source_operator_ids"]} == {f"PDF001:p1:d{i}:s1" for i in (1, 2, 3)}
    assert all(type(s["paint_sequence"]) is int for r in records for s in r["source_paths"])
    pdf.close()


def test_residual_connectivity_budget_blocks_without_losing_operator_custody():
    from core.drawings.pdf_component_boundaries import build_pdf_component_boundary_page
    from core.drawings.pdf_sheet_detail_inventory import inventory_pdf_page_regions

    with pymupdf.open() as pdf:
        page = _page(pdf)
        page.draw_rect((100, 90, 170, 155))
        page.draw_line((170, 127), (211, 127))
        page.draw_line((194, 105), (194, 144))
        page.draw_line((201, 105), (201, 144))
        summary = inventory_pdf_page_regions(page, document_id="PDF001", page_number=1, include_topology=True)

    records, receipt = build_pdf_component_boundary_page(
        summary["detail_topology"], document_id="PDF001", page=1, digest="a" * 64, sheet_kind=None,
        path_groups={}, paint_sequences=summary["source_paint_sequences"], max_enclosure_checks=1,
    )
    assert receipt["status"] == "BLOCKED"
    assert receipt["reason_code"] == "BLOCKED_RESIDUAL_CONNECTIVITY_BUDGET"
    assert receipt["unaccounted_operator_count"] == 0
    record, = records
    assert record["classification_status"] == "BLOCKED"
    assert record["source_operator_ids"] == [f"PDF001:p1:d{i}:s1" for i in range(1, 5)]
    assert [path["paint_sequence"] for path in record["source_paths"]] == [0, 1, 2, 3]


@pytest.mark.parametrize("wrong_sha", [False, True])
def test_contested_ocr_never_recovers_the_type_automatically(tmp_path, monkeypatch, wrong_sha):
    from core.drawings import pdf_auto_intake

    def recognize(page, *, document_id, page_number, source_sha256, **kwargs):
        return {"status": "INDEXED_RENDERED_OCR_TYPE_CANDIDATES", "type_word_witness_count": 1,
                "all_ocr_words_examined": True, "ambiguous_glyph_count": 1, "type_word_witnesses": [{
                    "document_id": document_id, "page": page_number, "source_word_index": 1,
                    "source_sha256": "f" * 64 if wrong_sha else source_sha256,
                    "status": "AMBIGUOUS_GLYPH", "source_quality": "RENDERED_OCR_NOT_VERIFIED",
                    "bbox_pt": [93, 108, 104, 123], "source_token": "B4", "type_tag": None,
                    "glyph_interpretations": ["B4", "84"], "financially_payable": False,
                }]}

    monkeypatch.setattr(pdf_auto_intake, "should_recover_rendered_labels", lambda _: True)
    monkeypatch.setattr(pdf_auto_intake, "recover_page_rendered_type_words", recognize)
    pdf = pymupdf.open()
    p = _page(pdf, "Beam Detail B4")
    _draw_typed_detail(p)
    path = _save(pdf, tmp_path, "synthetic-ocr")
    if wrong_sha:
        with pytest.raises(ValueError, match="Foreign.*text witness"):
            inspect_pdf_sheet_set([path], rendered_ocr=True)
        return
    report = inspect_pdf_sheet_set([path], rendered_ocr=True)
    link, = _ledger(report)["component_source_links"]
    assert link["status"] == "BLOCKED" and link["reason_code"] == "AMBIGUOUS_GLYPH_IN_OUTLINE"
    assert any(w["glyph_interpretations"] == ["B4", "84"] for w in link["local_type_witnesses"])
    assert link["type_source"] is None
    _assert_partition(report)


def test_qt_filter_readonly_source_link_and_boundary_records(tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from app.pdf_detail_graph_review import PDFDetailGraphReview

    def draw(pdf):
        p = _page(pdf, "Beam Detail B4")
        p.draw_rect((8, 8, 493, 412))
        _draw_typed_detail(p)

    app = QApplication.instance() or QApplication([])
    report, digest = _report(tmp_path, draw, registered=True)
    widget = PDFDetailGraphReview(report)
    try:
        key = "boundary_components"
        widget.sections.setCurrentIndex(widget._section_keys.index(key))
        widget.filters[key].setText("غیرعضو")
        assert widget.tables[key].model().rowCount() == 1
        key = "component_source_links"
        widget.sections.setCurrentIndex(widget._section_keys.index(key))
        widget.filters[key].setText("PROPOSED")
        table = widget.tables[key]
        assert table.model().rowCount() == 1
        index = table.model().index(0, 0)
        assert not index.flags() & Qt.ItemFlag.ItemIsEditable
        table.setCurrentIndex(index)
        details = widget.details.toPlainText()
        assert all(value in details for value in (
            digest, "PDF001:p1:d2:s1", "B4", "NATIVE_TYPE_WORD", "تأیید مهندسی نشده",
        ))
        _assert_partition(report)
    finally:
        widget.close()
        app.processEvents()


# Generic stroke fixture. Coordinates and caption are synthetic.
_PLATE_LETTERING = {
    "P": (((0, 1), (0, 0), (.75, 0), (1, .16), (1, .34), (.75, .5), (0, .5)),),
    "L": (((0, 0), (0, 1), (1, 1)),),
    "0": (((.3, 1), (0, .83), (0, .17), (.3, 0), (.7, 0), (1, .17),
           (1, .83), (.7, 1), (.3, 1)),),
    "1": (((0, .17), (1, 0), (1, 1)),),
    "2": (((0, .17), (.25, 0), (.75, 0), (1, .17), (1, .34), (.75, .5),
           (.25, .5), (0, .67), (0, 1), (1, 1)),),
    "X": (((0, 1), (1, 0)), ((0, 0), (1, 1))),
}


@pytest.mark.parametrize("case,excludes_label", [
    ("complete", True), ("crossed", False), ("lacks_plate_prefix", False),
    ("quarter_turn", False), ("incomplete", False), ("extra_ending_digit", True),
])
def test_plate_lettering_cannot_be_mistaken_for_an_outline(tmp_path, case, excludes_label):
    def draw(pdf):
        p = _page(pdf)
        # A real closed box is still a separate outline.
        p.draw_rect((47, 83, 136, 137))
        token = {"lacks_plate_prefix": "20X20X1", "incomplete": "PL20X20",
                 "extra_ending_digit": "PL20X20X12"}.get(case, "PL20X20X1")
        at = 160
        for char in token:
            w = {"0": 5, "1": 2}.get(char, 7)
            shape = p.new_shape()
            for chain in _PLATE_LETTERING[char]:
                points = [(at + x * w, 160 + y * 10) for x, y in chain]
                if case == "quarter_turn":
                    points = [(460 - y, x - 120) for x, y in points]
                shape.draw_polyline(points)
            shape.finish(closePath=False)
            shape.commit()
            at += w + (12 if char == "L" else 3)
        if case == "crossed":
            p.draw_line((176, 164), (258, 164))

    report, _ = _report(tmp_path, draw)
    rows = _assert_partition(report)
    lettering = [r for r in rows if r["reason_code"] == "SOURCE_STROKES_OF_PLATE_ANNOTATION"]
    assert bool(lettering) == excludes_label
    assert any(r["boundary_role"] == "CLOSED_OUTLINE" and len(r["source_operator_ids"]) == 1 for r in rows)
    if lettering:
        label, = lettering
        assert label["boundary_role"] == "CAD_TEXT"
        assert label["classification_status"] == "NON_MEMBER"
        assert label["role_witness"]["normalized_text"] == ("PL20X20X12" if case == "extra_ending_digit"
                                                            else "PL20X20X1")
        assert label["role_witness"]["source_operator_ids"] == label["source_operator_ids"]
        assert len(label["source_operator_ids"]) >= 40
        assert not any(r["status"] == "PROPOSED" for r in _ledger(report)["component_source_links"])


@pytest.mark.parametrize("case,reason", [
    ("no_scale", "NO_APPLICABLE_LOCAL_SCALE"),
    ("distant_scale", "NO_APPLICABLE_LOCAL_SCALE"),
    ("two_local_scales", "MULTIPLE_LOCAL_SCALE_WITNESSES"),
    ("revision_conflict", "REVISION_CONFLICT"),
])
def test_local_boundary_link_requires_one_applicable_scale_and_consistent_revision(tmp_path, case, reason):
    def draw(pdf):
        p = _page(pdf, "Beam Detail B4")
        p.draw_rect((40, 81, 165, 142))
        p.insert_text((66, 115), "B4")
        if case == "distant_scale":
            p.insert_text((300, 350), "Scale 1:40")
        if case == "two_local_scales":
            p.insert_text((61, 154), "Scale 1:40")
            p.insert_text((69, 170), "Scale 1:40")
        if case == "revision_conflict":
            p.insert_text((61, 154), "Scale 1:40")
            p.insert_text((255, 151), "Rev A")
            p.insert_text((255, 171), "Rev B")

    report, _ = _report(tmp_path, draw)
    _assert_partition(report)
    row, = _ledger(report)["component_source_links"]
    assert row["status"] in {"BLOCKED", "UNRESOLVED"}
    assert row["reason_code"] == reason


@pytest.mark.parametrize("rotation", [0, 90])
def test_qt_source_crop_is_bound_to_selected_pdf_bytes(tmp_path, monkeypatch, rotation):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QLabel, QMessageBox
    from app.pdf_detail_graph_review import PDFDetailGraphReview

    app = QApplication.instance() or QApplication([])
    doc = pymupdf.open()
    page = _page(doc)
    page.draw_rect((57, 85, 143, 136), width=2.5)
    page.set_rotation(rotation)
    path = _save(doc, tmp_path, "synthetic-image")
    review = PDFDetailGraphReview(inspect_pdf_sheet_set([path]), source_paths={"PDF001": path})
    try:
        key = "boundary_components"
        review.sections.setCurrentIndex(review._section_keys.index(key))
        view = review.tables[key]
        view.setCurrentIndex(view.model().index(0, 0))
        assert review.component_image_button.isEnabled()
        review.component_image_button.click()
        label = review.findChild(QLabel, "PDFComponentCropImage")
        assert label and not label.pixmap().isNull()
        image = label.pixmap().toImage()
        assert all(dim < 1000 for dim in (image.width(), image.height()))
        assert any(image.pixelColor(x, y).lightness() < 180
                   for x in range(0, image.width(), 5) for y in range(0, image.height(), 5))
        warnings = []
        monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))
        path.write_bytes(b"changed")
        review.component_image_button.click()
        assert warnings and review.findChild(QLabel, "PDFComponentCropImage") is None
    finally:
        review.close()
        app.processEvents()
