"""Acceptance contract for the P1-P140 deep product gap audit v2."""
from pathlib import Path

DOC = Path(__file__).resolve().parents[1] / "docs" / "P1_P140_DEEP_PRODUCT_GAP_AUDIT_V2.md"

REQUIRED = (
    "P141-P150",
    "P161-P180",
    "P181-P200",
    "P201-P220",
    "P221-P240",
    "P241-P260",
    "P261-P280",
    "P281-P300",
    "P301-P320",
    "P321-P340",
    "P341-P360",
    "P361-P380",
    "source → recognized element → quantity → BOQ → price → estimate → report",
    "official Iranian annual price-list datasets",
)

def test_deep_product_gap_audit_is_complete():
    text = DOC.read_text(encoding="utf-8")
    assert "P1-P140" in text
    for marker in REQUIRED:
        assert marker in text
    assert "P1-P140: GREEN / verified baseline." in text
    assert "P141-P380: not started as implementation." in text
