"""Deterministic revision diff engine with fail-closed comparison semantics.

Compares two project snapshots without mutating either input. The engine is
domain-neutral: drawing/model/takeoff/BOQ/estimate records are supplied by
existing pipelines and retain their source identifiers for impact tracing.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Iterable, Mapping
import math


_MISSING = object()


def _records(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        return [dict(value)]
    return [dict(x) if isinstance(x, Mapping) else dict(vars(x)) for x in value]


def _key(row: Mapping[str, Any], index: int, preferred: tuple[str, ...]) -> str:
    for field in preferred:
        value = str(row.get(field) or "").strip()
        if value:
            return value
    return f"__index_{index}"


def _safe_number(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    x = float(value)
    if not math.isfinite(x):
        raise ValueError("revision numeric value must be finite")
    return x


def _diff_records(
    old: Iterable[Mapping[str, Any]],
    new: Iterable[Mapping[str, Any]],
    *,
    key_fields: tuple[str, ...],
    quantity_fields: tuple[str, ...] = (),
) -> dict[str, Any]:
    old_rows = _records(old)
    new_rows = _records(new)
    before = {_key(row, i, key_fields): row for i, row in enumerate(old_rows)}
    after = {_key(row, i, key_fields): row for i, row in enumerate(new_rows)}
    added, removed, changed = [], [], []

    for key in sorted(after.keys() - before.keys()):
        added.append({"key": key, "after": after[key]})
    for key in sorted(before.keys() - after.keys()):
        removed.append({"key": key, "before": before[key]})
    for key in sorted(before.keys() & after.keys()):
        a, b = before[key], after[key]
        field_changes = []
        for field in sorted(set(a) | set(b)):
            av, bv = a.get(field, _MISSING), b.get(field, _MISSING)
            if av != bv:
                field_changes.append({
                    "field": field,
                    "before": None if av is _MISSING else av,
                    "after": None if bv is _MISSING else bv,
                })
        if field_changes:
            quantity_changes = []
            for field in quantity_fields:
                av = _safe_number(a.get(field), 0.0)
                bv = _safe_number(b.get(field), 0.0)
                if av != bv:
                    quantity_changes.append({
                        "field": field,
                        "before": av,
                        "after": bv,
                        "delta": bv - av,
                    })
            changed.append({
                "key": key,
                "changes": field_changes,
                "quantity_changes": quantity_changes,
            })
    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "counts": {
            "before": len(before),
            "after": len(after),
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
        },
    }


def _drawing_diff(old: Iterable[Mapping[str, Any]], new: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    return _diff_records(old, new, key_fields=("source_id", "id", "external_id"),
                         quantity_fields=("length", "area", "volume"))


def _element_diff(old: Iterable[Mapping[str, Any]], new: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    return _diff_records(old, new, key_fields=("element_id", "id", "GlobalId", "global_id", "source_id"),
                         quantity_fields=("quantity", "volume", "area"))


def _takeoff_diff(old: Iterable[Mapping[str, Any]], new: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    return _diff_records(old, new, key_fields=("element_id", "source_id", "id"),
                         quantity_fields=("quantity", "effective_quantity"))


def _boq_diff(old: Iterable[Mapping[str, Any]], new: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    return _diff_records(old, new, key_fields=("price_code", "item_code", "source_id", "description"),
                         quantity_fields=("quantity", "effective_quantity", "total"))


def _estimate_diff(old: Mapping[str, Any], new: Mapping[str, Any]) -> dict[str, Any]:
    old_cost = dict(old.get("cost") or {})
    new_cost = dict(new.get("cost") or {})
    old_total = _safe_number(old_cost.get("grand_total"), 0)
    new_total = _safe_number(new_cost.get("grand_total"), 0)
    return {
        "before_total": old_total,
        "after_total": new_total,
        "delta": new_total - old_total,
        "delta_percent": 0.0 if old_total == 0 else (new_total - old_total) / old_total * 100.0,
        "factor_changes": _diff_records(
            [{"key": k, "rate": v} for k, v in (old.get("factors") or {}).items()],
            [{"key": k, "rate": v} for k, v in (new.get("factors") or {}).items()],
            key_fields=("key",),
            quantity_fields=("rate",),
        ),
    }


def _impact(revision: dict[str, Any]) -> dict[str, Any]:
    boq = revision["boq"]
    takeoff = revision["takeoff"]
    elements = revision["elements"]
    return {
        "drawing_changes": revision["drawing"]["counts"],
        "element_changes": elements["counts"],
        "takeoff_changes": takeoff["counts"],
        "boq_changes": boq["counts"],
        "cost_delta": revision["estimate"]["delta"],
        "affected": any(
            section["counts"]["added"] or section["counts"]["removed"] or section["counts"]["changed"]
            for section in (revision["drawing"], elements, takeoff, boq)
        ) or revision["estimate"]["delta"] != 0,
    }


@dataclass(frozen=True)
class RevisionResult:
    revision_id: str
    drawing: dict[str, Any]
    elements: dict[str, Any]
    takeoff: dict[str, Any]
    boq: dict[str, Any]
    estimate: dict[str, Any]
    impact: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class RevisionEngine:
    """Compare two snapshots and produce a traceable revision impact report."""

    def compare(
        self,
        old: Mapping[str, Any],
        new: Mapping[str, Any],
        *,
        revision_id: str = "revision",
    ) -> RevisionResult:
        if not isinstance(old, Mapping) or not isinstance(new, Mapping):
            raise TypeError("revision snapshots must be mappings")
        rid = str(revision_id).strip()
        if not rid:
            raise ValueError("revision_id is required")
        drawing = _drawing_diff(old.get("drawing", ()), new.get("drawing", ()))
        elements = _element_diff(old.get("elements", ()), new.get("elements", ()))
        takeoff = _takeoff_diff(old.get("takeoff", ()), new.get("takeoff", ()))
        boq = _boq_diff(old.get("boq", ()), new.get("boq", ()))
        estimate = _estimate_diff(dict(old.get("estimate") or {}),
                                  dict(new.get("estimate") or {}))
        result = {
            "drawing": drawing, "elements": elements, "takeoff": takeoff,
            "boq": boq, "estimate": estimate,
        }
        return RevisionResult(
            revision_id=rid,
            drawing=drawing,
            elements=elements,
            takeoff=takeoff,
            boq=boq,
            estimate=estimate,
            impact=_impact(result),
        )
