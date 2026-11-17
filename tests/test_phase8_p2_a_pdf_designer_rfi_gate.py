"""Synthetic designer RFI and reply negative tests; no private drawings in CI."""
from copy import deepcopy
from hashlib import sha256
import json

import pymupdf
import pytest

from core.drawings.pdf_designer_rfi_gate import (
    build_designer_rfi_packet, inspect_designer_reply, load_designer_reply,
    write_designer_rfi_package,
)

PDF_HASH = "a"*64
GRAPH_HASH = "b"*64


def register():
    return {"status": "BLOCKED_AWAITING_GOVERNING_ENGINEERING_DOCUMENTS",
            "requests": [{"source_sha256": PDF_HASH,
                          "request_id": "BEAM_MISSING_DOCUMENT:"+"c"*32,
                          "required_evidence_codes": ["GOVERNING_DRAWING_ISSUE", "FABRICATION_CUT_LENGTH"],
                          "financially_payable": False,
                          "physical_member_verified": False,
                          "quantity_approved": False, "member_quantity": None,
                          "beam_page": 15, "detail_page":17,"span_axes":"A-B",
                          "printed_axis_row":"1","printed_mark":"5",
                          "end_review_id":"BEAM_END_REVIEW:1234", "profile_visual":"2IPE18",
                          "status":"BLOCKED_REQUIRES_GOVERNING_ENGINEERING_DOCUMENTS"}]}


def packet():
    return build_designer_rfi_packet(register(),source_sha256=PDF_HASH,graph_sha256=GRAPH_HASH)


def test_packet_anchors_span_and_both_conflicts_without_approval():
    p=packet()
    assert len(p["questions"])==3
    assert {x["category"] for x in p["questions"]}=={"BEAM_SPAN","PLAN_DETAIL_CONFLICT"}
    assert {x.get("conflict_code") for x in p["questions"] if x["category"]=="PLAN_DETAIL_CONFLICT"}=={"C2","F3"}
    assert all(x["status"]=="UNSENT_PENDING_DESIGNER" and x["physical_member_verified"] is False
               and x["approved_length_m"] is None and x["financially_payable"] is False for x in p["questions"])
    assert not p["response_received"] and not p["approved_financial_rows"]
    assert p["packet_sha256"] == packet()["packet_sha256"]


def test_package_export_is_private_and_empty_reply_never_claims_assurance(tmp_path):
    p=packet()
    write_designer_rfi_package(p,tmp_path)
    saved=json.loads((tmp_path/"PRIVATE_ENGINEERING_RFI_PACKET.json").read_text())
    assert saved["packet_sha256"] == p["packet_sha256"]
    t=load_designer_reply(tmp_path/"DESIGNER_RESPONSE_TEMPLATE.json")
    result=inspect_designer_reply(p,t)
    assert result["received_evidence_count"]==0
    assert result["questions_still_without_response"]==3
    assert result["acceptance"]=="PARTIAL_NO_GO"
    assert "ارسال‌نشده" in (tmp_path/"PRIVATE_RFI_TO_STRUCTURAL_DESIGNER_FA.md").read_text()


@pytest.mark.parametrize("mutator",[
    lambda r:r.update(status="COMPLETE"),
    lambda r:r["requests"][0].update(financially_payable=True),
    lambda r:r["requests"][0].update(member_quantity=2),
    lambda r:r["requests"][0].update(source_sha256="f"*64),
    lambda r:r["requests"].append(deepcopy(r["requests"][0])),
    lambda r:r["requests"][0].update(required_evidence_codes=["CUT", "CUT"]),
    lambda r:r["requests"][0].update(span_axes="A/2"),
    lambda r:r.update(requests=[]),
])
def test_reject_foreign_financial_or_unbounded_source_register(mutator):
    r=register()
    mutator(r)
    with pytest.raises(ValueError):
        build_designer_rfi_packet(r,source_sha256=PDF_HASH)


def test_wrong_packet_hash_or_mutated_question_rejected():
    p=packet()
    reply={"schema_version":1,"packet_sha256":p["packet_sha256"],
           "reply_reference":"RFI-ANSWER-12", "responses":[]}
    p["questions"][0]["request_fa"]="Forged after creation"
    with pytest.raises(ValueError,match="identity"):
        inspect_designer_reply(p,reply)
    p=packet()
    reply["packet_sha256"]="f"*64
    with pytest.raises(ValueError,match="another"):
        inspect_designer_reply(p,reply)


def _pdf(dirpath, name="issued.pdf"):
    path=dirpath/name
    with pymupdf.open() as d:
        d.new_page()
        d.save(path)
    return path


def _reply(p,attachment):
    return {"schema_version":1,"packet_sha256":p["packet_sha256"],"reply_reference":"DESIGN-RFI-12",
            "responses":[{"question_id":p["questions"][0]["question_id"],
                          "evidence_code":"FABRICATION_CUT_LENGTH",
                          "attachment_name":attachment.name,
                          "attachment_sha256":sha256(attachment.read_bytes()).hexdigest(),
                          "page_number":1,"document_reference":"STRUCT-DRG-001",
                          "document_revision":"R2"}]}


def test_received_actual_pdf_is_byte_checked_but_still_unapproved(tmp_path):
    p=packet(); f=_pdf(tmp_path)
    result=inspect_designer_reply(p,_reply(p,f),attachment_directory=tmp_path)
    assert result["status"]=="RECEIPT_ONLY_NOT_DESIGN_APPROVAL"
    assert result["received_evidence_count"]==1
    assert result["responses"][0]["status"]=="SOURCE_BYTES_MATCHED_ENGINEERING_REVIEW_REQUIRED"
    assert result["physical_member_verified"] is False
    assert result["approved_financial_rows"]==0
    assert result["questions_still_without_response"]==2


@pytest.mark.parametrize("edit",[
    lambda r:r["responses"][0].update(attachment_sha256="f"*64),
    lambda r:r["responses"][0].update(page_number=2),
    lambda r:r["responses"][0].update(evidence_code="NOT_REQUESTED"),
    lambda r:r["responses"][0].update(question_id="NOT_A_REAL_RFI"),
    lambda r:r["responses"][0].update(document_revision=""),
    lambda r:r["responses"][0].update(approved_length_m=12),
    lambda r:r["responses"].append(deepcopy(r["responses"][0])),
    lambda r:r.update(packet_sha256="c"*64),
    lambda r:r.update(reply_reference=""),
])
def test_reject_unsafe_fake_duplicate_or_foreign_evidence(tmp_path,edit):
    p=packet(); f=_pdf(tmp_path); r=_reply(p,f)
    edit(r)
    with pytest.raises(ValueError):
        inspect_designer_reply(p,r,attachment_directory=tmp_path)


def test_reject_document_with_invalid_traversal_path_or_missing_bytes(tmp_path):
    p=packet(); f=_pdf(tmp_path); r=_reply(p,f)
    r["responses"][0]["attachment_name"]="../issued.pdf"
    with pytest.raises(ValueError):inspect_designer_reply(p,r,attachment_directory=tmp_path)
    r=_reply(p,f)
    with pytest.raises(ValueError,match="locally"):
        inspect_designer_reply(p,r)
    f.unlink()
    with pytest.raises(ValueError,match="missing"):
        inspect_designer_reply(p,r,attachment_directory=tmp_path)


def test_load_json_rejects_duplicate_keys_and_bad_shape(tmp_path):
    bad=tmp_path/"reply.json"
    bad.write_text('{"a":1,"a":2}')
    with pytest.raises(ValueError,match="Duplicate"):
        load_designer_reply(bad)
    bad.write_text(" "* (256*1024+1))
    with pytest.raises(ValueError,match="Oversized"):
        load_designer_reply(bad)

def test_two_codes_for_one_question_are_legal_and_not_engineering_approval(tmp_path):
    p = packet()
    path = _pdf(tmp_path)
    r = _reply(p, path)
    second = deepcopy(r["responses"][0])
    second["evidence_code"] = "GOVERNING_DRAWING_ISSUE"
    r["responses"].append(second)
    receipt = inspect_designer_reply(p, r, attachment_directory=tmp_path)
    assert receipt["received_evidence_count"] == 2
    assert receipt["questions_with_some_response"] == 1
    assert receipt["questions_with_all_evidence_received"] == 1
    assert receipt["questions_partially_received"] == 0
    assert receipt["questions_still_without_response"] == 2
    assert receipt["question_coverage"][0]["missing_evidence_codes"] == []
    assert receipt["question_coverage"][0]["status"] == "ALL_CODES_RECEIVED_ENGINEERING_REVIEW_REQUIRED"
    assert not receipt["question_coverage"][0]["engineering_approved"]
    assert not receipt["physical_member_verified"]
    assert receipt["approved_financial_rows"] == 0


def test_partial_receipt_exposes_exact_missing_evidence_codes(tmp_path):
    p = packet()
    path = _pdf(tmp_path)
    result = inspect_designer_reply(p, _reply(p, path), attachment_directory=tmp_path)
    row = result["question_coverage"][0]
    assert row["received_code_count"] == 1
    assert row["required_code_count"] == 2
    assert row["missing_evidence_codes"] == ["GOVERNING_DRAWING_ISSUE"]
    assert row["status"] == "PARTIAL_CODES_RECEIVED_ENGINEERING_REVIEW_REQUIRED"
    assert result["questions_partially_received"] == 1
    assert result["questions_with_all_evidence_received"] == 0
    assert result["questions_still_without_response"] == 2
    assert all(x["status"] == "NO_EVIDENCE_RECEIVED" for x in result["question_coverage"][1:])


def test_conflicting_same_document_revision_is_rejected_but_other_sheet_allowed(tmp_path):
    p = packet()
    path = _pdf(tmp_path)
    base = _reply(p, path)
    second = deepcopy(base["responses"][0])
    second["evidence_code"] = "GOVERNING_DRAWING_ISSUE"
    second["document_revision"] = "R3"
    base["responses"].append(second)
    with pytest.raises(ValueError, match="Conflicting revisions"):
        inspect_designer_reply(p, base, attachment_directory=tmp_path)
    second["document_reference"] = "STRUCT-DRG-002"
    receipt = inspect_designer_reply(p, base, attachment_directory=tmp_path)
    assert receipt["received_evidence_count"] == 2
    assert receipt["questions_with_all_evidence_received"] == 1
    assert receipt["approved_financial_rows"] == 0


def test_no_reply_has_per_code_coverage_without_auto_acceptance():
    p = packet()
    empty = {"schema_version":1, "packet_sha256":p["packet_sha256"],
             "reply_reference":"RFI-OPEN-01", "responses":[]}
    receipt = inspect_designer_reply(p, empty)
    assert len(receipt["question_coverage"]) == len(p["questions"])
    assert receipt["questions_with_all_evidence_received"] == 0
    assert receipt["questions_partially_received"] == 0
    assert receipt["questions_still_without_response"] == 3
    assert receipt["acceptance"] == "PARTIAL_NO_GO"
