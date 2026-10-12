from core.drawings.review import review_candidates


def test_review_required_candidate_needs_explicit_true_without_quantity_change():
    candidates = [{
        "source": "pdf:p3",
        "description": "wall",
        "quantity": 12.5,
        "unit": "m",
        "page": 3,
        "sheet": "A-103",
        "confidence": 0.45,
        "needs_confirmation": True,
    }]
    accepted, audit = review_candidates(candidates, reviewed_at="2026-10-02T00:00:00+00:00")
    assert accepted == []
    assert audit[0]["decision"] == "rejected_pending_confirmation"
    assert audit[0]["page"] == 3
    assert audit[0]["sheet"] == "A-103"
    assert audit[0]["quantity"] == 12.5

    accepted, audit = review_candidates(
        candidates, {1: True}, reviewer="engineer", reviewed_at="2026-10-02T00:00:00+00:00"
    )
    assert len(accepted) == 1
    assert accepted[0]["quantity"] == 12.5
    assert accepted[0]["confirmation_status"] == "approved"
    assert accepted[0]["provenance"]["source"] == "pdf:p3"
    assert accepted[0]["provenance"]["page"] == 3
    assert audit[0]["decision"] == "approved"


def test_safe_candidate_can_be_explicitly_rejected_and_audited():
    candidates = [{
        "source": "cad:WALL:42",
        "description": "wall",
        "quantity": 8,
        "unit": "m",
        "handle": "42",
        "layer": "WALL",
        "needs_confirmation": False,
    }]
    accepted, audit = review_candidates(
        candidates, {1: False}, reviewer="engineer", reviewed_at="2026-10-02T00:00:00+00:00"
    )
    assert accepted == []
    assert audit[0]["decision"] == "rejected"
    assert audit[0]["source"] == "cad:WALL:42"


def test_safe_candidate_preserves_provenance_when_accepted():
    candidates = [{
        "source": "cad:COL:C1",
        "description": "column",
        "quantity": 4,
        "unit": "عدد",
        "entity_type": "INSERT",
        "layer": "COL",
        "handle": "C1",
        "needs_confirmation": False,
    }]
    accepted, _ = review_candidates(
        candidates, reviewer="engineer", reviewed_at="2026-10-02T00:00:00+00:00"
    )
    assert accepted[0]["quantity"] == 4
    assert accepted[0]["provenance"] == {
        "source": "cad:COL:C1",
        "sheet": "",
        "page": None,
        "revision": "",
        "handle": "C1",
        "entity_type": "INSERT",
        "layer": "COL",
        "metric": None,
        "element_type": None,
    }
