"""P38 acceptance tests for AI Takeoff 2.0."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from core.ai.takeoff_ai_v2 import (
    AITakeoffFeedback,
    build_ai_takeoff_2_package,
    create_feedback,
    detect_components,
    extract_dimensions,
    feedback_fingerprint,
)
from core.ai.takeoff_ai_v1 import propose_takeoff


@dataclass
class Entity:
    layer: str = ""
    entity_type: str = ""
    source_id: str = ""
    data: dict | None = None


def test_detects_structural_and_rebar_components():
    entities = (
        Entity(layer="COLUMN", source_id="c1", data={"text": "ستون"}),
        Entity(layer="REBAR", source_id="r1", data={"text": "میلگرد"}),
    )
    detected = detect_components(entities)
    assert ("c1", "column", 0.92) in detected
    assert ("r1", "rebar", 0.92) in detected


def test_extracts_only_explicit_dimensions():
    entities = (
        Entity(source_id="d1", data={"text": "طول 4.50 m"}),
        Entity(source_id="d2", data={"text": "12 بدون واحد"}),
    )
    dimensions = extract_dimensions(entities)
    assert len(dimensions) == 1
    assert dimensions[0].value == pytest.approx(4.5)
    assert dimensions[0].unit == "m"


def test_p38_reuses_existing_takeoff_pipeline_and_stays_review_only():
    entities = (
        Entity(layer="beam", source_id="b1", data={"volume": 2.5, "text": "beam"}),
    )
    package, dimensions = build_ai_takeoff_2_package(
        entities, source_fingerprint="source-abc"
    )
    assert package.status == "review_required"
    assert package.ready_for_review is True
    assert package.approved is False
    assert package.fail_closed is False
    assert dimensions == ()


def test_feedback_is_traceable_and_deterministic():
    candidate = propose_takeoff(
        (Entity(layer="beam", source_id="b1", data={"volume": 2.5, "text": "beam"}),)
    )[0]
    item = create_feedback(
        candidate,
        reviewer_id="engineer-1",
        outcome="corrected",
        correction="2.6",
        source_fingerprint="source-abc",
    )
    assert isinstance(item, AITakeoffFeedback)
    assert feedback_fingerprint((item,)) == feedback_fingerprint((item,))


def test_invalid_feedback_fails_closed():
    with pytest.raises(ValueError):
        AITakeoffFeedback("", "reviewer", "accepted", "", "source")
