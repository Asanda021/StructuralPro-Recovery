"""Canonical drawing-takeoff to BOQ bridge.

Keeps drawing provenance, confirmation state and BOQ mapping explicit.
No pricing or quantity is silently invented.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Iterable
import math

@dataclass(frozen=True)
class TakeoffBOQLink:
    takeoff_id: str
    source_ref: str
    description: str
    quantity: float
    unit: str
    boq_code: str | None = None
    confirmed: bool = False
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

class DrawingTakeoffBOQBridge:
    """Convert canonical takeoff items into auditable BOQ rows."""

    def __init__(self, price_resolver=None):
        self.price_resolver = price_resolver

    @staticmethod
    def _quantity(value: Any) -> float:
        q = float(value)
        if not math.isfinite(q) or q < 0:
            raise ValueError("quantity must be finite and non-negative")
        return q

    @staticmethod
    def _confidence(value: Any) -> float:
        c = float(value)
        if not math.isfinite(c) or not 0 <= c <= 1:
            raise ValueError("confidence must be between 0 and 1")
        return c

    def prepare(self, items: Iterable[Any]) -> list[TakeoffBOQLink]:
        out = []
        seen = set()
        for item in items:
            data = item.to_dict() if hasattr(item, "to_dict") else dict(item)
            takeoff_id = str(data.get("id") or data.get("takeoff_id") or "").strip()
            if not takeoff_id:
                raise ValueError("takeoff_id is required")
            if takeoff_id in seen:
                raise ValueError(f"duplicate takeoff_id: {takeoff_id}")
            seen.add(takeoff_id)
            source_ref = str(data.get("source_ref") or data.get("source") or "").strip()
            if not source_ref:
                raise ValueError(f"source_ref is required: {takeoff_id}")
            out.append(TakeoffBOQLink(
                takeoff_id=takeoff_id,
                source_ref=source_ref,
                description=str(data.get("label") or data.get("description") or data.get("kind") or ""),
                quantity=self._quantity(data.get("quantity", 0)),
                unit=str(data.get("unit") or "").strip(),
                boq_code=(str(data["takeoff_code"]).strip() if data.get("takeoff_code") else
                          (str(data["price_code"]).strip() if data.get("price_code") else None)),
                confirmed=bool(data.get("confirmed", not data.get("needs_confirmation", False))),
                confidence=self._confidence(data.get("confidence", 1.0)),
            ))
        return out

    def confirm(self, links: Iterable[TakeoffBOQLink], *, approved_ids: Iterable[str]) -> list[TakeoffBOQLink]:
        approved = {str(x) for x in approved_ids}
        return [
            TakeoffBOQLink(**{**x.to_dict(), "confirmed": x.takeoff_id in approved})
            for x in links
        ]

    def to_boq(self, links: Iterable[TakeoffBOQLink], *, confirmed_only: bool = True) -> list[dict[str, Any]]:
        rows = []
        for link in links:
            if confirmed_only and not link.confirmed:
                continue
            unit_price = None
            if link.boq_code and self.price_resolver:
                unit_price = self.price_resolver(link.boq_code)
                if unit_price is None:
                    raise ValueError(f"price not found: {link.boq_code}")
                unit_price = float(unit_price)
                if not math.isfinite(unit_price) or unit_price < 0:
                    raise ValueError("unit_price must be finite and non-negative")
            total = None if unit_price is None else link.quantity * unit_price
            rows.append({
                "takeoff_id": link.takeoff_id,
                "source": link.source_ref,
                "description": link.description,
                "quantity": link.quantity,
                "unit": link.unit,
                "price_code": link.boq_code,
                "unit_price": unit_price,
                "total": total,
                "confirmed": link.confirmed,
                "confidence": link.confidence,
            })
        return rows
