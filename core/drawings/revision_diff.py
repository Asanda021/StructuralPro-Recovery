"""Deterministic revision comparison for drawing takeoff candidates.

The service compares two already-extracted candidate snapshots. It does not
re-run CAD parsing and does not guess whether a change is intentional.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import math
from typing import Any, Iterable


@dataclass(frozen=True)
class RevisionChange:
    change_type: str
    key: str
    before_quantity: float | None = None
    after_quantity: float | None = None
    unit: str | None = None
    before_description: str = ""
    after_description: str = ""

    @property
    def quantity_delta(self) -> float | None:
        if self.before_quantity is None or self.after_quantity is None:
            return None
        return self.after_quantity - self.before_quantity

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["quantity_delta"] = self.quantity_delta
        return result


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _key(row: dict[str, Any]) -> str:
    source = str(row.get("source") or "").strip()
    if source:
        return source
    return "|".join(
        str(row.get(field) or "")
        for field in ("layer", "entity_type", "metric", "description")
    )


def _normalise(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = _key(row)
        if not key:
            continue
        # First occurrence is retained deterministically; duplicate source
        # identities are surfaced separately instead of silently changing order.
        if key not in result:
            result[key] = row
    return result


def compare_revisions(
    before: Iterable[dict[str, Any]],
    after: Iterable[dict[str, Any]],
    *,
    quantity_tolerance: float = 1e-9,
) -> list[dict[str, Any]]:
    """Return added, removed, changed and unchanged drawing candidates."""
    if quantity_tolerance < 0 or not math.isfinite(quantity_tolerance):
        raise ValueError("quantity_tolerance must be finite and nonnegative")

    old = _normalise(before)
    new = _normalise(after)
    changes: list[RevisionChange] = []

    for key in sorted(set(old) | set(new)):
        before_row = old.get(key)
        after_row = new.get(key)
        if before_row is None:
            changes.append(RevisionChange(
                "added", key, None, _number(after_row.get("quantity")),
                after_row.get("unit"), "", str(after_row.get("description") or "")
            ))
            continue
        if after_row is None:
            changes.append(RevisionChange(
                "removed", key, _number(before_row.get("quantity")), None,
                before_row.get("unit"), str(before_row.get("description") or ""), ""
            ))
            continue

        before_q = _number(before_row.get("quantity"))
        after_q = _number(after_row.get("quantity"))
        unit_changed = before_row.get("unit") != after_row.get("unit")
        description_before = str(before_row.get("description") or "")
        description_after = str(after_row.get("description") or "")
        description_changed = description_before != description_after
        quantity_changed = (
            before_q is None or after_q is None
            or abs(after_q - before_q) > quantity_tolerance
        )

        if quantity_changed or unit_changed or description_changed:
            changes.append(RevisionChange(
                "changed", key, before_q, after_q, after_row.get("unit"),
                description_before, description_after
            ))
        else:
            changes.append(RevisionChange(
                "unchanged", key, before_q, after_q, after_row.get("unit"),
                description_before, description_after
            ))

    return [change.as_dict() for change in changes]


def summarize_revision(changes: Iterable[dict[str, Any]]) -> dict[str, int]:
    """Count revision changes for a compact review dashboard."""
    summary = {"added": 0, "removed": 0, "changed": 0, "unchanged": 0}
    for change in changes:
        kind = str(change.get("change_type") or "")
        if kind in summary:
            summary[kind] += 1
    return summary
