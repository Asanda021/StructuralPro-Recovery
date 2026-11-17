"""Synthetic all-trade PDF coverage gaps, never an approved automatic takeoff."""
from copy import deepcopy

import pytest
pymupdf = pytest.importorskip("pymupdf")

from core.drawings.pdf_auto_intake import inspect_pdf_sheet_set
from core.drawings.pdf_multidiscipline_gap_register import build_pdf_multidiscipline_gap_register


def _drawing(tmp_path, name, titles):
    output = tmp_path / name
    with pymupdf.open() as pdf:
        for title in titles:
            page = pdf.new_page(width=842, height=595)
            if title:
                page.insert_text((30, 32), title, fontsize=12)
            # Two independently located vector drawings on each nonempty page.
            if title:
                page.draw_rect(pymupdf.Rect(130, 140, 320, 350))
                page.draw_line((440, 180), (710, 390))
        pdf.save(output)
    return output


def _report(tmp_path):
    first = _drawing(tmp_path, "structure.pdf",
                     ("Beam Detail B1", "Foundation Plan", ""))
    second = _drawing(tmp_path, "other-trades.pdf",
                      ("Architectural Detail", "Mechanical Detail", "Electrical Detail"))
    return inspect_pdf_sheet_set([first, second])


def test_main_intake_exposes_every_page_and_unknown_remaining_scope(tmp_path):
    report = _report(tmp_path)
    ledger = report["multidiscipline_gap_register"]
    assert ledger["page_count"] == 6
    assert ledger["all_input_pages_accounted_for"] is True
    assert ledger["unclassified_page_count"] == 6
    assert ledger["acceptance"] == "PARTIAL_NO_GO"
    assert ledger["complete"] is False
    assert ledger["all_trades_reviewed"] is False
    assert ledger["all_details_interpreted"] is False
    assert ledger["quantity_approval_count"] == 0
    assert ledger["physical_member_count"] is None
    rows = ledger["coverage_rows"]
    assert len(rows) >= 6
    assert {(r["document_id"], r["page"]) for r in rows} == {
        ("PDF001", 1), ("PDF001", 2), ("PDF001", 3),
        ("PDF002", 1), ("PDF002", 2), ("PDF002", 3),
    }
    assert sum(r["candidate_family"] == "UNCLASSIFIED_OR_OTHER_TRADES" for r in rows) == 6
    assert all(r["financially_payable"] is False and
               r["physical_member_count"] is None and
               r["governing_revision_verified"] is False and
               r["drawing_scale_verified"] is False and
               r["level_scope_verified"] is False and
               r["detail_boundary_verified"] is False for r in rows)


def test_multi_trade_detail_titles_are_review_leads_not_accepted_families(tmp_path):
    ledger = _report(tmp_path)["multidiscipline_gap_register"]
    groups = {}
    for row in ledger["coverage_rows"]:
        groups.setdefault((row["document_id"], row["page"]), set()).add(row["candidate_family"])
    assert "beam" in groups[("PDF001", 1)]
    assert "architecture_finishes" in groups[("PDF002", 1)]
    assert "mechanical" in groups[("PDF002", 2)]
    assert "electrical" in groups[("PDF002", 3)]
    assert all("UNCLASSIFIED_OR_OTHER_TRADES" in vals for vals in groups.values())
    assert all(row["status"].startswith(("UNRESOLVED_", "BLOCKED_"))
               for row in ledger["coverage_rows"])


def test_blank_page_not_asserted_trade_free(tmp_path):
    ledger = _report(tmp_path)["multidiscipline_gap_register"]
    rows = [r for r in ledger["coverage_rows"]
            if r["document_id"] == "PDF001" and r["page"] == 3]
    assert len(rows) == 1
    assert rows[0]["candidate_family"] == "UNCLASSIFIED_OR_OTHER_TRADES"
    assert rows[0]["status"] == "UNRESOLVED_UNCLASSIFIED_SCOPE"
    assert rows[0]["required_review"]


def test_each_candidate_row_keeps_source_identity_and_no_member_count(tmp_path):
    report = _report(tmp_path)
    docs = {d["document_id"]: d["sha256"] for d in report["documents"]}
    coverage = report["sheet_detail_inventory"]
    ids = {r["region_id"] for r in coverage["region_inventory"]}
    rows = report["multidiscipline_gap_register"]["coverage_rows"]
    assert len({r["coverage_id"] for r in rows}) == len(rows)
    for row in rows:
        assert row["source_pdf_sha256"] == docs[row["document_id"]]
        assert row["source_region_ids"]
        assert set(row["source_region_ids"]) <= ids
        assert row["physical_member_count"] is None
        assert row["quantity_approval_count"] == 0


@pytest.mark.parametrize("mutation", [
    lambda c, i: c.update(all_input_pages_indexed=False),
    lambda c, i: c["sheet_inventory"].pop(),
    lambda c, i: c["documents"][0].update(sha256="0"*63),
    lambda c, i: c["documents"][0].update(page_count=7),
    lambda c, i: c["region_inventory"][0].update(financially_payable=True),
    lambda c, i: c["region_inventory"][0].update(region_id="PDF002:p1:r1:c1"),
    lambda c, i: i["detail_candidates"][0].update(physical_member_verified=True),
    lambda c, i: i.update(quantity_approval_count=1),
])
def test_fail_closed_on_missing_foreign_or_promoted_source(tmp_path, mutation):
    report = _report(tmp_path)
    coverage = deepcopy(report["sheet_detail_inventory"])
    index = deepcopy(report["detail_object_index"])
    mutation(coverage, index)
    with pytest.raises(ValueError):
        build_pdf_multidiscipline_gap_register(coverage, index)


def test_blocked_source_preserves_every_family_and_unclassified_review(tmp_path):
    report = _report(tmp_path)
    coverage = deepcopy(report["sheet_detail_inventory"])
    coverage["sheet_inventory"][0]["coverage_status"] = "BLOCKED"
    rows = build_pdf_multidiscipline_gap_register(coverage, report["detail_object_index"])["coverage_rows"]
    blocked = [r for r in rows if (r["document_id"], r["page"]) == ("PDF001", 1)]
    assert blocked
    assert all(r["status"] == "BLOCKED_SOURCE_EVIDENCE_INCOMPLETE" for r in blocked)
    assert all(r["physical_member_count"] is None for r in blocked)


def test_unknown_discipline_hint_survives_in_unclassified_remainder(tmp_path):
    report = _report(tmp_path)
    coverage = deepcopy(report["sheet_detail_inventory"])
    coverage["sheet_inventory"][0]["discipline_candidates"] = ["geotechnical_unsupported"]
    ledger = build_pdf_multidiscipline_gap_register(coverage, report["detail_object_index"])
    remainder = next(r for r in ledger["coverage_rows"] if
                     r["document_id"] == "PDF001" and r["page"] == 1
                     and r["candidate_family"] == "UNCLASSIFIED_OR_OTHER_TRADES")
    assert remainder["required_review"]
    assert ledger["all_trades_reviewed"] is False
