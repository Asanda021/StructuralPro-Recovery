"""P24 AI Takeoff Intelligence — normalization, duplicate safety and explainable grouping.

This layer improves proposal quality without inventing geometry or quantities.
It remains deterministic, offline, traceable and review-gated.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, asdict
from hashlib import sha256
import json
import math
import re
from typing import Any, Iterable

from .takeoff_ai_v1 import AITakeoffCandidate


_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


@dataclass(frozen=True)
class IntelligenceGroup:
    element_type: str
    metric: str
    unit: str
    quantity: float
    candidate_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    confidence: float
    needs_confirmation: bool = True


def normalize_drawing_text(value: Any) -> str:
    """Normalize common CAD/PDF/BIM text variants without changing meaning."""
    text = "" if value is None else str(value)
    text = text.translate(_PERSIAN_DIGITS)
    text = text.replace("ي", "ی").replace("ى", "ی").replace("ك", "ک")
    text = text.replace("\u200c", " ").replace("\u200f", " ").replace("\u200e", " ")
    text = re.sub(r"\s+", " ", text).strip().casefold()
    return text


def _key(candidate: AITakeoffCandidate) -> tuple[str, str, str]:
    return candidate.element_type, candidate.metric, candidate.unit


def candidate_source_key(candidate: AITakeoffCandidate) -> tuple[str, str, str]:
    """Stable identity used to prevent double counting the same source."""
    source = "|".join(sorted(set(candidate.source_ids)))
    return source, candidate.element_type, candidate.metric


def deduplicate_candidates(candidates: Iterable[AITakeoffCandidate]) -> tuple[list[AITakeoffCandidate], list[str]]:
    """Keep the first deterministic source record and report duplicate IDs."""
    kept: list[AITakeoffCandidate] = []
    seen: set[tuple[str, str, str]] = set()
    duplicates: list[str] = []
    for candidate in candidates:
        key = candidate_source_key(candidate)
        if key in seen:
            duplicates.append(candidate.candidate_id)
            continue
        seen.add(key)
        kept.append(candidate)
    return kept, duplicates


def group_candidates(candidates: Iterable[AITakeoffCandidate]) -> list[IntelligenceGroup]:
    """Group traceable candidates for human review; never auto-accepts them."""
    unique, _ = deduplicate_candidates(candidates)
    buckets: dict[tuple[str, str, str], list[AITakeoffCandidate]] = defaultdict(list)
    for candidate in unique:
        buckets[_key(candidate)].append(candidate)

    groups: list[IntelligenceGroup] = []
    for key in sorted(buckets):
        rows = buckets[key]
        quantity = sum(row.quantity for row in rows)
        confidence = min(row.confidence for row in rows)
        ids = tuple(row.candidate_id for row in rows)
        sources = tuple(sorted({source for row in rows for source in row.source_ids}))
        groups.append(
            IntelligenceGroup(
                element_type=key[0],
                metric=key[1],
                unit=key[2],
                quantity=round(quantity, 9),
                candidate_ids=ids,
                source_ids=sources,
                confidence=confidence,
            )
        )
    return groups


def intelligence_fingerprint(groups: Iterable[IntelligenceGroup]) -> str:
    payload = [asdict(group) for group in groups]
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def validate_intelligence(groups: Iterable[IntelligenceGroup]) -> tuple[bool, tuple[str, ...]]:
    """Structural gate for downstream BOQ use. Any invalid group fails closed."""
    errors: list[str] = []
    for group in groups:
        if not group.source_ids:
            errors.append("missing source evidence")
        if not group.candidate_ids:
            errors.append("missing candidate evidence")
        if not math.isfinite(group.quantity) or group.quantity < 0:
            errors.append("invalid quantity")
        if not 0 <= group.confidence <= 1:
            errors.append("invalid confidence")
        if not group.needs_confirmation:
            errors.append("human confirmation gate removed")
    return not errors, tuple(errors)
