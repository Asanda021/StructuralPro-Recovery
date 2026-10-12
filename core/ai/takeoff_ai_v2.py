"""P38 AI Takeoff 2.0 — deterministic drawing-evidence extraction and learning feedback.

AI may detect/propose; deterministic rules validate geometry; human review remains
mandatory. This module adds component/dimension recognition, rebar awareness and
a traceable feedback record without inventing missing quantities.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
import re
from typing import Any, Iterable, Mapping

from .takeoff_ai_v1 import AITakeoffCandidate, propose_takeoff
from .takeoff_intelligence_v1 import group_candidates, normalize_drawing_text
from .takeoff_production_v1 import ProductionTakeoffPackage, build_production_takeoff


COMPONENT_TERMS: dict[str, tuple[str, ...]] = {
    "wall": ("wall", "walls", "دیوار"),
    "column": ("column", "columns", "col", "ستون"),
    "beam": ("beam", "beams", "تیر"),
    "slab": ("slab", "floor", "roof", "دال", "سقف"),
    "footing": ("footing", "foundation", "پی", "فونداسیون"),
    "door": ("door", "doors", "در"),
    "window": ("window", "windows", "پنجره"),
    "rebar": ("rebar", "reinforcement", "bar", "میلگرد", "آرماتور", "خاموت", "سنجاقی"),
}

DIMENSION_PATTERN = re.compile(
    r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>mm|cm|m)\b", re.I
)


@dataclass(frozen=True)
class DetectedDimension:
    source_id: str
    value: float
    unit: str
    axis: str | None = None
    confidence: float = 0.90

    def __post_init__(self) -> None:
        if not self.source_id or not math.isfinite(self.value) or self.value <= 0:
            raise ValueError("valid source_id and positive finite dimension are required")
        if self.unit not in {"mm", "cm", "m"}:
            raise ValueError("unsupported dimension unit")
        if not 0 < self.confidence <= 1:
            raise ValueError("confidence must be in (0, 1]")


@dataclass(frozen=True)
class AITakeoffFeedback:
    candidate_id: str
    reviewer_id: str
    outcome: str
    correction: str
    source_fingerprint: str

    def __post_init__(self) -> None:
        if self.outcome not in {"accepted", "rejected", "corrected"}:
            raise ValueError("invalid feedback outcome")
        if not self.candidate_id or not self.reviewer_id.strip() or not self.source_fingerprint:
            raise ValueError("feedback provenance is required")


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _source_id(entity: Any, index: int) -> str:
    data = getattr(entity, "data", None)
    data = data if isinstance(data, Mapping) else {}
    value = data.get("source_id") or getattr(entity, "source_id", None) or data.get("global_id") or data.get("id")
    return str(value).strip() if value else f"entity-{index + 1}"


def detect_components(entities: Iterable[Any]) -> list[tuple[str, str, float]]:
    """Return unambiguous component proposals as (source_id, type, confidence)."""
    result: list[tuple[str, str, float]] = []
    for index, entity in enumerate(entities):
        data = getattr(entity, "data", None)
        data = data if isinstance(data, Mapping) else {}
        text = normalize_drawing_text(" ".join(
            str(value) for value in (
                getattr(entity, "layer", None),
                getattr(entity, "entity_type", None),
                data.get("text"), data.get("name"), data.get("block"),
                data.get("block_name"), data.get("ifc_type"),
            ) if value
        ))
        matches = [
            kind for kind, terms in COMPONENT_TERMS.items()
            if any(normalize_drawing_text(term) in text for term in terms)
        ]
        if len(matches) == 1:
            result.append((_source_id(entity, index), matches[0], 0.92))
    return result


def extract_dimensions(entities: Iterable[Any]) -> list[DetectedDimension]:
    """Extract only dimensions whose source explicitly contains a unit."""
    result: list[DetectedDimension] = []
    for index, entity in enumerate(entities):
        data = getattr(entity, "data", None)
        data = data if isinstance(data, Mapping) else {}
        source = _source_id(entity, index)
        for raw in (data.get("text"), data.get("dimension"), getattr(entity, "text", None)):
            if not raw:
                continue
            text = normalize_drawing_text(raw).replace(",", ".")
            for match in DIMENSION_PATTERN.finditer(text):
                result.append(
                    DetectedDimension(
                        source,
                        float(match.group("value")),
                        match.group("unit").lower(),
                    )
                )
    return result


def build_ai_takeoff_2_package(
    entities: Iterable[Any],
    *,
    source_fingerprint: str,
    minimum_confidence: float = 0.70,
) -> tuple[ProductionTakeoffPackage, tuple[DetectedDimension, ...]]:
    """Run P38 detection through the existing P23-P25 production gates."""
    if not source_fingerprint.strip():
        raise ValueError("source_fingerprint is required")
    materialized = tuple(entities)
    candidates = propose_takeoff(materialized)
    package = build_production_takeoff(
        group_candidates(candidates),
        minimum_confidence=minimum_confidence,
    )
    return package, tuple(extract_dimensions(materialized))


def create_feedback(
    candidate: AITakeoffCandidate,
    *,
    reviewer_id: str,
    outcome: str,
    correction: str = "",
    source_fingerprint: str,
) -> AITakeoffFeedback:
    return AITakeoffFeedback(
        candidate_id=candidate.candidate_id,
        reviewer_id=reviewer_id.strip(),
        outcome=outcome,
        correction=correction.strip(),
        source_fingerprint=source_fingerprint,
    )


def feedback_fingerprint(feedback: Iterable[AITakeoffFeedback]) -> str:
    return sha256(_canonical([asdict(item) for item in feedback]).encode("utf-8")).hexdigest()
