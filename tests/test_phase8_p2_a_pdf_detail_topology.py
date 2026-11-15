"""Synthetic vector stroke topology with an independent set of expected anchors."""
import pymupdf as fitz
import pytest

from core.drawings.pdf_detail_topology import scan_detail_topology


def _scan(page, **kwargs):
    return scan_detail_topology(page, document_id="source-A", page_number=page.number + 1, **kwargs)


def _owners(report):
    return {
        (item["path_index"], item["operator_index"]): group
        for group in report["groups"] for item in group["source_operators"]
    }


def test_frame_and_overlapping_envelopes_preserve_three_independent_contours():
    with fitz.open() as doc:
        page = doc.new_page(width=300, height=200)
        page.draw_rect((5, 5, 295, 195))
        page.draw_rect((20, 20, 100, 104))
        page.draw_rect((40, 45, 65, 75))
        page.draw_quad(fitz.Quad((120, 35), (160, 24), (128, 73), (166, 63)))
        report = _scan(page)
    groups = _owners(report)
    assert report["status"] == "UNRESOLVED"
    assert sorted(groups) == [(1, 1), (2, 1), (3, 1), (4, 1)]
    assert groups[(1, 1)]["role"] == "FRAME_CANDIDATE"
    assert all(groups[(n, 1)]["role"] == "CLOSED_CONTOUR" for n in (2, 3, 4))
    assert len({group["candidate_id"] for group in groups.values()}) == 4
    assert groups[(2, 1)]["bbox_pt"] == [20, 20, 100, 104]
    assert report["physical_member_count"] is None
    assert report["quantity_approval_count"] == 0


def test_real_endpoint_chain_and_adjacent_disconnected_strokes():
    with fitz.open() as doc:
        page = doc.new_page(width=200, height=160)
        page.draw_line((15, 15), (45, 15))
        page.draw_line((45, 15), (44, 45))
        page.draw_line((44, 45), (15, 15))
        shape = page.new_shape()
        shape.draw_line((74, 32), (87, 38))
        shape.draw_line((87.04, 38.04), (96, 50))
        shape.finish(closePath=False)
        shape.commit()
        report = _scan(page)
    groups = _owners(report)
    assert len(groups) == 5
    triangle = groups[(1, 1)]
    assert triangle["role"] == "CLOSED_CONTOUR"
    assert triangle["source_path_indices"] == [1, 2, 3]
    assert groups[(4, 1)]["role"] == groups[(4, 2)]["role"] == "OPEN_CHAIN"
    assert groups[(4, 1)]["candidate_id"] != groups[(4, 2)]["candidate_id"]
    assert report["source_operators_accounted_for"]


def test_internal_frame_enclosing_disconnected_shapes_keeps_scope_unresolved():
    with fitz.open() as doc:
        page = doc.new_page(width=400, height=320)
        page.draw_rect((30, 30, 310, 230))
        page.draw_rect((50, 50, 105, 115))
        page.draw_rect((130, 130, 170, 178))
        report = _scan(page)
    groups = _owners(report)
    enclosure = groups[(1, 1)]
    assert enclosure["role"] == "ENCLOSING_CONTOUR_CANDIDATE"
    assert enclosure["enclosed_contour_candidate_ids"] == [
        groups[(2, 1)]["candidate_id"], groups[(3, 1)]["candidate_id"],
    ]
    assert groups[(2, 1)]["role"] == groups[(3, 1)]["role"] == "CLOSED_CONTOUR"
    assert enclosure["detail_boundary_verified"] is False


def test_grid_and_repeated_parallel_ink_have_no_section_contour():
    with fitz.open() as doc:
        page = doc.new_page(width=300, height=250)
        page.draw_rect((15, 25, 105, 115))
        page.draw_line((15, 60), (105, 60))
        page.draw_line((50, 25), (50, 115))
        page.draw_rect((185, 35, 220, 70))
        shape = page.new_shape()
        for x in [130, 135, 140]:
            shape.draw_line((x, 120), (x + 25, 145))
        shape.finish(closePath=False)
        shape.commit()
        report = _scan(page)
    groups = _owners(report)
    assert groups[(1, 1)]["role"] == "TABLE_OR_PLAN_GRID"
    assert groups[(1, 1)]["candidate_id"] == groups[(2, 1)]["candidate_id"] == groups[(3, 1)]["candidate_id"]
    assert groups[(4, 1)]["role"] == "CLOSED_CONTOUR"
    assert all(groups[(5, n)]["role"] == "PARALLEL_STROKES" for n in (1, 2, 3))
    assert all(group["detail_boundary_verified"] is False for group in report["groups"])


def test_rotated_page_keeps_cubic_controls_in_unrotated_pdf_space():
    with fitz.open() as doc:
        page = doc.new_page(width=240, height=180)
        page.draw_bezier((50, 40), (15, 35), (15, 45), (50, 40))
        page.set_rotation(90)
        report = _scan(page)
    group, = report["groups"]
    assert report["coordinate_space"] == "unrotated_pdf_points"
    assert report["rotation"] == 90
    assert report["page_bbox_pt"] == [0, 0, 240, 180]
    assert group["role"] == "CURVED_ENDPOINT_CYCLE"
    assert group["bbox_pt"] == [15, 35, 50, 45]
    assert group["source_operators"][0]["points_pt"] == [[50, 40], [15, 35], [15, 45], [50, 40]]


def test_unsupported_or_corrupt_geometry_and_path_budgets_are_explicit():
    with fitz.open() as doc:
        page = doc.new_page(width=200, height=160)
        page.draw_rect((20, 25, 85, 110))
        paths = page.get_drawings()
        failed = _scan(page, paths=[*paths, {"items": [("unsupported",)]}])
        budget = _scan(page, max_pair_checks=1)
        excessive = _scan(page, paths=[*paths, *paths], max_paths=1)
    assert failed["status"] == "BLOCKED"
    assert failed["reason_code"] == "BLOCKED_UNSUPPORTED_VECTOR_OPERATORS"
    assert failed["source_path_count"] == failed["source_operator_count"] == 2
    assert failed["source_operators_accounted_for"]
    bad, = failed["unresolved_operators"]
    assert (bad["path_index"], bad["operator_index"]) == (2, 1)
    assert all(group["status"] == "BLOCKED" for group in failed["groups"])
    assert budget["reason_code"] == "BLOCKED_VECTOR_TOPOLOGY_PAIR_BUDGET"
    assert excessive["reason_code"] == "BLOCKED_VECTOR_TOPOLOGY_PATH_BUDGET"
    assert budget["groups"] == excessive["groups"] == []
    assert not budget["source_operators_accounted_for"]


def test_wrong_page_anchor_and_invalid_extraction_have_no_group():
    with fitz.open() as doc:
        page = doc.new_page(width=180, height=120)
        page.draw_rect((15, 15, 100, 80))
        with pytest.raises(ValueError, match="page identity"):
            scan_detail_topology(page, document_id="source-A", page_number=2)
        report = _scan(page, source_blocked=True)
    assert report["reason_code"] == "BLOCKED_SOURCE_EVIDENCE_INCOMPLETE"
    assert report["source_path_count"] == 1
    assert report["groups"] == []
