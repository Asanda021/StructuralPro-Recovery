"""Evidence-first graphical PDF measurement boundary.

The engine measures only explicit graphical primitives supplied by an upstream
PDF/vector extractor. It never guesses scale, geometry, dimensions, or
engineering quantities. Missing calibration or ambiguous evidence fails closed.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Literal


@dataclass(frozen=True)
class Calibration:
    units_per_page_unit: float
    source_id: str

    def validate(self) -> None:
        if not math.isfinite(self.units_per_page_unit) or self.units_per_page_unit <= 0:
            raise ValueError("Calibration scale must be a positive finite value")
        if not self.source_id.strip():
            raise ValueError("Calibration source_id is required")


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class MeasurementEvidence:
    project_id: str
    revision: str
    source_id: str
    page: int
    element_id: str
    geometry_type: Literal["line", "polyline", "polygon"]
    points: tuple[Point, ...]
    calibration: Calibration


@dataclass(frozen=True)
class MeasurementResult:
    evidence_fingerprint: str
    value: float
    unit: str


def _validate_points(points: tuple[Point, ...]) -> None:
    if len(points) < 2:
        raise ValueError("At least two explicit points are required")
    for point in points:
        if not (math.isfinite(point.x) and math.isfinite(point.y)):
            raise ValueError("Point coordinates must be finite")


def _canonical(evidence: MeasurementEvidence) -> str:
    payload = {
        "project_id": evidence.project_id,
        "revision": evidence.revision,
        "source_id": evidence.source_id,
        "page": evidence.page,
        "element_id": evidence.element_id,
        "geometry_type": evidence.geometry_type,
        "points": [{"x": p.x, "y": p.y} for p in evidence.points],
        "calibration": {
            "units_per_page_unit": evidence.calibration.units_per_page_unit,
            "source_id": evidence.calibration.source_id,
        },
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def validate_evidence(evidence: MeasurementEvidence) -> None:
    if not evidence.project_id.strip() or not evidence.revision.strip():
        raise ValueError("Project and revision are required")
    if not evidence.source_id.strip() or not evidence.element_id.strip():
        raise ValueError("Source and element identifiers are required")
    if evidence.page < 1:
        raise ValueError("Page must be >= 1")
    if evidence.source_id != evidence.calibration.source_id:
        raise ValueError("Calibration must cite the same source")
    evidence.calibration.validate()
    _validate_points(evidence.points)


def evidence_fingerprint(evidence: MeasurementEvidence) -> str:
    validate_evidence(evidence)
    return hashlib.sha256(_canonical(evidence).encode("utf-8")).hexdigest()


def _line_length(points: tuple[Point, ...]) -> float:
    return sum(
        math.hypot(b.x - a.x, b.y - a.y)
        for a, b in zip(points, points[1:])
    )


def _polygon_area(points: tuple[Point, ...]) -> float:
    if len(points) < 3:
        raise ValueError("Polygon requires at least three points")
    return abs(
        sum(
            a.x * b.y - b.x * a.y
            for a, b in zip(points, points[1:] + points[:1])
        )
    ) / 2


def measure(evidence: MeasurementEvidence) -> MeasurementResult:
    """Measure explicit vector evidence after validated calibration."""
    validate_evidence(evidence)
    if evidence.geometry_type in {"line", "polyline"}:
        raw = _line_length(evidence.points)
        unit = "length"
    elif evidence.geometry_type == "polygon":
        raw = _polygon_area(evidence.points)
        unit = "area"
    else:
        raise ValueError("Unsupported geometry type")
    return MeasurementResult(
        evidence_fingerprint=evidence_fingerprint(evidence),
        value=raw * (evidence.calibration.units_per_page_unit ** (2 if unit == "area" else 1)),
        unit=unit,
    )
