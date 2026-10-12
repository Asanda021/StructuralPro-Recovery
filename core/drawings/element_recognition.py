"""Deterministic drawing element recognition for CAD takeoff.

Recognition is signal-based and review-first: layer names, block names and text
labels can suggest a structural/architectural element, but geometry alone never
claims a semantic type with certainty. No quantity is changed by recognition.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_KEYWORDS: dict[str, tuple[str, ...]] = {
    "column": ("column", "col", "ستون"),
    "beam": ("beam", "girder", "تیر"),
    "wall": ("wall", "دیوار"),
    "footing": ("footing", "foundation", "پی", "فونداسیون"),
    "slab": ("slab", "floor", "roof", "دال", "سقف"),
    "door": ("door", "در"),
    "window": ("window", "پنجره"),
    "stair": ("stair", "stairs", "پله"),
}

@dataclass(frozen=True)
class ElementRecognition:
    element_type: str
    confidence: float
    reason: str
    needs_confirmation: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "element_type": self.element_type,
            "recognition_confidence": self.confidence,
            "recognition_reason": self.reason,
            "needs_confirmation": self.needs_confirmation,
        }


def _tokens(*values: Any) -> str:
    return " ".join(str(v or "") for v in values).casefold()


def recognize_entity(entity: Any) -> ElementRecognition:
    """Recognize an entity from explicit CAD naming signals.

    Signal priority: block > layer > text. If several types tie, the result is
    unknown rather than inventing a semantic classification.
    """
    data = getattr(entity, "data", {}) or {}
    block = data.get("block", "")
    layer = getattr(entity, "layer", "")
    text = data.get("text", "")

    scores: dict[str, int] = {}
    reasons: dict[str, list[str]] = {}
    for field_name, value, weight in (
        ("block", block, 3),
        ("layer", layer, 2),
        ("text", text, 1),
    ):
        hay = str(value or "").casefold()
        if not hay:
            continue
        for kind, words in _KEYWORDS.items():
            hits = [word for word in words if word.casefold() in hay]
            if hits:
                scores[kind] = scores.get(kind, 0) + weight
                reasons.setdefault(kind, []).append(f"{field_name}:{hits[0]}")

    if not scores:
        return ElementRecognition("unknown", 0.0, "no semantic naming signal", True)

    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    best_kind, best_score = ordered[0]
    if len(ordered) > 1 and ordered[1][1] == best_score:
        return ElementRecognition("unknown", min(0.5, best_score / 6), "ambiguous semantic signals", True)

    confidence = min(0.99, 0.55 + 0.12 * best_score)
    return ElementRecognition(best_kind, confidence, ";".join(reasons[best_kind]), True)


def enrich_candidate(entity: Any, candidate: dict[str, Any]) -> dict[str, Any]:
    result = dict(candidate)
    recognition = recognize_entity(entity)
    result.update(recognition.as_dict())
    result["needs_confirmation"] = bool(
        candidate.get("needs_confirmation", True) or recognition.needs_confirmation
    )
    return result
