import copy

import pytest

from core.takeoff.ai_output_guard import validate_ai_takeoff_proposal


def valid_proposal():
    return {
        "drawing_id": "sha256:drawing-a101",
        "revision_id": "revision-3",
        "candidates": [
            {
                "source_id": "sha256:drawing-a101:page-2:region-7",
                "session_item_id": "TO-00001",
                "page": 2,
                "kind": "length",
                "unit": "m",
                "quantity": 12.5,
                "confidence": 0.97,
                "label": "طول دیوار محور A",
                "formula": "طول هندسی پس از کالیبراسیون صفحه ۲",
                "evidence": {
                    "source_ref": "drawing-a101.pdf#page=2&region=7",
                    "scale_ref": "calibration:page-2:rev-1",
                    "meters_per_pixel": 0.025,
                },
            }
        ],
    }


def test_ai_proposal_is_never_approved_without_explicit_user_confirmation():
    result = validate_ai_takeoff_proposal(valid_proposal())
    assert result["valid"] is True
    assert result["approved"] is False
    assert result["requires_human_confirmation"] is True
    assert result["rows"] == []


def test_ai_proposal_can_become_approved_only_after_confirmation():
    result = validate_ai_takeoff_proposal(valid_proposal(), user_confirmed=True)
    assert result["valid"] is True
    assert result["approved"] is True
    assert result["requires_human_confirmation"] is False
    assert len(result["rows"]) == 1
    assert result["rows"][0]["quantity"] == pytest.approx(12.5)


@pytest.mark.parametrize("mutation, expected", [
    (lambda p: p.update(drawing_id=""), "شناسه منبع نقشه"),
    (lambda p: p["candidates"][0]["evidence"].update(scale_ref=""), "مقیاس"),
    (lambda p: p["candidates"][0].update(unit="cm"), "واحد"),
    (lambda p: p["candidates"][0].update(quantity=float("nan")), "متناهی"),
    (lambda p: p["candidates"][0].update(confidence=0.2), "حد مجاز"),
    (lambda p: p["candidates"][0]["evidence"].update(source_ref=""), "مرجع دقیق"),
    (lambda p: p["candidates"][0].update(source_id=""), "شناسه منبع پایدار"),
])
def test_ai_proposal_missing_or_invalid_evidence_fails_closed(mutation, expected):
    proposal = copy.deepcopy(valid_proposal())
    mutation(proposal)
    result = validate_ai_takeoff_proposal(proposal, user_confirmed=True)
    assert result["valid"] is False
    assert result["approved"] is False
    assert result["rows"] == []
    assert any(expected in issue for issue in result["issues"])


def test_ai_proposal_rejects_duplicate_sources_and_fractional_counts():
    proposal = copy.deepcopy(valid_proposal())
    duplicate = copy.deepcopy(proposal["candidates"][0])
    proposal["candidates"].append(duplicate)
    result = validate_ai_takeoff_proposal(proposal, user_confirmed=True)
    assert result["valid"] is False
    assert any("تکراری" in issue for issue in result["issues"])

    proposal = copy.deepcopy(valid_proposal())
    candidate = proposal["candidates"][0]
    candidate.update(kind="count", unit="عدد", quantity=1.5)
    candidate["evidence"].pop("scale_ref", None)
    result = validate_ai_takeoff_proposal(proposal, user_confirmed=True)
    assert result["valid"] is False
    assert any("عدد صحیح" in issue for issue in result["issues"])


def test_ai_proposal_rejects_invalid_threshold_and_non_mapping():
    assert validate_ai_takeoff_proposal(None)["approved"] is False
    result = validate_ai_takeoff_proposal(valid_proposal(), minimum_confidence=float("nan"))
    assert result["valid"] is False
    assert result["approved"] is False
