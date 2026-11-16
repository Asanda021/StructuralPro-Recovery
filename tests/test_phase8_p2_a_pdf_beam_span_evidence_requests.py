"""Synthetic-only validation of blocked per-span engineering document requests."""
import copy
import json
import pytest

from core.drawings.pdf_beam_span_evidence_requests import (
    build_beam_span_evidence_requests, write_beam_span_evidence_requests,
)

SHA = "a" * 64


def sample():
    bbox = [200.0, 160.0, 252.0, 197.3333]
    first = {"anchor_id": "anchor:1", "source_sha256": SHA,
             "document_id": "PDF001", "page": 15, "source_name": "naghshe.pdf",
             "kind": "VISUALLY_READ_BEAM_PROFILE", "bbox_pt": bbox}
    profile = {"review_id": "prof-1", "status": "REVIEW_REQUIRED",
               "span_axes": "A-B", "printed_axis_row": "3",
               "circled_mark_raw": "1", "profile_text": "2IPE16",
               "anchors": [first], "financially_payable": False,
               "physical_member_verified": False, "quantity_approved": False,
               "member_quantity": None}
    end = {"review_id": "end-1", "source_sha256": SHA,
           "document_id": "PDF001", "beam_page": 15, "axis_page": 13,
           "detail_page": 17, "plan_profile_bbox_pt": bbox,
           "span_axes": "A-B", "printed_axis_row": "3", "profile_text": "2IPE16",
           "status": "PROPOSED_BOTH_END_GRID_SYMBOLS", "detail_status": "PROPOSED_TYPE_ONLY_NOT_SPAN_SPECIFIC",
           "endpoint_marker_ids": ["mark-A3", "mark-B3"],
           "candidate_detail_count": 1, "anchors": [first],
           "financially_payable": False, "physical_member_verified": False,
           "support_verified": False, "detail_link_verified": False,
           "member_quantity": None, "verified_installed_length": None}
    return {"acceptance": "PARTIAL_NO_GO", "complete": False,
            "fully_evidenced_member_count": 0, "temporary_quantity_count": 0,
            "quantity_approval_count": 0,
            "beam_profile_reviews": [profile], "beam_end_support_reviews": [end]}


def test_single_span_requests_documents_not_payable_member():
    result = build_beam_span_evidence_requests(sample(), expected_sha256=SHA)
    assert result["status"] == "BLOCKED_AWAITING_GOVERNING_ENGINEERING_DOCUMENTS"
    assert result["summary"]["candidate_spans"] == 1
    assert result["summary"]["name_only_detail_matches"] == 1
    assert result["summary"]["two_end_symbols_proposed"] == 1
    row, = result["requests"]
    assert row["status"].startswith("BLOCKED_")
    assert "SPAN_SPECIFIC_CONNECTION_DETAIL" in row["required_evidence_codes"]
    assert "FABRICATION_CUT_LENGTH" in row["required_evidence_codes"]
    assert "TYPE_ONLY_DETAIL_IS_NOT_SPAN_REFERENCE" in row["required_evidence_codes"]
    assert row["span_specific_detail_verified"] is False
    assert row["member_quantity"] is None and row["financially_payable"] is False


def test_ambiguous_glyph_and_missing_one_end_add_separate_requests():
    graph = sample()
    graph["beam_profile_reviews"][0]["status"] = "BLOCKED"
    graph["beam_end_support_reviews"][0]["status"] = "BLOCKED_PROFILE_GLYPH_UNCERTAIN"
    graph["beam_end_support_reviews"][0]["endpoint_marker_ids"] = ["mark-A3", None]
    row, = build_beam_span_evidence_requests(graph)["requests"]
    assert "PROFILE_VISUAL_GLYPH_CONFIRMATION" in row["required_evidence_codes"]
    assert "BOTH_ENDPOINT_MARKERS_RECONCILIATION" in row["required_evidence_codes"]


def test_no_manual_observations_are_not_mistaken_for_success():
    graph = sample()
    graph["beam_profile_reviews"] = []
    graph["beam_end_support_reviews"] = []
    result = build_beam_span_evidence_requests(graph)
    assert result["status"] == "NOT_ASSESSED_MISSING_BEAM_WITNESSES"
    assert result["summary"]["source_identity_verified"] is False
    assert result["requests"] == []


def test_duplicate_or_foreign_profile_fails_closed():
    graph = sample()
    graph["beam_profile_reviews"].append(copy.deepcopy(graph["beam_profile_reviews"][0]))
    graph["beam_end_support_reviews"].append(copy.deepcopy(graph["beam_end_support_reviews"][0]))
    with pytest.raises(ValueError, match="Duplicate"):
        build_beam_span_evidence_requests(graph)
    graph = sample()
    with pytest.raises(ValueError, match="Foreign"):
        build_beam_span_evidence_requests(graph, expected_sha256="b" * 64)


@pytest.mark.parametrize("field,value", [
    ("financially_payable", True), ("physical_member_verified", True),
    ("support_verified", True), ("detail_link_verified", True),
    ("member_quantity", 1), ("verified_installed_length", 2.6),
    ("source_sha256", "b" * 64), ("beam_page", 14),
    ("profile_text", "2IPE18"), ("endpoint_marker_ids", ["mark-A3"]),
    ("candidate_detail_count", -1), ("plan_profile_bbox_pt", [-1, 0, -1, 2]),
])
def test_nonfinancial_cross_sheet_guards(field, value):
    graph = sample()
    graph["beam_end_support_reviews"][0][field] = value
    with pytest.raises(ValueError):
        build_beam_span_evidence_requests(graph)


def test_mismatched_source_anchor_rejected():
    graph = sample()
    graph["beam_end_support_reviews"][0]["anchors"][0] = dict(graph["beam_end_support_reviews"][0]["anchors"][0])
    graph["beam_end_support_reviews"][0]["anchors"][0]["source_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="Foreign"):
        build_beam_span_evidence_requests(graph)


def test_gap_between_profile_and_end_rejected():
    graph = sample()
    graph["beam_end_support_reviews"] = []
    with pytest.raises(ValueError, match="Incomplete"):
        build_beam_span_evidence_requests(graph)


def test_output_deterministic_and_private_export(tmp_path):
    one = build_beam_span_evidence_requests(sample(), expected_sha256=SHA)
    two = build_beam_span_evidence_requests(sample(), expected_sha256=SHA)
    assert one == two
    write_beam_span_evidence_requests(one, tmp_path)
    data = json.loads((tmp_path / "PRIVATE_BEAM_GOVERNING_DOCUMENT_REQUESTS.json").read_text(encoding="utf8"))
    assert data == one
    exported = (tmp_path / "PRIVATE_BEAM_GOVERNING_DOCUMENT_REQUESTS.csv").read_text(encoding="utf-8-sig")
    assert "FABRICATION_CUT_LENGTH" in exported
    assert "BEAM_MISSING_DOCUMENT:" in exported
    assert "noghshe" not in exported


def test_approved_graph_never_generates_provisional_design_assurance():
    graph = sample()
    graph["quantity_approval_count"] = 1
    with pytest.raises(ValueError, match="approved quantities"):
        build_beam_span_evidence_requests(graph)


def test_other_families_nonfinancial_completed_are_not_blocked():
    graph = sample()
    graph['temporary_quantity_count'] = 3
    graph['fully_evidenced_member_count'] = 3
    result = build_beam_span_evidence_requests(graph)
    assert result['summary']['verified_beam_members'] == 0
    assert result['summary']['candidate_spans'] == 1