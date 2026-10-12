import json
from pathlib import Path

from core.validation.real_world_validation_v1 import (
    REQUIRED_SCALES,
    REQUIRED_SURFACES,
    acceptance_summary,
    validate_evidence,
)

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "validation" / "real_world" / "P29_EVIDENCE.json"

def _rows():
    payload = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert payload["phase"] == "P29"
    assert payload["basis"] == "repository_golden_validation"
    return payload["evidence"]

def test_p29_evidence_is_complete_and_verified():
    result = validate_evidence(_rows())
    assert result["valid"] is True
    assert result["scales"] == list(REQUIRED_SCALES)
    assert result["surfaces"] == list(REQUIRED_SURFACES)
    assert len(result["scenarios"]) >= 3

def test_p29_acceptance_summary_is_deterministic():
    rows = _rows()
    assert acceptance_summary(rows) == acceptance_summary(rows)

def test_p29_is_fail_closed_for_missing_real_evidence():
    rows = list(_rows())
    rows[0] = {**rows[0], "status": "pending"}
    result = validate_evidence(rows)
    assert result["valid"] is False
    assert any("status is not verified" in issue for issue in result["issues"])

def test_p29_requires_all_scales():
    rows = [row for row in _rows() if row["scale"] != "large"]
    result = validate_evidence(rows)
    assert result["valid"] is False
    assert any("missing scales" in issue for issue in result["issues"])
