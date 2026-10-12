from decimal import Decimal

import pytest

from core.revision.revision_impact_v1 import (
    RevisionSnapshot,
    compare_revisions,
    impact_totals,
    revision_impact_fingerprint,
)


def row(
    element: str,
    revision: str,
    record: str,
    quantity: str,
    boq: str,
    estimate: str,
    actual: str,
) -> RevisionSnapshot:
    return RevisionSnapshot(
        record_id=record,
        project_id="PROJECT-1",
        revision=revision,
        source_id=f"DRAW-{revision}",
        element_id=element,
        quantity=Decimal(quantity),
        boq_quantity=Decimal(boq),
        estimate_amount=Decimal(estimate),
        actual_cost=Decimal(actual),
    )


def test_added_removed_modified_and_totals_are_explicit():
    old = (
        row("E1", "R1", "R1-E1", "10", "10", "1000", "200"),
        row("E2", "R1", "R1-E2", "20", "20", "2000", "300"),
    )
    new = (
        row("E1", "R2", "R2-E1", "12", "12", "1200", "250"),
        row("E3", "R2", "R2-E3", "5", "5", "500", "0"),
    )

    report = compare_revisions(old, new, "R1", "R2")

    assert [c.change_type for c in report.changes] == ["modified", "removed", "added"]
    assert impact_totals(report) == {
        "quantity_delta": Decimal("-13"),
        "boq_quantity_delta": Decimal("-13"),
        "estimate_delta": Decimal("-1300"),
        "actual_cost_delta": Decimal("-250"),
    }


def test_no_change_produces_no_impact():
    old = (row("E1", "R1", "R1-E1", "10", "10", "1000", "200"),)
    new = (row("E1", "R2", "R2-E1", "10", "10", "1000", "200"),)

    report = compare_revisions(old, new, "R1", "R2")
    assert report.changes == ()


def test_revision_mismatch_fails_closed():
    with pytest.raises(ValueError):
        compare_revisions(
            (row("E1", "R0", "R0-E1", "1", "1", "1", "0"),),
            (row("E1", "R2", "R2-E1", "1", "1", "1", "0"),),
            "R1",
            "R2",
        )


def test_duplicate_element_fails_closed():
    with pytest.raises(ValueError):
        compare_revisions(
            (
                row("E1", "R1", "A", "1", "1", "1", "0"),
                row("E1", "R1", "B", "2", "2", "2", "0"),
            ),
            (row("E1", "R2", "C", "1", "1", "1", "0"),),
            "R1",
            "R2",
        )


def test_mixed_projects_fail_closed():
    a = row("E1", "R1", "A", "1", "1", "1", "0")
    b = row("E1", "R2", "B", "1", "1", "1", "0")
    object.__setattr__(b, "project_id", "PROJECT-2")
    with pytest.raises(ValueError):
        compare_revisions((a,), (b,), "R1", "R2")


def test_negative_input_fails_closed():
    with pytest.raises(ValueError):
        compare_revisions(
            (row("E1", "R1", "A", "-1", "1", "1", "0"),),
            (row("E1", "R2", "B", "1", "1", "1", "0"),),
            "R1",
            "R2",
        )


def test_fingerprint_is_deterministic():
    old = (row("E1", "R1", "A", "10", "10", "100", "20"),)
    new = (row("E1", "R2", "B", "12", "12", "120", "25"),)
    first = compare_revisions(old, new, "R1", "R2")
    second = compare_revisions(old, new, "R1", "R2")
    assert revision_impact_fingerprint(first) == revision_impact_fingerprint(second)
