"""Evidence-first revision/change impact engine for P581-P590.

The caller supplies both revision snapshots. This module compares explicit
element/quantity/BOQ/estimate/cost values only; it never infers geometry,
quantities, prices, or engineering values.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from hashlib import sha256
import json
from typing import Iterable


@dataclass(frozen=True)
class RevisionSnapshot:
    record_id: str
    project_id: str
    revision: str
    source_id: str
    element_id: str
    quantity: Decimal
    boq_quantity: Decimal
    estimate_amount: Decimal
    actual_cost: Decimal


@dataclass(frozen=True)
class RevisionChange:
    element_id: str
    change_type: str
    old_record_id: str | None
    new_record_id: str | None
    quantity_delta: Decimal
    boq_quantity_delta: Decimal
    estimate_delta: Decimal
    actual_cost_delta: Decimal


@dataclass(frozen=True)
class RevisionImpactReport:
    project_id: str
    old_revision: str
    new_revision: str
    changes: tuple[RevisionChange, ...]


_ALLOWED_CHANGE_TYPES = {"added", "removed", "modified"}


def _required_text(*values: str) -> None:
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError("required identity/provenance text is missing")


def _number(value: Decimal, label: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise ValueError(f"{label} must be a finite non-negative Decimal")


def validate_snapshot(snapshot: RevisionSnapshot) -> None:
    _required_text(
        snapshot.record_id,
        snapshot.project_id,
        snapshot.revision,
        snapshot.source_id,
        snapshot.element_id,
    )
    for value, label in (
        (snapshot.quantity, "quantity"),
        (snapshot.boq_quantity, "boq_quantity"),
        (snapshot.estimate_amount, "estimate_amount"),
        (snapshot.actual_cost, "actual_cost"),
    ):
        _number(value, label)


def _validate_collection(
    snapshots: Iterable[RevisionSnapshot],
    expected_revision: str,
) -> tuple[RevisionSnapshot, ...]:
    rows = tuple(snapshots)
    _required_text(expected_revision)
    seen: set[str] = set()
    for row in rows:
        validate_snapshot(row)
        if row.revision != expected_revision:
            raise ValueError("snapshot revision does not match requested revision")
        if row.record_id in seen:
            raise ValueError(f"duplicate snapshot record id: {row.record_id}")
        seen.add(row.record_id)
    return rows


def compare_revisions(
    old_snapshots: Iterable[RevisionSnapshot],
    new_snapshots: Iterable[RevisionSnapshot],
    old_revision: str,
    new_revision: str,
) -> RevisionImpactReport:
    """Compare explicit snapshots and return deterministic impact records."""
    _required_text(old_revision, new_revision)
    if old_revision == new_revision:
        raise ValueError("old and new revisions must differ")

    old_rows = _validate_collection(old_snapshots, old_revision)
    new_rows = _validate_collection(new_snapshots, new_revision)

    projects = {row.project_id for row in (*old_rows, *new_rows)}
    if len(projects) != 1:
        raise ValueError("all snapshots must belong to one project")
    project_id = next(iter(projects))

    old_by_element: dict[str, RevisionSnapshot] = {}
    new_by_element: dict[str, RevisionSnapshot] = {}
    for row in old_rows:
        if row.element_id in old_by_element:
            raise ValueError(f"duplicate element id in old revision: {row.element_id}")
        old_by_element[row.element_id] = row
    for row in new_rows:
        if row.element_id in new_by_element:
            raise ValueError(f"duplicate element id in new revision: {row.element_id}")
        new_by_element[row.element_id] = row

    changes: list[RevisionChange] = []
    for element_id in sorted(set(old_by_element) | set(new_by_element)):
        old = old_by_element.get(element_id)
        new = new_by_element.get(element_id)

        if old is None:
            changes.append(RevisionChange(
                element_id=element_id,
                change_type="added",
                old_record_id=None,
                new_record_id=new.record_id,
                quantity_delta=new.quantity,
                boq_quantity_delta=new.boq_quantity,
                estimate_delta=new.estimate_amount,
                actual_cost_delta=new.actual_cost,
            ))
            continue

        if new is None:
            changes.append(RevisionChange(
                element_id=element_id,
                change_type="removed",
                old_record_id=old.record_id,
                new_record_id=None,
                quantity_delta=-old.quantity,
                boq_quantity_delta=-old.boq_quantity,
                estimate_delta=-old.estimate_amount,
                actual_cost_delta=-old.actual_cost,
            ))
            continue

        delta = (
            new.quantity - old.quantity,
            new.boq_quantity - old.boq_quantity,
            new.estimate_amount - old.estimate_amount,
            new.actual_cost - old.actual_cost,
        )
        if any(value != 0 for value in delta):
            changes.append(RevisionChange(
                element_id=element_id,
                change_type="modified",
                old_record_id=old.record_id,
                new_record_id=new.record_id,
                quantity_delta=delta[0],
                boq_quantity_delta=delta[1],
                estimate_delta=delta[2],
                actual_cost_delta=delta[3],
            ))

    return RevisionImpactReport(
        project_id=project_id,
        old_revision=old_revision,
        new_revision=new_revision,
        changes=tuple(changes),
    )


def validate_change(change: RevisionChange) -> None:
    _required_text(change.element_id, change.change_type)
    if change.change_type not in _ALLOWED_CHANGE_TYPES:
        raise ValueError("invalid revision change type")
    if change.change_type == "added" and change.old_record_id is not None:
        raise ValueError("added change cannot have an old record")
    if change.change_type == "removed" and change.new_record_id is not None:
        raise ValueError("removed change cannot have a new record")
    if change.change_type == "modified" and (
        change.old_record_id is None or change.new_record_id is None
    ):
        raise ValueError("modified change requires both record identities")


def impact_totals(report: RevisionImpactReport) -> dict[str, Decimal]:
    if not report.project_id.strip() or not report.old_revision.strip() or not report.new_revision.strip():
        raise ValueError("report identity is required")
    for change in report.changes:
        validate_change(change)
    return {
        "quantity_delta": sum((c.quantity_delta for c in report.changes), Decimal("0")),
        "boq_quantity_delta": sum((c.boq_quantity_delta for c in report.changes), Decimal("0")),
        "estimate_delta": sum((c.estimate_delta for c in report.changes), Decimal("0")),
        "actual_cost_delta": sum((c.actual_cost_delta for c in report.changes), Decimal("0")),
    }


def revision_impact_fingerprint(report: RevisionImpactReport) -> str:
    impact_totals(report)
    payload = {
        "project_id": report.project_id,
        "old_revision": report.old_revision,
        "new_revision": report.new_revision,
        "changes": [asdict(change) for change in report.changes],
    }

    def normalize(value: object) -> object:
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, dict):
            return {key: normalize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [normalize(item) for item in value]
        return value

    canonical = json.dumps(
        normalize(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()
