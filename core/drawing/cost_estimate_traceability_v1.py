"""Deterministic cost/estimate propagation layer for P181-P190."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from typing import Mapping, Sequence

@dataclass(frozen=True)
class PriceEvidence:
    price_id: str
    boq_id: str
    unit_price: float
    currency: str
    source_ids: tuple[str, ...]
    confidence: float
    status: str = "accepted"
    def validate(self):
        if not all(x.strip() for x in (self.price_id, self.boq_id, self.currency)):
            raise ValueError("complete price evidence is required")
        if self.unit_price < 0:
            raise ValueError("unit price cannot be negative")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if self.status not in {"accepted", "review", "rejected"}:
            raise ValueError("invalid price status")
        if self.status == "accepted" and not self.source_ids:
            raise ValueError("accepted price requires source identity")
        return self

@dataclass(frozen=True)
class EstimateLineage:
    estimate_id: str
    boq_id: str
    element_id: str
    quantity: float
    unit: str
    unit_price: float
    currency: str
    amount: float
    source_ids: tuple[str, ...]
    status: str = "accepted"
    def validate(self):
        if not all(x.strip() for x in (self.estimate_id, self.boq_id, self.element_id, self.unit, self.currency)):
            raise ValueError("complete estimate lineage is required")
        if self.quantity < 0 or self.unit_price < 0 or self.amount < 0:
            raise ValueError("estimate values cannot be negative")
        if self.status not in {"accepted", "review", "rejected"}:
            raise ValueError("invalid estimate status")
        if self.status == "accepted" and not self.source_ids:
            raise ValueError("accepted estimate requires source identity")
        return self

@dataclass(frozen=True)
class EstimateImpact:
    estimate_id: str
    boq_id: str
    changed_fields: tuple[str, ...]
    old_amount: float | None
    new_amount: float | None
    impact: str
    def validate(self):
        if self.impact not in {"unchanged", "quantity_changed", "price_changed", "currency_changed",
                               "source_changed", "review_required", "removed"}:
            raise ValueError("invalid estimate impact")
        return self

class CostEstimateTraceabilityWorkflow:
    def __init__(self, *, accept_confidence: float = 0.80):
        if not 0 <= accept_confidence <= 1:
            raise ValueError("invalid confidence threshold")
        self.accept_confidence = accept_confidence

    @staticmethod
    def _id(*parts: object) -> str:
        return "est-" + sha256("|".join(str(x).strip() for x in parts).encode()).hexdigest()[:16]

    def build(
        self,
        boq_lines: Sequence[object],
        prices: Sequence[PriceEvidence],
        rows: Sequence[Mapping[str, object]],
    ) -> tuple[EstimateLineage, ...]:
        pmap = {p.boq_id: p for p in prices}
        out = []
        for row in rows:
            boq = next((x for x in boq_lines if str(getattr(x, "boq_id", "")) == str(row.get("boq_id", ""))), None)
            if boq is None:
                continue
            price = pmap.get(str(boq.boq_id))
            if price is None:
                continue
            qty = float(getattr(boq, "quantity", 0))
            unit = str(getattr(boq, "unit", "")).strip()
            unit_price = float(row.get("unit_price", price.unit_price))
            currency = str(row.get("currency", price.currency)).strip()
            confidence = float(row.get("confidence", price.confidence))
            source_ids = tuple(getattr(boq, "source_ids", ())) + tuple(price.source_ids)
            status = str(row.get("status", "accepted"))
            if not unit or not currency or not source_ids:
                status = "rejected"
            elif price.status == "rejected":
                status = "rejected"
            elif confidence < self.accept_confidence or price.status == "review":
                status = "review"
            amount = qty * unit_price
            line = EstimateLineage(
                self._id(boq.boq_id, currency),
                str(boq.boq_id),
                str(getattr(boq, "element_id", "")),
                qty, unit, unit_price, currency, amount, source_ids, status
            )
            out.append(line.validate())
        return tuple(sorted(out, key=lambda x: x.estimate_id))

    @staticmethod
    def impact(old: Sequence[EstimateLineage], new: Sequence[EstimateLineage]) -> tuple[EstimateImpact, ...]:
        a, b = {x.estimate_id: x for x in old}, {x.estimate_id: x for x in new}
        out = []
        for key in sorted(set(a) | set(b)):
            x, y = a.get(key), b.get(key)
            if x is None:
                out.append(EstimateImpact(key, y.boq_id, ("presence",), None, y.amount, "review_required"))
                continue
            if y is None:
                out.append(EstimateImpact(key, x.boq_id, ("presence",), x.amount, None, "removed"))
                continue
            changed = []
            if x.quantity != y.quantity: changed.append("quantity")
            if x.unit_price != y.unit_price: changed.append("unit_price")
            if x.currency != y.currency: changed.append("currency")
            if x.source_ids != y.source_ids: changed.append("source_ids")
            if x.status != y.status: changed.append("status")
            if "source_ids" in changed or "status" in changed: imp = "review_required"
            elif "quantity" in changed: imp = "quantity_changed"
            elif "unit_price" in changed: imp = "price_changed"
            elif "currency" in changed: imp = "currency_changed"
            else: imp = "unchanged"
            out.append(EstimateImpact(key, y.boq_id, tuple(changed), x.amount, y.amount, imp).validate())
        return tuple(out)
