"""Discipline-neutral measurement primitives for every AEC trade."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any
import math

@dataclass(frozen=True)
class GenericMeasurement:
    discipline: str
    measurement_type: str
    quantity: float
    unit: str
    formula: str
    source: str = "manual"
    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

def _n(value: Any, name: str) -> float:
    x = float(value)
    if not math.isfinite(x) or x < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return x

def measure(discipline: str, measurement_type: str, *, length: float = 0,
            width: float = 0, height: float = 0, depth: float = 0,
            count: float = 1, weight: float = 0, radius: float = 0,
            source: str = "manual") -> GenericMeasurement:
    d = str(discipline or "").strip().casefold()
    t = str(measurement_type or "").strip().casefold()
    if not d:
        raise ValueError("discipline is required")
    if t == "length":
        q = _n(length, "length"); return GenericMeasurement(d,t,q,"m","L",source)
    if t == "area":
        q = _n(length,"length") * _n(width,"width"); return GenericMeasurement(d,t,q,"m2","L×W",source)
    if t == "volume":
        q = _n(length,"length") * _n(width,"width") * _n(height or depth,"height"); return GenericMeasurement(d,t,q,"m3","L×W×H",source)
    if t == "count":
        q = _n(count,"count"); return GenericMeasurement(d,t,q,"عدد","N",source)
    if t == "weight":
        q = _n(weight,"weight"); return GenericMeasurement(d,t,q,"kg","W",source)
    if t == "perimeter":
        q = 2 * (_n(length,"length") + _n(width,"width")); return GenericMeasurement(d,t,q,"m","2×(L+W)",source)
    if t == "radius":
        q = _n(radius,"radius"); return GenericMeasurement(d,t,q,"m","R",source)
    raise KeyError(f"unsupported measurement type: {measurement_type}")
