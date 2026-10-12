from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Iterable

@dataclass(frozen=True)
class TakeoffResult:
    kind: str
    value: float
    unit: str
    source: str = ""

def length_takeoff(length: float, count: int = 1) -> TakeoffResult:
    if length < 0 or count < 0: raise ValueError("length and count must be non-negative")
    return TakeoffResult("length", float(length) * int(count), "m")

def area_takeoff(area: float, count: int = 1) -> TakeoffResult:
    if area < 0 or count < 0: raise ValueError("area and count must be non-negative")
    return TakeoffResult("area", float(area) * int(count), "m2")

def count_takeoff(count: int) -> TakeoffResult:
    if count < 0: raise ValueError("count must be non-negative")
    return TakeoffResult("count", int(count), "count")

def perimeter_takeoff(perimeter: float, count: int = 1) -> TakeoffResult:
    if perimeter < 0 or count < 0: raise ValueError("perimeter and count must be non-negative")
    return TakeoffResult("perimeter", float(perimeter) * int(count), "m")

def depth_volume(area: float, depth: float) -> TakeoffResult:
    if area < 0 or depth < 0: raise ValueError("area and depth must be non-negative")
    return TakeoffResult("volume", area * depth, "m3")

def cutout_area(area: float, cutouts: Iterable[float]) -> TakeoffResult:
    value = area - sum(float(x) for x in cutouts)
    return TakeoffResult("area", max(0.0, value), "m2")

def legend(items: Iterable[dict[str, Any]]) -> dict[str, int]:
    out = {}
    for item in items:
        key = str(item.get("label") or item.get("symbol") or "unknown")
        out[key] = out.get(key, 0) + 1
    return out

def visual_symbol_search(symbols: Iterable[str], query: str) -> list[str]:
    q = query.casefold()
    return [s for s in symbols if q in str(s).casefold()]

def dynamic_fill(boundary_area: float, holes: Iterable[float] = ()) -> TakeoffResult:
    return cutout_area(boundary_area, holes)

def ai_count(items: Iterable[Any], expected_type: str | None = None) -> int:
    items = list(items)
    if expected_type is None: return len(items)
    return sum(1 for x in items if str(getattr(x, "kind", x)).casefold() == expected_type.casefold())

def ai_map(description: str, candidates: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    q = description.casefold()
    scored = []
    for c in candidates:
        hay = f"{c.get('code','')} {c.get('description','')}".casefold()
        score = sum(1 for token in q.split() if token and token in hay)
        if score: scored.append((score, c))
    return [c for _, c in sorted(scored, key=lambda x: x[0], reverse=True)]
