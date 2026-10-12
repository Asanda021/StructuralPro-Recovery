"""Typed construction element model for deterministic quantity takeoff.

This layer describes what is being measured; it deliberately contains no
structural design assumptions. Missing dimensions are rejected rather than
guessed.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import math

def _finite(value: float, name: str, minimum: float = 0.0) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(x) or x < minimum:
        raise ValueError(f"{name} must be finite and >= {minimum}")
    return x

@dataclass(frozen=True)
class ConstructionElement:
    id: str
    kind: str
    quantity_count: float = 1.0
    length_m: float | None = None
    width_m: float | None = None
    height_m: float | None = None
    thickness_m: float | None = None
    area_m2: float | None = None
    source_id: str = "manual"
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if not str(self.id).strip():
            raise ValueError("element id is required")
        if not str(self.kind).strip():
            raise ValueError("element kind is required")
        object.__setattr__(self, "quantity_count", _finite(self.quantity_count, "quantity_count"))
        for name in ("length_m", "width_m", "height_m", "thickness_m", "area_m2"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _finite(value, name))
        if not str(self.source_id).strip():
            raise ValueError("source_id is required")
