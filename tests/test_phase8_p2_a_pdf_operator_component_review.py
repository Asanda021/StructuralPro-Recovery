"""Source-bound operator connectivity and plan/detail name-only review tests."""
from copy import deepcopy

import pytest

pymupdf = pytest.importorskip("pymupdf")

from core.drawings.pdf_auto_intake import inspect_pdf_sheet_set
from core.drawings.pdf_operator_component_review import build_pdf_operator_component_review


def _source(tmp_path, *, mode="two_details"):
    pdf = pymupdf.open()
    if mode == "two_details":
        p = pdf.new_page(width=500, height=400)
        p.insert_text((35, 50), "Beam Detail B1")
        p.draw_rect(pymupdf.Rect(40, 80, 100, 140))
        p.insert_text((280, 223), "Column Detail C2")
        p.draw_rect(pymupdf.Rect(285, 250, 348, 320))
    elif mode == "one_path_two_operators":
        p = pdf.new_page(width=500, height=400)
        p.insert_text((35, 50), "Beam Detail B1")
        shape = p.new_shape()
        shape.draw_rect(pymupdf.Rect(40, 80, 100, 140))
        shape.draw_rect(pymupdf.Rect(140, 80, 200, 140))
        shape.finish()
        shape.commit()
    elif mode == "frame":
        p = pdf.new_page(width=500, height=400)
        p.insert_text((40, 50), "Beam Detail B1")
        p.draw_rect(pymupdf.Rect(5, 5, 495, 395))
    elif mode == "plan_detail":
        p = pdf.new_page(width=500, height=400)
        p.insert_text((30, 28), "Beam Layout Plan")
        p.insert_text((110, 100), "B1")
        p.draw_line((100, 125), (400, 125))
        p = pdf.new_page(width=500, height=400)
        p.insert_text((40, 50), "Beam Detail B1")
        p.draw_rect(pymupdf.Rect(40, 82, 125, 160))
    else:
        raise AssertionError(mode)
    path = tmp_path / (mode + ".pdf")
    pdf.save(path)
    pdf.close()
    return path


def _inspect(tmp_path, mode):
    return inspect_pdf_sheet_set([_source(tmp_path, mode=mode)])


def test_two_disconnected_details_keep_distinct_operator_groups_and_titles(tmp_path):
    report = _inspect(tmp_path, "two_details")
    result = report["operator_component_review"]
    assert result["page_count"] == 1
    assert result["all_source_pages_accounted_for"]
    assert result["operator_component_review_count"] == 2
    rows = result["operator_components"]
    assert len({r["component_id"] for r in rows}) == 2
    assert len({r["proposed_title_anchor_id"] for r in rows}) == 2
    assert all(r["status"] == "PROPOSED_SINGLE_OPERATOR_COMPONENT_NEAR_UNIQUE_TITLE"
               for r in rows)
    assert all(r["detail_boundary_verified"] is False and
               r["span_specific_detail_verified"] is False and
               r["physical_member_verified"] is False and
               r["financially_payable"] is False for r in rows)
    assert result["physical_member_count"] is None
    assert result["quantity_approval_count"] == 0


def test_one_pdf_path_with_two_separate_contours_vetoes_bbox_only_join(tmp_path):
    report = _inspect(tmp_path, "one_path_two_operators")
    result = report["operator_component_review"]
    checks = result["page_reviews"]
    assert checks[0]["geometry_coverage_verified"] is True
    assert checks[0]["operator_component_count"] == 2
    assert checks[0]["bbox_group_count"] == 1
    assert all(r["status"] == "BLOCKED_BBOX_GROUP_AND_OPERATOR_COMPONENT_DISAGREE"
               and r["proposed_title_anchor_id"] is None
               for r in result["operator_components"])


def test_very_large_sheet_frame_cannot_be_called_detail_boundary(tmp_path):
    report = _inspect(tmp_path, "frame")
    rows = report["operator_component_review"]["operator_components"]
    assert rows
    assert all(r["status"] != "PROPOSED_SINGLE_OPERATOR_COMPONENT_NEAR_UNIQUE_TITLE"
               and r["detail_boundary_verified"] is False for r in rows)


def test_cross_sheet_same_type_name_remains_nonauthoritative(tmp_path):
    report = _inspect(tmp_path, "plan_detail")
    ledger = report["operator_component_review"]
    refs = ledger["plan_detail_type_only_references"]
    assert refs
    assert all(r["plan_document_id"] == "PDF001" and
               r["plan_page"] == 1 and r["printed_type_tag"] == "B1"
               for r in refs)
    assert all(r["status"] in ("PROPOSED_TYPE_NAME_ONLY_NOT_SPAN_REFERENCE",
                               "UNRESOLVED_NO_SAME_SOURCE_DETAIL_TYPE_REFERENCE")
               and r["plan_to_section_detail_verified"] is False
               and r["span_specific_detail_verified"] is False
               and r["physical_member_verified"] is False
               and r["financially_payable"] is False for r in refs)
    assert ledger["quantity_approval_count"] == 0


@pytest.mark.parametrize("mutate", [
    lambda pages, coverage, idx, members: pages[0]["detail_topology"].update(
        source_operator_count=999),
    lambda pages, coverage, idx, members: pages[0]["detail_topology"]["groups"][0].update(
        physical_member_verified=True),
    lambda pages, coverage, idx, members: coverage["vector_geometry_groupings"][0]["groups"][0].update(
        source_path_indices=[2]),
    lambda pages, coverage, idx, members: coverage["detail_title_anchors"][0].update(
        page=99),
    lambda pages, coverage, idx, members: idx.update(
        acceptance="COMPLETE"),
])
def test_reject_tampered_operator_counts_and_identity(tmp_path, mutate):
    source = _inspect(tmp_path, "two_details")
    page_data = deepcopy(source["operator_component_review"])
    # Recreate trusted upstream state independently for intentional tampering.
    from core.drawings.pdf_sheet_detail_inventory import inventory_pdf_page_regions
    pdf = pymupdf.open(_source(tmp_path, mode="two_details"))
    page = inventory_pdf_page_regions(pdf[0], document_id="PDF001", page_number=1,
                                      include_topology=True)
    page_summaries = [page]
    coverage = deepcopy(source["sheet_detail_inventory"])
    idx = deepcopy(source["detail_object_index"])
    members = deepcopy(source["member_type_candidates"])
    mutate(page_summaries, coverage, idx, members)
    with pytest.raises(ValueError):
        build_pdf_operator_component_review(page_summaries, coverage, idx, members)
    pdf.close()


def test_two_independent_pdfs_never_cross_link_by_matching_type_name(tmp_path):
    a = _source(tmp_path, mode="plan_detail")
    with pymupdf.open() as pdf:
        p = pdf.new_page(width=500, height=400)
        p.insert_text((40, 50), "Beam Detail B1")
        p.draw_rect(pymupdf.Rect(40, 82, 125, 160))
        b = tmp_path / "other.pdf"
        pdf.save(b)
    report = inspect_pdf_sheet_set([a, b])
    for link in report["operator_component_review"]["plan_detail_type_only_references"]:
        assert all(detail_id.startswith(f"TYPE_MARK:{link['plan_document_id']}:")
                   for detail_id in link["candidate_detail_type_ids"])
        assert link["physical_member_verified"] is False
