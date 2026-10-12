"""P42 — domain-neutral revision intelligence and BOQ impact.

Evidence-first comparison for all building/civil disciplines. The caller supplies
the extracted snapshots; this layer never invents geometry, quantities or costs.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from decimal import Decimal
from hashlib import sha256
import json
from typing import Iterable, Mapping


@dataclass(frozen=True)
class RevisionElement:
    project_id: str
    revision: str
    element_id: str
    discipline: str
    member_type: str
    description: str
    source_id: str
    quantity: Decimal
    unit: str
    dimensions: tuple[tuple[str, Decimal], ...] = ()
    count: Decimal = Decimal("1")
    rebar_weight_kg: Decimal | None = None
    boq_quantity: Decimal | None = None
    boq_item_code: str = ""

    def validate(self) -> None:
        required = (
            self.project_id, self.revision, self.element_id, self.discipline,
            self.member_type, self.description, self.source_id, self.unit,
        )
        if any(not isinstance(v, str) or not v.strip() for v in required):
            raise ValueError("revision element identity/provenance is incomplete")
        for value, label in ((self.quantity, "quantity"), (self.count, "count")):
            if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
                raise ValueError(f"{label} must be a finite non-negative Decimal")
        if self.rebar_weight_kg is not None and (
            not isinstance(self.rebar_weight_kg, Decimal)
            or not self.rebar_weight_kg.is_finite()
            or self.rebar_weight_kg < 0
        ):
            raise ValueError("rebar_weight_kg must be a finite non-negative Decimal")
        if self.boq_quantity is not None and (
            not isinstance(self.boq_quantity, Decimal)
            or not self.boq_quantity.is_finite()
            or self.boq_quantity < 0
        ):
            raise ValueError("boq_quantity must be a finite non-negative Decimal")
        for name, value in self.dimensions:
            if not isinstance(name, str) or not name.strip():
                raise ValueError("dimension name is required")
            if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
                raise ValueError("dimensions must be finite non-negative Decimals")


@dataclass(frozen=True)
class RevisionChange:
    element_id: str
    change_type: str
    discipline: str
    member_type_before: str
    member_type_after: str
    quantity_delta: Decimal
    count_delta: Decimal
    rebar_delta_kg: Decimal
    boq_delta: Decimal
    dimension_changes: tuple[tuple[str, Decimal, Decimal], ...]
    changed_fields: tuple[str, ...]
    source_before: str | None
    source_after: str | None
    review_required: bool


def _index(rows: Iterable[RevisionElement], revision: str, project_id: str) -> dict[str, RevisionElement]:
    result: dict[str, RevisionElement] = {}
    for row in rows:
        row.validate()
        if row.revision != revision:
            raise ValueError("snapshot revision mismatch")
        if row.project_id != project_id:
            raise ValueError("snapshot project mismatch")
        if row.element_id in result:
            raise ValueError(f"duplicate element id: {row.element_id}")
        result[row.element_id] = row
    return result


def _dimensions(row: RevisionElement | None) -> dict[str, Decimal]:
    return dict(row.dimensions) if row else {}


def _dec(value: Decimal | None) -> Decimal:
    return value if value is not None else Decimal("0")


def compare_revision_elements(
    before: Iterable[RevisionElement],
    after: Iterable[RevisionElement],
    *,
    project_id: str,
    before_revision: str,
    after_revision: str,
    tolerance: Decimal = Decimal("0"),
) -> tuple[RevisionChange, ...]:
    """Return deterministic added/removed/modified changes from explicit evidence."""
    if not project_id.strip() or not before_revision.strip() or not after_revision.strip():
        raise ValueError("project and revision identities are required")
    if before_revision == after_revision:
        raise ValueError("before and after revisions must differ")
    if not isinstance(tolerance, Decimal) or not tolerance.is_finite() or tolerance < 0:
        raise ValueError("tolerance must be a finite non-negative Decimal")

    old = tuple(before)
    new = tuple(after)
    all_rows = old + new
    if any(row.project_id != project_id for row in all_rows):
        raise ValueError("snapshot project mismatch")
    old_map = _index(old, before_revision, project_id)
    new_map = _index(new, after_revision, project_id)

    result: list[RevisionChange] = []
    for element_id in sorted(set(old_map) | set(new_map)):
        a, b = old_map.get(element_id), new_map.get(element_id)
        if a is None:
            result.append(RevisionChange(
                element_id=element_id, change_type="added",
                discipline=b.discipline, member_type_before="", member_type_after=b.member_type,
                quantity_delta=b.quantity, count_delta=b.count,
                rebar_delta_kg=_dec(b.rebar_weight_kg), boq_delta=_dec(b.boq_quantity),
                dimension_changes=tuple((k, Decimal("0"), v) for k, v in sorted(_dimensions(b).items())),
                changed_fields=("element",), source_before=None, source_after=b.source_id,
                review_required=True,
            ))
            continue
        if b is None:
            result.append(RevisionChange(
                element_id=element_id, change_type="removed",
                discipline=a.discipline, member_type_before=a.member_type, member_type_after="",
                quantity_delta=-a.quantity, count_delta=-a.count,
                rebar_delta_kg=-_dec(a.rebar_weight_kg), boq_delta=-_dec(a.boq_quantity),
                dimension_changes=tuple((k, v, Decimal("0")) for k, v in sorted(_dimensions(a).items())),
                changed_fields=("element",), source_before=a.source_id, source_after=None,
                review_required=True,
            ))
            continue

        old_dim, new_dim = _dimensions(a), _dimensions(b)
        dim_changes = tuple(
            (k, old_dim.get(k, Decimal("0")), new_dim.get(k, Decimal("0")))
            for k in sorted(set(old_dim) | set(new_dim))
            if abs(new_dim.get(k, Decimal("0")) - old_dim.get(k, Decimal("0"))) > tolerance
        )
        fields = []
        if a.discipline != b.discipline: fields.append("discipline")
        if a.member_type != b.member_type: fields.append("member_type")
        if a.description != b.description: fields.append("description")
        if a.unit != b.unit: fields.append("unit")
        if abs(b.quantity - a.quantity) > tolerance: fields.append("quantity")
        if abs(b.count - a.count) > tolerance: fields.append("count")
        if abs(_dec(b.rebar_weight_kg) - _dec(a.rebar_weight_kg)) > tolerance: fields.append("rebar_weight_kg")
        if abs(_dec(b.boq_quantity) - _dec(a.boq_quantity)) > tolerance: fields.append("boq_quantity")
        if a.boq_item_code != b.boq_item_code: fields.append("boq_item_code")
        if dim_changes: fields.append("dimensions")
        if not fields:
            continue
        result.append(RevisionChange(
            element_id=element_id, change_type="modified",
            discipline=b.discipline, member_type_before=a.member_type, member_type_after=b.member_type,
            quantity_delta=b.quantity - a.quantity, count_delta=b.count - a.count,
            rebar_delta_kg=_dec(b.rebar_weight_kg) - _dec(a.rebar_weight_kg),
            boq_delta=_dec(b.boq_quantity) - _dec(a.boq_quantity),
            dimension_changes=dim_changes, changed_fields=tuple(fields),
            source_before=a.source_id, source_after=b.source_id,
            review_required=True,
        ))
    return tuple(result)


def summarize_revision(changes: Iterable[RevisionChange]) -> dict[str, object]:
    rows = tuple(changes)
    return {
        "total_changes": len(rows),
        "added": sum(r.change_type == "added" for r in rows),
        "removed": sum(r.change_type == "removed" for r in rows),
        "modified": sum(r.change_type == "modified" for r in rows),
        "quantity_delta": sum((r.quantity_delta for r in rows), Decimal("0")),
        "count_delta": sum((r.count_delta for r in rows), Decimal("0")),
        "rebar_delta_kg": sum((r.rebar_delta_kg for r in rows), Decimal("0")),
        "boq_delta": sum((r.boq_delta for r in rows), Decimal("0")),
        "review_required": sum(bool(r.review_required) for r in rows),
    }


def revision_fingerprint(changes: Iterable[RevisionChange]) -> str:
    rows = [asdict(x) for x in changes]

    def normalize(value: object) -> object:
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, tuple):
            return [normalize(x) for x in value]
        if isinstance(value, list):
            return [normalize(x) for x in value]
        if isinstance(value, dict):
            return {k: normalize(v) for k, v in value.items()}
        return value

    canonical = json.dumps(normalize(rows), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()
