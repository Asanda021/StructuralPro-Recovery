"""Deterministic CAD geometry -> auto-takeoff extraction.

The extractor turns already-parsed CAD entities into auditable candidates.
It never guesses missing geometry and keeps the CAD handle/layer as provenance.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from core.drawings.element_recognition import enrich_candidate


_LENGTH_TYPES = {"LINE", "LWPOLYLINE", "POLYLINE", "ARC"}
_AREA_TYPES = {"LWPOLYLINE", "POLYLINE", "CIRCLE"}


@dataclass(frozen=True)
class GeometryTakeoffCandidate:
    source: str
    entity_type: str
    layer: str
    handle: str | None
    metric: str
    quantity: float
    unit: str
    confidence: float
    needs_confirmation: bool = True
    description: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "description": self.description or self.layer or self.entity_type,
            "quantity": self.quantity,
            "unit": self.unit,
            "entity_type": self.entity_type,
            "layer": self.layer,
            "handle": self.handle,
            "metric": self.metric,
            "confidence": self.confidence,
            "needs_confirmation": self.needs_confirmation,
        }


def _finite_nonnegative(value: Any, *, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid CAD {field}") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"Invalid CAD {field}")
    return number


def _point(value: Any) -> tuple[float, float] | None:
    try:
        x, y = float(value[0]), float(value[1])
    except (TypeError, ValueError, IndexError):
        return None
    if not math.isfinite(x) or not math.isfinite(y):
        return None
    return x, y


def _geometry_fingerprint(entity: Any) -> tuple[Any, ...] | None:
    """Return a deterministic identity for exact duplicate CAD geometry.

    Handles identify the source entity; this fingerprint catches copied/duplicated
    geometry that has different handles but identical measurable geometry.
    """
    data = getattr(entity, "data", {}) or {}
    entity_type = str(getattr(entity, "entity_type", "") or "").upper()
    layer = str(getattr(entity, "layer", "") or "0")

    def norm_point(p):
        point = _point(p)
        return None if point is None else (round(point[0], 9), round(point[1], 9))

    points = data.get("points")
    if points:
        pts = tuple(x for x in (norm_point(p) for p in points) if x is not None)
        if pts:
            return (entity_type, layer, "points", pts)
    # LINE geometry is direction-independent: A→B and B→A are the same segment.
    if entity_type == "LINE" and "start" in data and "end" in data:
        start = norm_point(data.get("start"))
        end = norm_point(data.get("end"))
        if start is not None and end is not None:
            endpoints = tuple(sorted((start, end)))
            return (
                entity_type,
                layer,
                "segment",
                endpoints,
                round(float(data.get("length", 0) or 0), 9),
            )

    for key in ("insert", "center"):
        if key in data and norm_point(data[key]) is not None:
            pair = norm_point(data[key])
            return (entity_type, layer, key, pair, round(float(data.get("length", 0) or 0), 9))
    if "radius" in data:
        try:
            return (
                entity_type,
                layer,
                "radius",
                round(float(data["radius"]), 9),
                round(float(data.get("length", 0) or 0), 9),
            )
        except (TypeError, ValueError):
            return None
    return None


def _collinear_line_overlap(a: Any, b: Any, *, tolerance: float = 1e-9) -> float:
    """Return positive overlap length for two LINE segments, else zero.

    This intentionally handles only straight LINE entities. Touching endpoints
    have zero overlap and are not treated as a duplicate. The original
    quantities remain unchanged; callers only use this as a review signal.
    """
    if str(getattr(a, "entity_type", "") or "").upper() != "LINE":
        return 0.0
    if str(getattr(b, "entity_type", "") or "").upper() != "LINE":
        return 0.0
    if str(getattr(a, "layer", "") or "0") != str(getattr(b, "layer", "") or "0"):
        return 0.0

    da = getattr(a, "data", {}) or {}
    db = getattr(b, "data", {}) or {}
    a0, a1 = _point(da.get("start")), _point(da.get("end"))
    b0, b1 = _point(db.get("start")), _point(db.get("end"))
    if None in (a0, a1, b0, b1):
        return 0.0

    ax, ay = a1[0] - a0[0], a1[1] - a0[1]
    bx, by = b1[0] - b0[0], b1[1] - b0[1]
    len_a = math.hypot(ax, ay)
    len_b = math.hypot(bx, by)
    if len_a <= tolerance or len_b <= tolerance:
        return 0.0

    cross_dirs = ax * by - ay * bx
    if abs(cross_dirs) > tolerance * max(1.0, len_a * len_b):
        return 0.0

    # Collinearity of b0 with a's supporting line.
    offset = (b0[0] - a0[0]) * ay - (b0[1] - a0[1]) * ax
    if abs(offset) > tolerance * max(1.0, len_a):
        return 0.0

    # Project both segments onto a's unit direction and intersect intervals.
    ux, uy = ax / len_a, ay / len_a
    a_min, a_max = 0.0, len_a
    b_proj0 = (b0[0] - a0[0]) * ux + (b0[1] - a0[1]) * uy
    b_proj1 = (b1[0] - a0[0]) * ux + (b1[1] - a0[1]) * uy
    b_min, b_max = sorted((b_proj0, b_proj1))
    overlap = min(a_max, b_max) - max(a_min, b_min)
    return overlap if overlap > tolerance else 0.0


def _source(entity: Any, index: int) -> str:
    layer = str(getattr(entity, "layer", "") or "0")
    handle = getattr(entity, "handle", None)
    if handle:
        return f"cad:{layer}:{handle}"
    return f"cad:{layer}:entity-{index}"


def extract_geometry_candidates(
    entities: list[Any],
    *,
    include_count: bool = True,
    confidence: float = 0.98,
    source_unit: str = "m",
) -> list[dict[str, Any]]:
    """Extract one candidate per source entity, with deterministic safety flags.

    Length/area are preferred over count. INSERT and other non-measured entities
    become count candidates when requested. A real CAD handle is the identity;
    handle-less entities use a stable input-position fallback.
    """
    if not math.isfinite(confidence) or not 0 <= confidence <= 1:
        raise ValueError("confidence must be between 0 and 1")
    source_unit = str(source_unit or "unknown").lower()
    if source_unit not in {"m", "unknown", "unitless"}:
        raise ValueError(f"unsupported CAD source unit: {source_unit}")

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    seen_geometry: dict[tuple[Any, ...], str] = {}
    measured_entities: list[tuple[Any, str]] = []

    for index, entity in enumerate(entities, 1):
        entity_type = str(getattr(entity, "entity_type", "") or "").upper()
        layer = str(getattr(entity, "layer", "") or "0")
        handle = getattr(entity, "handle", None)
        source = _source(entity, index)
        if source in seen:
            continue
        seen.add(source)

        data = getattr(entity, "data", {}) or {}
        metric: str | None = None
        unit: str | None = None
        quantity: float | None = None

        if entity_type in _AREA_TYPES and data.get("area") is not None:
            quantity = _finite_nonnegative(data.get("area"), field="area")
            metric, unit = "area", "m2"
        elif entity_type in _LENGTH_TYPES and data.get("length") is not None:
            quantity = _finite_nonnegative(data.get("length"), field="length")
            metric, unit = "length", "m"
        elif include_count:
            quantity, metric, unit = 1.0, "count", "عدد"

        if quantity is None:
            continue

        duplicate_of = None
        fingerprint = _geometry_fingerprint(entity)
        if fingerprint is not None and fingerprint in seen_geometry:
            duplicate_of = seen_geometry[fingerprint]
        elif fingerprint is not None:
            seen_geometry[fingerprint] = source

        overlap_with: list[dict[str, Any]] = []
        if metric == "length":
            for previous_entity, previous_source in measured_entities:
                overlap = _collinear_line_overlap(previous_entity, entity)
                if overlap > 0:
                    overlap_with.append({
                        "source": previous_source,
                        "overlap_length": overlap,
                    })
            measured_entities.append((entity, source))

        candidate = GeometryTakeoffCandidate(
            source=source,
            entity_type=entity_type,
            layer=layer,
            handle=str(handle) if handle is not None else None,
            metric=metric,
            quantity=quantity,
            unit=unit if source_unit == "m" else "unknown",
            confidence=confidence if source_unit == "m" else min(confidence, 0.5),
            description=layer or entity_type,
        )
        candidate_data = candidate.as_dict()
        candidate_data["duplicate_geometry"] = duplicate_of is not None
        candidate_data["duplicate_of"] = duplicate_of
        candidate_data["partial_overlap"] = bool(overlap_with)
        candidate_data["overlap_sources"] = overlap_with
        candidate_data["overlap_length"] = sum(x["overlap_length"] for x in overlap_with)
        if duplicate_of is not None or overlap_with:
            candidate_data["needs_confirmation"] = True
        out.append(enrich_candidate(entity, candidate_data))

    return out


def aggregate_geometry_candidates(
    entities: list[Any],
    *,
    confidence: float = 0.98,
    source_unit: str = "m",
) -> list[dict[str, Any]]:
    """Aggregate measured geometry by layer + metric without losing provenance."""
    candidates = extract_geometry_candidates(entities, confidence=confidence, source_unit=source_unit)
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}

    for row in candidates:
        key = (row["layer"], row["metric"], row["unit"], row.get("element_type", "unknown"))
        group = groups.setdefault(
            key,
            {
                "source": f"cad-geometry:{row['layer']}:{row['metric']}:{row.get('element_type', 'unknown')}",
                "description": row["layer"] or row["entity_type"],
                "quantity": 0.0,
                "unit": row["unit"],
                "metric": row["metric"],
                "element_type": row.get("element_type", "unknown"),
                "recognition_confidence": row.get("recognition_confidence", 0.0),
                "recognition_reason": row.get("recognition_reason", ""),
                "layer": row["layer"],
                "confidence": min(float(row["confidence"]), 1.0),
                "needs_confirmation": True,
                "entity_count": 0,
                "source_entities": [],
                "duplicate_geometry_count": 0,
                "duplicate_sources": [],
                "partial_overlap_count": 0,
                "overlap_sources": [],
                "overlap_length": 0.0,
            },
        )
        group["quantity"] += row["quantity"]
        group["entity_count"] += 1
        group["source_entities"].append(row["source"])
        if row.get("duplicate_geometry"):
            group["duplicate_geometry_count"] += 1
            group["duplicate_sources"].append({
                "source": row["source"], "duplicate_of": row.get("duplicate_of")
            })
            group["needs_confirmation"] = True
        if row.get("partial_overlap"):
            group["partial_overlap_count"] += 1
            group["overlap_sources"].append({
                "source": row["source"],
                "matches": row.get("overlap_sources", []),
            })
            group["overlap_length"] += float(row.get("overlap_length", 0.0) or 0.0)
            group["needs_confirmation"] = True

    return list(groups.values())
