"""Project-wide revision intelligence for all building disciplines.

This layer compares already-extracted project snapshots. It is intentionally
domain-neutral: concrete, steel, masonry, architecture, MEP and other building
work can use the same revision contract. It never replaces a revision or
silently changes quantities.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping
import math

_REVIEW_TYPES = {"added", "removed", "changed"}
_NUMERIC_FIELDS = {
    "quantity": "quantity_delta",
    "concrete_quantity": "concrete_delta",
    "concrete_volume_m3": "concrete_delta",
    "rebar_weight_kg": "rebar_delta",
    "steel_weight_kg": "steel_delta",
    "total": "cost_delta",
    "cost": "cost_delta",
}


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _key(row: Mapping[str, Any]) -> str:
    for field in (
        "revision_key", "object_id", "global_id", "element_id",
        "source", "item_code", "price_code", "code",
    ):
        value = str(row.get(field) or "").strip()
        if value:
            return value
    return "|".join(
        str(row.get(field) or "").strip()
        for field in ("discipline", "member_type", "description", "unit")
    ).strip("|")


def _index(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in rows:
        row = dict(raw)
        key = _key(row)
        if key and key not in result:
            result[key] = row
    return result


def _delta(before: Mapping[str, Any] | None, after: Mapping[str, Any] | None,
           names: tuple[str, ...]) -> float | None:
    a = next((_num(before.get(n)) for n in names if before and _num(before.get(n)) is not None), None)
    b = next((_num(after.get(n)) for n in names if after and _num(after.get(n)) is not None), None)
    if a is None and b is None:
        return None
    return (b or 0.0) - (a or 0.0)


def _changed_fields(before: Mapping[str, Any], after: Mapping[str, Any],
                    tolerance: float) -> list[str]:
    ignored = {"revision", "revision_id", "revision_key"}
    fields = sorted(set(before) | set(after))
    changed = []
    for field in fields:
        if field in ignored or field in _NUMERIC_FIELDS:
            continue
        if before.get(field) != after.get(field):
            changed.append(field)
    for field in _NUMERIC_FIELDS:
        a, b = _num(before.get(field)), _num(after.get(field))
        if a is not None or b is not None:
            if a is None or b is None or abs(b - a) > tolerance:
                changed.append(field)
    return changed


def compare_project_revisions(
    before: Iterable[Mapping[str, Any]],
    after: Iterable[Mapping[str, Any]],
    *,
    before_revision: str = "",
    after_revision: str = "",
    quantity_tolerance: float = 1e-9,
    significant_quantity_threshold: float = 0.0,
) -> list[dict[str, Any]]:
    """Compare project elements and expose quantity/material/BOQ impacts.

    Inputs are generic building rows. The caller can supply concrete, steel,
    masonry, architecture, MEP, site works, or any other discipline without
    changing this API.
    """
    if quantity_tolerance < 0 or not math.isfinite(quantity_tolerance):
        raise ValueError("quantity_tolerance must be finite and non-negative")
    if significant_quantity_threshold < 0 or not math.isfinite(significant_quantity_threshold):
        raise ValueError("significant_quantity_threshold must be finite and non-negative")

    old, new = _index(before), _index(after)
    output = []
    for key in sorted(set(old) | set(new)):
        a, b = old.get(key), new.get(key)
        if a is None:
            kind = "added"
        elif b is None:
            kind = "removed"
        else:
            changed = _changed_fields(a, b, quantity_tolerance)
            kind = "changed" if changed else "unchanged"

        q_delta = _delta(a, b, ("quantity",))
        concrete_delta = _delta(a, b, ("concrete_quantity", "concrete_volume_m3"))
        rebar_delta = _delta(a, b, ("rebar_weight_kg", "rebar_quantity_kg"))
        steel_delta = _delta(a, b, ("steel_weight_kg",))
        cost_delta = _delta(a, b, ("total", "cost"))
        changed_fields = [] if a is None or b is None else _changed_fields(a, b, quantity_tolerance)
        review_required = (
            kind in _REVIEW_TYPES
            and (
                kind in {"added", "removed"}
                or abs(q_delta or 0) > significant_quantity_threshold
                or bool(concrete_delta is not None and abs(concrete_delta) > significant_quantity_threshold)
                or bool(rebar_delta is not None and abs(rebar_delta) > significant_quantity_threshold)
                or bool(steel_delta is not None and abs(steel_delta) > significant_quantity_threshold)
                or bool(cost_delta is not None and abs(cost_delta) > significant_quantity_threshold)
            )
        )
        output.append({
            "revision_key": key,
            "change_type": kind,
            "discipline": (b or a or {}).get("discipline", ""),
            "member_type": (b or a or {}).get("member_type", ""),
            "description_before": (a or {}).get("description", ""),
            "description_after": (b or a or {}).get("description", ""),
            "unit": (b or a or {}).get("unit", ""),
            "quantity_before": _num((a or {}).get("quantity")),
            "quantity_after": _num((b or {}).get("quantity")),
            "quantity_delta": q_delta,
            "concrete_delta": concrete_delta,
            "rebar_delta": rebar_delta,
            "steel_delta": steel_delta,
            "cost_delta": cost_delta,
            "changed_fields": changed_fields,
            "before_revision": before_revision,
            "after_revision": after_revision,
            "before_provenance": dict((a or {}).get("provenance") or {}),
            "after_provenance": dict((b or {}).get("provenance") or {}),
            "review_required": review_required,
            "review_status": "pending" if review_required else "not_required",
        })
    return output


def summarize_impact(changes: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = list(changes)
    return {
        "total": len(rows),
        "added": sum(r.get("change_type") == "added" for r in rows),
        "removed": sum(r.get("change_type") == "removed" for r in rows),
        "changed": sum(r.get("change_type") == "changed" for r in rows),
        "unchanged": sum(r.get("change_type") == "unchanged" for r in rows),
        "review_required": sum(bool(r.get("review_required")) for r in rows),
        "quantity_delta": sum(float(r.get("quantity_delta") or 0) for r in rows),
        "concrete_delta": sum(float(r.get("concrete_delta") or 0) for r in rows),
        "rebar_delta": sum(float(r.get("rebar_delta") or 0) for r in rows),
        "steel_delta": sum(float(r.get("steel_delta") or 0) for r in rows),
        "cost_delta": sum(float(r.get("cost_delta") or 0) for r in rows),
    }


def apply_change_review(
    changes: Iterable[Mapping[str, Any]],
    decisions: Mapping[str, bool] | None = None,
    *,
    reviewer: str = "local-user",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Apply explicit review decisions; never mutates quantities."""
    decisions = decisions or {}
    reviewed, audit = [], []
    for row in changes:
        item = dict(row)
        key = str(item.get("revision_key") or "")
        required = bool(item.get("review_required"))
        if required:
            if key not in decisions:
                status = "pending"
                accepted = False
            else:
                accepted = decisions[key] is True
                status = "approved" if accepted else "rejected"
        else:
            accepted = decisions.get(key, True) is True
            status = "approved" if accepted else "rejected"
        item["review_status"] = status
        item["reviewer"] = str(reviewer or "local-user")
        reviewed.append(item)
        audit.append({
            "revision_key": key,
            "decision": status,
            "reviewer": str(reviewer or "local-user"),
            "before_revision": item.get("before_revision", ""),
            "after_revision": item.get("after_revision", ""),
        })
    return reviewed, audit


def boq_revision_impact(
    before_boq: Iterable[Mapping[str, Any]],
    after_boq: Iterable[Mapping[str, Any]],
    *,
    quantity_tolerance: float = 1e-9,
) -> dict[str, Any]:
    """Compare BOQ lines separately so drawing/model changes remain traceable."""
    changes = compare_project_revisions(
        before_boq, after_boq, quantity_tolerance=quantity_tolerance,
    )
    return {
        "changes": changes,
        "summary": summarize_impact(changes),
        "finalizable_after_review": not any(
            r.get("review_required") and r.get("review_status") != "approved"
            for r in changes
        ),
    }


def build_revision_history(
    snapshots: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Build deterministic revision history without replacing earlier snapshots."""
    history = [dict(x) for x in snapshots]
    history.sort(key=lambda x: (str(x.get("revision") or ""), str(x.get("created_at") or "")))
    return history


@dataclass(frozen=True)
class RevisionReportRow:
    """RTL-ready report record; presentation can render it right-to-left."""
    change_type: str
    revision_key: str
    discipline: str
    description: str
    quantity_delta: float | None
    material_delta: float | None
    cost_delta: float | None
    review_status: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def to_rtl_report_rows(changes: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Create stable report rows; no UI direction is imposed here."""
    result = []
    labels = {
        "added": "افزوده‌شده",
        "removed": "حذف‌شده",
        "changed": "تغییرکرده",
        "unchanged": "بدون تغییر",
    }
    for row in changes:
        material = row.get("concrete_delta")
        if material is None:
            material = row.get("rebar_delta")
        if material is None:
            material = row.get("steel_delta")
        result.append(RevisionReportRow(
            change_type=labels.get(str(row.get("change_type")), str(row.get("change_type") or "")),
            revision_key=str(row.get("revision_key") or ""),
            discipline=str(row.get("discipline") or ""),
            description=str(row.get("description_after") or row.get("description_before") or ""),
            quantity_delta=_num(row.get("quantity_delta")),
            material_delta=_num(material),
            cost_delta=_num(row.get("cost_delta")),
            review_status=str(row.get("review_status") or ""),
        ).as_dict())
    return result
