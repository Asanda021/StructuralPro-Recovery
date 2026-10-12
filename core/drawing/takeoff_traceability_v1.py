"""Production takeoff traceability and revision-impact contracts.

This layer turns already-recognized drawing elements and quantity candidates into
explicit, deterministic, auditable links. It never invents engineering values.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Mapping, Sequence


@dataclass(frozen=True)
class QuantityEvidence:
    quantity_id: str
    element_id: str
    source_ids: tuple[str, ...]
    quantity: float | None
    unit: str
    confidence: float
    formula: str
    status: str
    warnings: tuple[str, ...] = ()

    def validate(self) -> "QuantityEvidence":
        if not self.quantity_id.strip() or not self.element_id.strip():
            raise ValueError("quantity and element identity are required")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.status not in {"accepted", "review", "rejected"}:
            raise ValueError("invalid quantity status")
        if self.status == "accepted" and (self.quantity is None or not self.unit.strip()):
            raise ValueError("accepted quantity requires value and unit")
        return self


@dataclass(frozen=True)
class TraceLink:
    parent_id: str
    child_id: str
    relation: str

    def validate(self) -> "TraceLink":
        if not self.parent_id.strip() or not self.child_id.strip() or not self.relation.strip():
            raise ValueError("trace link fields are required")
        return self


@dataclass(frozen=True)
class RevisionImpact:
    element_id: str
    source_ids: tuple[str, ...]
    changed_fields: tuple[str, ...]
    old_quantity: float | None
    new_quantity: float | None
    old_unit: str
    new_unit: str
    impact: str

    def validate(self) -> "RevisionImpact":
        if self.impact not in {"unchanged", "quantity_changed", "source_changed", "review_required"}:
            raise ValueError("invalid revision impact")
        return self


class TakeoffTraceabilityWorkflow:
    """Build deterministic source -> element -> quantity -> BOQ lineage."""

    def __init__(self, *, accept_confidence: float = 0.80) -> None:
        if not 0.0 <= accept_confidence <= 1.0:
            raise ValueError("accept_confidence must be between 0 and 1")
        self.accept_confidence = accept_confidence

    @staticmethod
    def _id(prefix: str, *parts: object) -> str:
        raw = "|".join(str(p).strip() for p in parts)
        return f"{prefix}-{sha256(raw.encode('utf-8')).hexdigest()[:16]}"

    def evaluate(self, element, candidate: Mapping[str, object]) -> QuantityEvidence:
        source_ids = tuple(sorted({str(x).strip() for x in getattr(element, "source_ids", ()) if str(x).strip()}))
        warnings = [str(x) for x in candidate.get("warnings", ()) if str(x)]
        quantity = candidate.get("quantity")
        unit = str(candidate.get("unit") or "").strip()
        formula = str(candidate.get("formula") or "").strip()
        confidence = float(candidate.get("confidence", getattr(element, "confidence", 0.0)))
        if not source_ids:
            warnings.append("منبع نقشه برای ردیابی معتبر وجود ندارد")
        if quantity is None:
            warnings.append("مقدار متره موجود نیست")
        if not unit:
            warnings.append("واحد متره موجود نیست")
        if confidence < self.accept_confidence:
            warnings.append("اعتماد کمتر از آستانه پذیرش است")
        status = "accepted"
        if not source_ids or quantity is None or not unit:
            status = "rejected"
        elif confidence < self.accept_confidence:
            status = "review"
        qid = self._id("qty", element.element_id, *source_ids, quantity, unit, formula)
        return QuantityEvidence(qid, element.element_id, source_ids, quantity if isinstance(quantity, (int, float)) else None,
                                unit, confidence, formula, status, tuple(dict.fromkeys(warnings))).validate()

    def build(self, elements: Sequence[object], candidates: Sequence[Mapping[str, object]],
              boq_rows: Sequence[Mapping[str, object]] = ()) -> tuple[tuple[QuantityEvidence, ...], tuple[TraceLink, ...]]:
        by_element = {str(c["element_id"]): c for c in candidates if "element_id" in c}
        quantities = []
        links = []
        for element in sorted(elements, key=lambda e: str(e.element_id)):
            candidate = by_element.get(str(element.element_id), {"element_id": element.element_id})
            evidence = self.evaluate(element, candidate)
            quantities.append(evidence)
            for source_id in evidence.source_ids:
                links.append(TraceLink(source_id, element.element_id, "source_to_element").validate())
            links.append(TraceLink(element.element_id, evidence.quantity_id, "element_to_quantity").validate())
        accepted = {q.element_id: q for q in quantities if q.status == "accepted"}
        for row in boq_rows:
            source = str(row.get("source") or "").strip()
            if not source:
                continue
            q = accepted.get(source)
            if q is not None:
                links.append(TraceLink(q.quantity_id, self._id("boq", source, row.get("quantity"), row.get("unit")),
                                       "quantity_to_boq").validate())
        unique = {(x.parent_id, x.child_id, x.relation): x for x in links}
        return tuple(quantities), tuple(unique[k] for k in sorted(unique))

    @staticmethod
    def revision_impact(old: Sequence[QuantityEvidence], new: Sequence[QuantityEvidence]) -> tuple[RevisionImpact, ...]:
        old_by = {x.element_id: x for x in old}
        new_by = {x.element_id: x for x in new}
        impacts = []
        for element_id in sorted(set(old_by) | set(new_by)):
            a, b = old_by.get(element_id), new_by.get(element_id)
            if a is None or b is None:
                impacts.append(RevisionImpact(element_id, (b or a).source_ids, ("presence",),
                                               a.quantity if a else None, b.quantity if b else None,
                                               a.unit if a else "", b.unit if b else "", "review_required"))
                continue
            changed = []
            if a.quantity != b.quantity:
                changed.append("quantity")
            if a.unit != b.unit:
                changed.append("unit")
            if a.source_ids != b.source_ids:
                changed.append("source_ids")
            if a.status != b.status:
                changed.append("status")
            if "source_ids" in changed:
                impact = "source_changed"
            elif "quantity" in changed or "unit" in changed:
                impact = "quantity_changed"
            elif "status" in changed and b.status != "accepted":
                impact = "review_required"
            else:
                impact = "unchanged"
            impacts.append(RevisionImpact(element_id, b.source_ids, tuple(changed),
                                           a.quantity, b.quantity, a.unit, b.unit, impact))
        return tuple(x.validate() for x in impacts)
