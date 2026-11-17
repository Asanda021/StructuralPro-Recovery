"""Synthetic source-operator losslessness: no private CAD/PDF drawing in Git."""
import pytest

pymupdf = pytest.importorskip("pymupdf")
from core.drawings.pdf_auto_intake import inspect_pdf_sheet_set
from core.drawings.pdf_detail_topology import scan_detail_topology


def _draw_quad(page, coords):
    page.draw_quad(pymupdf.Quad(*[pymupdf.Point(x, y) for x, y in coords]))


def _two_point_quad(a=(50, 100), b=(130, 100)):
    return a, b, b, a


def test_degenerate_quad_preserves_four_corners_but_only_one_topology_stroke():
    doc = pymupdf.open()
    page = doc.new_page(width=350, height=280)
    _draw_quad(page, _two_point_quad())
    result = scan_detail_topology(page, document_id="PDF001", page_number=1)
    assert result["source_path_count"] == result["source_operator_count"] == 1
    assert result["source_operators_accounted_for"] is True
    assert result["source_degenerate_operator_count"] == 1
    assert result["source_degenerate_operator_ids"] == ["PDF001:p1:d1:s1"]
    assert result["status"] == "UNRESOLVED"
    assert result["reason_code"] == "DEGENERATE_QUAD_STROKES_ACCOUNTED_FOR"
    assert result["unresolved_operators"] == []
    assert result["group_count"] == 1
    group = result["groups"][0]
    assert group["role"] == "DEGENERATE_QUAD_STROKE_REVIEW_ONLY"
    op = group["source_operators"][0]
    assert len(group["source_operators"]) == 1
    assert op["source_quad_corners_pt"] == [
        [50.0, 100.0], [130.0, 100.0], [130.0, 100.0], [50.0, 100.0]
    ]
    assert op["points_pt"] == [[50.0, 100.0], [130.0, 100.0]]
    assert op["geometry_quality"] == "DEGENERATE_QUAD_STROKE_REVIEW_ONLY"
    assert not group["detail_boundary_verified"]
    assert not group["physical_member_verified"]
    assert not group["financially_payable"]
    doc.close()


def test_two_page_intake_keeps_collapsed_quad_as_review_only(tmp_path):
    doc = pymupdf.open()
    p = doc.new_page(width=350, height=280)
    p.insert_text((40, 30), "Beam Detail B1")
    p.draw_rect(pymupdf.Rect(55, 70, 125, 155))
    p = doc.new_page(width=350, height=280)
    p.insert_text((40, 30), "Beam Detail B2")
    _draw_quad(p, _two_point_quad((50, 110), (130, 110)))
    _draw_quad(p, _two_point_quad((175, 80), (175, 160)))
    source = tmp_path / "synthetic_geometry.pdf"
    doc.save(source)
    doc.close()
    result = inspect_pdf_sheet_set([source])
    review = result["operator_component_review"]
    tops = result["detail_evidence_graph"]["topology_pages"]
    assert len(tops) == 2
    assert all(p["source_operators_accounted_for"] for p in tops)
    assert [p["source_degenerate_operator_count"] for p in tops] == [0, 2]
    assert all(p["status"] != "BLOCKED" for p in tops)
    assert review["all_source_pages_accounted_for"]
    assert all(p["geometry_coverage_verified"] for p in review["page_reviews"])
    assert review["page_reviews"][1]["status"] == (
        "REVIEW_OPEN_DEGENERATE_QUAD_OPERATORS_ACCOUNTED_FOR"
    )
    assert review["page_reviews"][1]["source_degenerate_operator_count"] == 2
    assert review["quantity_approval_count"] == 0
    assert review["physical_member_count"] is None
    assert all(row["proposed_title_anchor_id"] is None
               for row in review["operator_components"]
               if row["stroke_topology_role"] == "DEGENERATE_QUAD_STROKE_REVIEW_ONLY")
    assert all(not row["financially_payable"] for row in review["operator_components"])


@pytest.mark.parametrize("coords", [
    ((10, 10), (40, 10), (40, 20), (10, 10)),
    ((10, 10), (10, 10), (10, 10), (10, 10)),
    ((10, 10), (40, 10), (40, 10), (40, 10)),
])
def test_ambiguous_or_zero_length_quad_must_stay_blocked(coords):
    doc = pymupdf.open()
    page = doc.new_page(width=350, height=280)
    _draw_quad(page, coords)
    # Some PyMuPDF builds normalize a 3:1 Quad to two line operators.
    # Supply the raw Quad source as a controlled negative fixture instead.
    paths = None
    if coords == ((10, 10), (40, 10), (40, 10), (40, 10)):
        quad = pymupdf.Quad(*[pymupdf.Point(x, y) for x, y in coords])
        paths = [{"items": [("qu", quad)], "type": "s"}]
    result = scan_detail_topology(page, document_id="PDF001", page_number=1, paths=paths)
    assert result["status"] == "BLOCKED"
    assert result["reason_code"] == "BLOCKED_UNSUPPORTED_VECTOR_OPERATORS"
    assert result["source_operators_accounted_for"] is False
    assert result["source_operator_count"] == 1
    assert len(result["unresolved_operators"]) == 1
    assert result["unresolved_operators"][0]["source_id"] == "PDF001:p1:d1:s1"
    assert result["source_degenerate_operator_count"] == 0
    assert result["physical_member_count"] is None
    assert result["financially_payable"] is False
    doc.close()


def test_four_corner_quad_remains_an_original_closed_contour():
    doc = pymupdf.open()
    page = doc.new_page(width=350, height=280)
    _draw_quad(page, ((20, 30), (100, 30), (20, 90), (100, 90)))
    result = scan_detail_topology(page, document_id="PDF001", page_number=1)
    assert result["source_degenerate_operator_count"] == 0
    assert result["source_operators_accounted_for"] is True
    assert result["group_count"] == 1
    assert result["groups"][0]["role"] == "CLOSED_CONTOUR"
    assert result["groups"][0]["source_operators"][0]["source_quad_corners_pt"] is None
    doc.close()
