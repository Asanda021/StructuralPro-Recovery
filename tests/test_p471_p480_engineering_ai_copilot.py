import pytest

from core.ai.engineering_copilot_v1 import (
    CopilotEvidence,
    CopilotRequest,
    fingerprint,
    respond,
)


def evidence(status="accepted"):
    return {"e1": CopilotEvidence("e1", ("sheet:A1",), "explicit dimension exists", "r1", status)}


def request(action="explain", evidence_ids=("e1",)):
    return CopilotRequest("q1", "explain quantity provenance", ("element:1",), evidence_ids, action)


def test_evidence_driven_response_is_review_state():
    result = respond(request(), evidence(), "The quantity is supported by the supplied evidence.")
    assert result.status == "review"
    assert result.evidence_ids == ("e1",)


def test_missing_evidence_fails_closed():
    with pytest.raises(ValueError):
        respond(request(evidence_ids=("missing",)), evidence(), "proposal")


def test_unaccepted_evidence_fails_closed():
    with pytest.raises(ValueError):
        respond(request(), evidence("review"), "proposal")


def test_unsupported_action_fails_closed():
    with pytest.raises(ValueError):
        respond(request("calculate"), evidence(), "proposal")


def test_fingerprint_is_deterministic():
    result = respond(request("propose"), evidence(), "Suggested review of the supplied source.")
    assert fingerprint(result) == fingerprint(result)


def test_empty_proposal_fails():
    with pytest.raises(ValueError):
        respond(request(), evidence(), " ")
