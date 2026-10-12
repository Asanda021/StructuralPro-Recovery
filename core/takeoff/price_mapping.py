"""Offline mapping from takeoff quantities to price-list items.

Stage 3: exact code matches, explicit overrides, then conservative text/unit
matching.  Ambiguous matches are returned for user confirmation rather than
silently assigning a price.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import re
from typing import Any, Iterable

from ..pricing.catalog import PriceCatalog, PriceItem

_UNIT_ALIASES = {
    "m": {"m", "م", "متر"},
    "m2": {"m2", "m²", "م2", "مترمربع", "مترمربع"},
    "m3": {"m3", "m³", "م3", "مترمکعب"},
    "kg": {"kg", "کیلو", "کیلوگرم"},
    "عدد": {"عدد", "pcs", "piece", "count"},
}

def normalize_text(value: Any) -> str:
    s = str(value or "").strip().casefold()
    s = s.replace("ي", "ی").replace("ك", "ک")
    s = re.sub(r"\s+", " ", s)
    return s

def units_compatible(a: str, b: str) -> bool:
    a, b = normalize_text(a), normalize_text(b)
    if a == b:
        return True
    for values in _UNIT_ALIASES.values():
        if a in values and b in values:
            return True
    return False

@dataclass(frozen=True)
class MappingCandidate:
    price_code: str
    description: str
    unit: str
    score: float
    reason: str

class PriceMapper:
    def __init__(self, catalog: PriceCatalog):
        self.catalog = catalog

    def candidates(self, description: str, unit: str, year: int,
                   *, limit: int = 5) -> list[MappingCandidate]:
        q = normalize_text(description)
        if not q:
            return []
        tokens = {x for x in re.split(r"\W+", q) if len(x) > 1}
        scored: list[MappingCandidate] = []
        for item in self.catalog.search("", year=year, limit=100000):
            if not units_compatible(unit, item.unit):
                continue
            text = normalize_text(item.description)
            item_tokens = {x for x in re.split(r"\W+", text) if len(x) > 1}
            overlap = len(tokens & item_tokens)
            contains = 1.0 if q in text or text in q else 0.0
            score = contains * 0.65 + (overlap / max(1, len(tokens))) * 0.35
            if score > 0:
                scored.append(MappingCandidate(item.code, item.description, item.unit,
                                                round(score, 4), "text+unit"))
        scored.sort(key=lambda x: (-x.score, x.price_code))
        return scored[:max(1, limit)]

    def map_row(self, row: dict[str, Any], year: int,
                *, override_code: str | None = None) -> dict[str, Any]:
        code = override_code or row.get("price_code")
        if code:
            item = self.catalog.get(str(code), year)
            if item:
                if not units_compatible(str(row.get("unit", "")), item.unit):
                    return {"status": "unit_mismatch", "row": row, "item": asdict(item)}
                return {"status": "exact", "row": row, "item": asdict(item), "score": 1.0}
            if override_code:
                return {"status": "code_not_found", "row": row, "code": code}
        candidates = self.candidates(str(row.get("description", "")), str(row.get("unit", "")), year)
        if not candidates:
            return {"status": "unmatched", "row": row, "candidates": []}
        if len(candidates) == 1 or candidates[0].score >= 0.9:
            return {"status": "suggested", "row": row, "candidate": asdict(candidates[0]),
                    "candidates": [asdict(x) for x in candidates]}
        return {"status": "ambiguous", "row": row,
                "candidates": [asdict(x) for x in candidates]}

    def price_rows(self, rows: Iterable[dict[str, Any]], year: int) -> list[dict[str, Any]]:
        out = []
        for row in rows:
            result = self.map_row(row, year)
            item = result.get("item") or result.get("candidate")
            priced = dict(row)
            if item:
                priced["price_code"] = item["code"]
                priced["unit_price"] = item.get("unit_price")
                priced["mapping_status"] = result["status"]
                priced["total"] = float(row.get("quantity", 0) or 0) * float(item.get("unit_price", 0) or 0)
            else:
                priced["mapping_status"] = result["status"]
            out.append(priced)
        return out
