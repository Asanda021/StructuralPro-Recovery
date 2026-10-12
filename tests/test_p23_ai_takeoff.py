from core.ai.takeoff_ai_v1 import (
    AITakeoffCandidate,
    build_takeoff_payload,
    candidate_fingerprint,
    propose_takeoff,
    review_candidates,
)
from core.drawings.dwg_takeoff import DWGEntity


def test_p23_proposes_traceable_candidate_without_inventing_quantity():
    entity = DWGEntity("LINE", "WALL", "wall-01", {"length": 4, "source_id": "A-101:wall-01"})
    rows = propose_takeoff([entity])
    assert len(rows) == 1
    row = rows[0]
    assert row.element_type == "wall"
    assert row.metric == "length"
    assert row.quantity == 4
    assert row.source_ids == ("A-101:wall-01",)
    assert row.needs_confirmation is True
    assert 0 <= row.confidence <= 1


def test_p23_ambiguous_evidence_fails_closed():
    entity = DWGEntity(
        "INSERT", "WALL_DOOR", "mixed-01",
        {"length": 4, "area": 8, "source_id": "A-101:mixed-01"},
    )
    assert propose_takeoff([entity]) == []


def test_p23_unknown_element_fails_closed():
    entity = DWGEntity("LINE", "MISC", "x", {"length": 4, "source_id": "A-101:x"})
    assert propose_takeoff([entity]) == []


def test_p23_review_never_auto_accepts():
    entity = DWGEntity("LINE", "BEAM", "b1", {"length": 6, "source_id": "A-101:b1"})
    row = propose_takeoff([entity])[0]
    decision = review_candidates([row])[0]
    assert decision.status == "review"
    assert "confirmation" in decision.reason


def test_p23_explicit_acceptance_is_required():
    entity = DWGEntity("LINE", "BEAM", "b1", {"length": 6, "source_id": "A-101:b1"})
    row = propose_takeoff([entity])[0]
    decision = review_candidates([row], {row.candidate_id: "accepted"})[0]
    assert decision.status == "accepted"


def test_p23_payload_is_deterministic_and_fingerprinted():
    entity = DWGEntity("LWPOLYLINE", "SLAB", "s1", {"area": 20, "source_id": "A-101:s1"})
    row = propose_takeoff([entity])[0]
    assert candidate_fingerprint(row) == candidate_fingerprint(row)
    payload = build_takeoff_payload([row], source_fingerprint="sha256:test")
    assert payload["kind"] == "ai_takeoff_v1"
    assert payload["fail_closed"] is True
    assert payload["review_required"] == 1
    assert payload["accepted_count"] == 0


def test_p23_bim_global_id_is_valid_evidence_source():
    entity = DWGEntity("IFCWALL", "IFCWALL", "global-1", {"length": 5, "global_id": "3x-global"})
    row = propose_takeoff([entity])[0]
    assert row.source_ids == ("3x-global",)
