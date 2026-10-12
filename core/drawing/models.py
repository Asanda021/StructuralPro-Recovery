"""Normalized drawing entities used by Drawing Intelligence."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Mapping

@dataclass(frozen=True)
class DrawingPrimitive:
    kind: str
    x: float = 0.0
    y: float = 0.0
    x2: float = 0.0
    y2: float = 0.0
    width: float = 0.0
    height: float = 0.0
    text: str = ""
    layer: str = ""
    source_id: str = ""
    properties: Mapping[str, object] = field(default_factory=dict)

    def normalized_kind(self) -> str:
        return self.kind.strip().casefold()

@dataclass(frozen=True)
class EngineeringElement:
    element_id: str
    domain: str
    kind: str
    source_ids: tuple[str, ...]
    geometry: Mapping[str, float]
    confidence: float
    evidence: tuple[str, ...] = ()
    properties: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> "EngineeringElement":
        if not self.element_id.strip(): raise ValueError("element_id is required")
        if not self.domain.strip(): raise ValueError("domain is required")
        if not self.kind.strip(): raise ValueError("kind is required")
        if not 0.0 <= self.confidence <= 1.0: raise ValueError("confidence must be between 0 and 1")
        return self
