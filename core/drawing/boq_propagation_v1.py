"""Deterministic BOQ propagation and revision-impact layer for P171-P180."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import math
from typing import Mapping, Sequence


@dataclass(frozen=True)
class BOQLineage:
    boq_id: str
    quantity_id: str
    element_id: str
    source_ids: tuple[str, ...]
    description: str
    quantity: float
    unit: str
    status: str = "accepted"

    def validate(self):
        if not all(isinstance(x, str) and x.strip() for x in (
            self.boq_id, self.quantity_id, self.element_id, self.unit
        )):
            raise ValueError("complete BOQ identity is required")
        if self.status == "accepted" and not self.description.strip():
            raise ValueError("accepted BOQ line requires description")
        if isinstance(self.quantity, bool):
            raise ValueError("quantity must be finite and non-negative")
        try:
            quantity = float(self.quantity)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("quantity must be finite and non-negative") from exc
        if not math.isfinite(quantity) or quantity < 0:
            raise ValueError("quantity must be finite and non-negative")
        if self.status not in {"accepted", "review", "rejected"}:
            raise ValueError("invalid BOQ status")
        if self.status == "accepted" and not self.source_ids:
            raise ValueError("accepted BOQ line requires source identity")
        if any(not isinstance(source, str) or not source.strip() for source in self.source_ids):
            raise ValueError("source identity must be non-empty")
        return self


@dataclass(frozen=True)
class BOQImpact:
    boq_id: str
    element_id: str
    changed_fields: tuple[str, ...]
    old_quantity: float | None
    new_quantity: float | None
    impact: str

    def validate(self):
        if self.impact not in {
            "unchanged", "quantity_changed", "description_changed",
            "unit_changed", "review_required", "removed"
        }:
            raise ValueError("invalid BOQ impact")
        return self


class BOQPropagationWorkflow:
    def __init__(self, *, accept_confidence=0.80):
        if isinstance(accept_confidence, bool):
            raise ValueError("invalid confidence threshold")
        try:
            threshold = float(accept_confidence)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("invalid confidence threshold") from exc
        if not math.isfinite(threshold) or not 0 <= threshold <= 1:
            raise ValueError("invalid confidence threshold")
        self.accept_confidence = threshold

    @staticmethod
    def _id(*parts):
        return "boq-" + sha256("|".join(str(x).strip() for x in parts).encode()).hexdigest()[:16]

    def build(self, quantities: Sequence[object], rows: Sequence[Mapping[str, object]]):
        qmap = {}
        for quantity in quantities:
            quantity_id = str(getattr(quantity, "quantity_id", "")).strip()
            if not quantity_id:
                raise ValueError("quantity identity is required for BOQ propagation")
            if quantity_id in qmap:
                raise ValueError(f"duplicate quantity identity: {quantity_id}")
            qmap[quantity_id] = quantity

        out = []
        seen = set()
        for row in rows:
            q = qmap.get(str(row.get("quantity_id", "")))
            if q is None:
                continue
            desc = str(row.get("description", "")).strip()
            raw_qty = row.get("quantity", getattr(q, "quantity", None))
            unit = str(row.get("unit", getattr(q, "unit", ""))).strip()
            src = tuple(sorted(set(getattr(q, "source_ids", ()))))
            raw_confidence = row.get("confidence", getattr(q, "confidence", 0))
            if isinstance(raw_confidence, bool):
                raise ValueError("confidence must be finite and between 0 and 1")
            try:
                confidence = float(raw_confidence)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("confidence must be finite and between 0 and 1") from exc
            if not math.isfinite(confidence) or not 0 <= confidence <= 1:
                raise ValueError("confidence must be finite and between 0 and 1")
            status = str(row.get("status", getattr(q, "status", "rejected")))

            if isinstance(raw_qty, bool):
                raise ValueError("quantity must be finite and non-negative")
            try:
                qty = float(raw_qty) if raw_qty is not None else None
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("quantity must be finite and non-negative") from exc
            if qty is not None and (not math.isfinite(qty) or qty < 0):
                raise ValueError("quantity must be finite and non-negative")

            if qty is None or not unit or not src or not desc:
                status = "rejected"
            elif confidence < self.accept_confidence:
                status = "review"

            line = BOQLineage(
                self._id(q.quantity_id, desc, unit), q.quantity_id, q.element_id,
                src, desc, float(qty or 0), unit, status
            )
            if line.boq_id in seen:
                raise ValueError("duplicate BOQ identity")
            seen.add(line.boq_id)
            out.append(line.validate())
        return tuple(sorted(out, key=lambda x: x.boq_id))

    @staticmethod
    def impact(old, new):
        old = tuple(x.validate() for x in old)
        new = tuple(x.validate() for x in new)
        a = {x.boq_id: x for x in old}
        b = {x.boq_id: x for x in new}
        if len(a) != len(old) or len(b) != len(new):
            raise ValueError("duplicate BOQ identity in revision")
        out = []
        for key in sorted(set(a) | set(b)):
            x, y = a.get(key), b.get(key)
            if x is None:
                out.append(BOQImpact(key, y.element_id, ("presence",), None, y.quantity, "review_required"))
                continue
            if y is None:
                out.append(BOQImpact(key, x.element_id, ("presence",), x.quantity, None, "removed"))
                continue
            changed = []
            changed += ["quantity"] if x.quantity != y.quantity else []
            changed += ["description"] if x.description != y.description else []
            changed += ["unit"] if x.unit != y.unit else []
            changed += ["source_ids"] if x.source_ids != y.source_ids else []
            changed += ["status"] if x.status != y.status else []
            impact = (
                "review_required" if ("source_ids" in changed or "status" in changed)
                else "quantity_changed" if "quantity" in changed
                else "description_changed" if "description" in changed
                else "unit_changed" if "unit" in changed
                else "unchanged"
            )
            out.append(BOQImpact(key, y.element_id, tuple(changed), x.quantity, y.quantity, impact).validate())
        return tuple(out)

    @staticmethod
    def fingerprints(lines):
        checked = tuple(x.validate() for x in lines)
        return tuple(sorted(
            "line-" + sha256("|".join((
                x.boq_id, x.quantity_id, x.element_id, x.description,
                str(x.quantity), x.unit, x.status, *x.source_ids
            )).encode()).hexdigest()[:16]
            for x in checked
        ))

    @staticmethod
    def unresolved(lines):
        return tuple(x for x in lines if x.status != "accepted")

    @staticmethod
    def source_conflicts(lines):
        by = {}
        for line in lines:
            line.validate()
            by.setdefault(line.element_id, set()).update(line.source_ids)
        return tuple(sorted(element_id for element_id, sources in by.items() if len(sources) > 1))
