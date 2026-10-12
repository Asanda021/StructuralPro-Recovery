import pytest
from core.ai.ai_qa_v1 import QAInput, QAFinding, create_finding, fingerprint, gate_findings


def item(status="accepted"):
    return QAInput("item-1", ("sheet:A1",), "explicit source claim", "r1", status)


def test_evidence_bound_finding():
    f = create_finding(item(), "f1", "warning", "Review source alignment.")
    assert f.evidence_ids == ("sheet:A1",)


def test_unaccepted_input_fails_closed():
    with pytest.raises(ValueError):
        create_finding(item("review"), "f1", "warning", "Review.")


def test_missing_message_fails_closed():
    with pytest.raises(ValueError):
        create_finding(item(), "f1", "warning", " ")


def test_gate_blocks_unaccepted_error():
    f = QAFinding("f1", "item-1", "error", "Critical evidence gap.", ("sheet:A1",), "open")
    assert gate_findings((f,)) == "blocked"


def test_gate_requires_review_for_open_warning():
    f = QAFinding("f1", "item-1", "warning", "Review evidence.", ("sheet:A1",), "open")
    assert gate_findings((f,)) == "review"


def test_gate_accepts_resolved_findings():
    f = QAFinding("f1", "item-1", "info", "Evidence verified.", ("sheet:A1",), "accepted")
    assert gate_findings((f,)) == "accepted"


def test_fingerprint_is_deterministic():
    f = create_finding(item(), "f1", "info", "Verified.")
    assert fingerprint(f) == fingerprint(f)
