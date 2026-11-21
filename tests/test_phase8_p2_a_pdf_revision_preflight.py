"""Synthetic source-bound PDF issue register drafting, never implicit CURRENT."""
from copy import deepcopy
import pytest

from core.drawings.pdf_revision_preflight import build_pdf_revision_register_draft
from core.drawings.pdf_detail_evidence_graph import _parse_registry


def sample(multi=False):
    return {
        "documents": [
            {"document_id":"PDF001","source_name":"plans.pdf","sha256":"a"*64,"page_count":2},
            {"document_id":"PDF002","source_name":"details.pdf","sha256":"b"*64,"page_count":1},
        ],
        "detail_evidence_graph":{"pages":[
            {"document_id":"PDF001","page":1,"printed_revisions":["R1"]},
            {"document_id":"PDF001","page":2,"printed_revisions":["R3" if multi else "R1"]},
            {"document_id":"PDF002","page":1,"printed_revisions":[]},
        ]},
    }


def test_issued_register_draft_is_not_loadable_without_real_authority():
    out=build_pdf_revision_register_draft(sample())
    assert out["source_document_count"]==2
    assert out["source_page_count"]==3
    assert list(out["template"])==["schema_version","documents"]
    assert out["template"]["documents"][0]["sha256"]=="a"*64
    assert all(entry[key] is None for entry in out["template"]["documents"]
               for key in ("project_id","issue_id","revision","status","authority_reference"))
    with pytest.raises(ValueError):
        _parse_registry(out["template"])
    assert out["quantity_approval_count"]==0
    assert out["financially_payable"] is False
    assert out["valid_register_to_attach"] is False
    assert out["review"][1]["pages_without_printed_revision"]==[1]


def test_collated_pdf_with_different_sheet_revisions_is_not_assumed_current():
    out=build_pdf_revision_register_draft(sample(multi=True))
    assert out["review"][0]["printed_revision_candidates"]==["R1","R3"]
    assert "MULTI_REVISION_PDF_REQUIRES_PAGE_SPECIFIC_AUTHORITY" in out["review"][0]["required_actions"]
    assert out["template"]["documents"][0]["revision"] is None


def test_two_printed_revisions_on_one_page_requires_authority():
    x=sample()
    x["detail_evidence_graph"]["pages"][0]["printed_revisions"]=["R1","R2"]
    out=build_pdf_revision_register_draft(x)
    assert out["review"][0]["pages_with_conflicting_revisions"]==[1]
    assert "CONFLICTING_PRINTED_REVISIONS_ON_PAGE" in out["review"][0]["required_actions"]


def test_missing_pages_and_forged_source_identity_fail_closed():
    x=sample()
    x["documents"][1]["sha256"]="a"*64
    with pytest.raises(ValueError,match="duplicate"):
        build_pdf_revision_register_draft(x)
    x=sample()
    x["detail_evidence_graph"]["pages"].pop()
    with pytest.raises(ValueError,match="Incomplete"):
        build_pdf_revision_register_draft(x)
    x=sample()
    x["detail_evidence_graph"]["pages"][0]["document_id"]="PDF999"
    with pytest.raises(ValueError,match="foreign"):
        build_pdf_revision_register_draft(x)
    x=sample()
    x["detail_evidence_graph"]["pages"].append(deepcopy(x["detail_evidence_graph"]["pages"][0]))
    with pytest.raises(ValueError,match="Duplicate"):
        build_pdf_revision_register_draft(x)


def test_missing_page_graph_keeps_template_non_authoritative():
    x=sample()
    x.pop("detail_evidence_graph")
    out=build_pdf_revision_register_draft(x)
    assert all("PAGE_EVIDENCE_NOT_ATTACHED" in r["required_actions"] for r in out["review"])
    assert out["valid_register_to_attach"] is False
