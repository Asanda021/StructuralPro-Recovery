"""P23 AI Takeoff — evidence-first AI-assisted quantity takeoff.

The AI layer proposes; deterministic engines calculate; a human confirms.
No network calls are required. Unknown or conflicting evidence fails closed.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
import json
import math
from typing import Any, Iterable, Mapping


ELEMENT_TERMS: dict[str, tuple[str, ...]] = {
    "wall": ("wall", "walls", "دیوار"),
    "column": ("column", "columns", "col", "ستون"),
    "beam": ("beam", "beams", "تیر"),
    "slab": ("slab", "floor", "roof", "دال", "سقف"),
    "footing": ("footing", "foundation", "پی", "فونداسیون"),
    "door": ("door", "doors", "در"),
    "window": ("window", "windows", "پنجره"),
}

METRICS = ("length", "area", "count", "volume")


@dataclass(frozen=True)
class AITakeoffCandidate:
    candidate_id: str
    element_type: str
    metric: str
    quantity: float
    unit: str
    confidence: float
    source_ids: tuple[str, ...]
    reasons: tuple[str, ...]
    needs_confirmation: bool = True

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.source_ids:
            raise ValueError("candidate identity and source evidence are required")
        if self.element_type not in ELEMENT_TERMS:
            raise ValueError("unsupported element type")
        if self.metric not in METRICS:
            raise ValueError("unsupported metric")
        if not math.isfinite(self.quantity) or self.quantity < 0:
            raise ValueError("quantity must be finite and non-negative")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True)
class AITakeoffDecision:
    candidate_id: str
    status: str
    reason: str


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def candidate_fingerprint(candidate: AITakeoffCandidate) -> str:
    return sha256(_canonical(asdict(candidate)).encode("utf-8")).hexdigest()


def _classify(text: str) -> tuple[str | None, float, str]:
    q = text.casefold()
    matches: list[str] = []
    for kind, terms in ELEMENT_TERMS.items():
        if any(term.casefold() in q for term in terms):
            matches.append(kind)
    if len(matches) != 1:
        return None, 0.0, "no unique element classification"
    return matches[0], 0.85, f"classified from drawing text as {matches[0]}"


def _metric(data: Mapping[str, Any]) -> tuple[str | None, float]:
    present = []
    for key in METRICS:
        if data.get(key) is not None:
            try:
                value = float(data[key])
            except (TypeError, ValueError):
                continue
            if math.isfinite(value) and value >= 0:
                present.append(key)
    if len(present) != 1:
        return None, 0.0
    return present[0], 1.0


def propose_takeoff(entities: Iterable[Any]) -> list[AITakeoffCandidate]:
    """Generate review-required candidates from CAD/BIM-like entities.

    Entity values are treated as evidence, never as permission to invent a
    missing dimension. Ambiguous classification/metric is skipped.
    """
    output: list[AITakeoffCandidate] = []
    for index, entity in enumerate(entities):
        data = getattr(entity, "data", None)
        data = dict(data or {}) if isinstance(data, Mapping) else {}
        layer = _text(getattr(entity, "layer", None) or data.get("layer"))
        entity_type = _text(getattr(entity, "entity_type", None) or data.get("entity_type"))
        label = " ".join(
            x for x in (
                layer,
                entity_type,
                _text(data.get("text")),
                _text(data.get("block")),
                _text(data.get("block_name")),
                _text(data.get("name")),
                _text(data.get("ifc_type")),
            ) if x
        )
        kind, class_score, class_reason = _classify(label)
        metric, metric_score = _metric(data)
        if kind is None or metric is None:
            continue

        source = _text(
            data.get("source_id")
            or getattr(entity, "source_id", None)
            or data.get("global_id")
            or data.get("id")
            or f"entity-{index + 1}"
        )
        quantity = float(data[metric])
        unit = {"length": "m", "area": "m2", "count": "عدد", "volume": "m3"}[metric]
        confidence = round(min(class_score, metric_score), 3)
        candidate_id = sha256(
            _canonical({"source": source, "kind": kind, "metric": metric, "quantity": quantity}).encode()
        ).hexdigest()[:16]
        output.append(
            AITakeoffCandidate(
                candidate_id=candidate_id,
                element_type=kind,
                metric=metric,
                quantity=quantity,
                unit=unit,
                confidence=confidence,
                source_ids=(source,),
                reasons=(class_reason, "quantity supplied by source evidence"),
            )
        )
    return output


def review_candidates(
    candidates: Iterable[AITakeoffCandidate],
    decisions: Mapping[str, str] | None = None,
) -> list[AITakeoffDecision]:
    """Apply an explicit human decision; never auto-accept an AI proposal."""
    decisions = decisions or {}
    result: list[AITakeoffDecision] = []
    for candidate in candidates:
        status = _text(decisions.get(candidate.candidate_id))
        if status not in {"accepted", "rejected"}:
            result.append(AITakeoffDecision(candidate.candidate_id, "review", "explicit confirmation required"))
        elif status == "accepted":
            result.append(AITakeoffDecision(candidate.candidate_id, "accepted", "accepted by explicit reviewer decision"))
        else:
            result.append(AITakeoffDecision(candidate.candidate_id, "rejected", "rejected by explicit reviewer decision"))
    return result


def build_takeoff_payload(
    candidates: Iterable[AITakeoffCandidate],
    *,
    source_fingerprint: str,
) -> dict[str, Any]:
    """Create a deterministic payload for the existing quantity/BOQ pipeline."""
    if not _text(source_fingerprint):
        raise ValueError("source_fingerprint is required")
    rows = [asdict(c) for c in candidates]
    return {
        "kind": "ai_takeoff_v1",
        "source_fingerprint": source_fingerprint,
        "candidates": rows,
        "accepted_count": 0,
        "review_required": len(rows),
        "fail_closed": True,
    }
