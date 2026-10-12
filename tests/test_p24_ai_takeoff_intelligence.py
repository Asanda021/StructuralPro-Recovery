from core.ai.takeoff_ai_v1 import AITakeoffCandidate
from core.ai.takeoff_intelligence_v1 import (
    candidate_source_key, deduplicate_candidates, group_candidates,
    intelligence_fingerprint, normalize_drawing_text, validate_intelligence,
)

def c(cid, source, kind="beam", metric="length", q=6, confidence=.85):
    return AITakeoffCandidate(cid, kind, metric, q, "m", confidence, (source,), ("evidence",))

def test_p24_normalizes_common_drawing_text_variants():
    assert normalize_drawing_text("  ستون  ۱۲ ي ك ") == "ستون 12 ی ک"

def test_p24_duplicate_source_is_not_double_counted():
    rows, dupes = deduplicate_candidates([c("a", "G1"), c("b", "G1")])
    assert [r.candidate_id for r in rows] == ["a"]
    assert dupes == ["b"]
    assert candidate_source_key(rows[0]) == ("G1", "beam", "length")

def test_p24_grouping_is_traceable_and_sums_unique_quantities():
    rows = [c("a", "G1", q=6), c("b", "G2", q=4)]
    groups = group_candidates(rows)
    assert len(groups) == 1
    assert groups[0].quantity == 10
    assert groups[0].source_ids == ("G1", "G2")
    assert groups[0].needs_confirmation is True

def test_p24_grouping_does_not_double_count_duplicate_source():
    groups = group_candidates([c("a", "G1", q=6), c("b", "G1", q=6)])
    assert groups[0].quantity == 6

def test_p24_fingerprint_is_deterministic():
    rows = [c("a", "G1")]
    groups = group_candidates(rows)
    assert intelligence_fingerprint(groups) == intelligence_fingerprint(groups)

def test_p24_validation_fails_closed_when_confirmation_is_removed():
    rows = [c("a", "G1")]
    groups = group_candidates(rows)
    ok, errors = validate_intelligence(groups)
    assert ok is True
    bad = type(groups[0])(**{**groups[0].__dict__, "needs_confirmation": False})
    ok, errors = validate_intelligence([bad])
    assert ok is False
    assert "human confirmation gate removed" in errors
