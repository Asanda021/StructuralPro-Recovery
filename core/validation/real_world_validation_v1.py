"""P29 real-world validation gate.

Evidence-first, deterministic validation of representative small/medium/large
project workflows. This gate never treats missing evidence as success.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

REQUIRED_SURFACES = tuple(sorted(("pdf", "cad", "revision", "takeoff", "boq", "estimate", "reports", "excel", "output_pdf")))
REQUIRED_SCALES = tuple(sorted(("small", "medium", "large")))

@dataclass(frozen=True)
class Evidence:
    scenario: str
    scale: str
    surfaces: tuple[str, ...]
    reference: str
    comparison: str
    status: str

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "Evidence":
        return cls(
            scenario=str(row.get("scenario", "")).strip(),
            scale=str(row.get("scale", "")).strip(),
            surfaces=tuple(str(x).strip() for x in row.get("surfaces", []) if str(x).strip()),
            reference=str(row.get("reference", "")).strip(),
            comparison=str(row.get("comparison", "")).strip(),
            status=str(row.get("status", "")).strip(),
        )

def validate_evidence(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    evidence = tuple(Evidence.from_dict(x) for x in rows)
    issues: list[str] = []
    if not evidence:
        issues.append("no evidence records")
    for index, item in enumerate(evidence):
        prefix = f"evidence[{index}]"
        if not item.scenario:
            issues.append(f"{prefix}.scenario missing")
        if item.scale not in REQUIRED_SCALES:
            issues.append(f"{prefix}.scale invalid")
        missing = sorted(set(REQUIRED_SURFACES) - set(item.surfaces))
        if missing:
            issues.append(f"{prefix}.surfaces missing: {','.join(missing)}")
        if not item.reference:
            issues.append(f"{prefix}.reference missing")
        if not item.comparison:
            issues.append(f"{prefix}.comparison missing")
        if item.status != "verified":
            issues.append(f"{prefix}.status is not verified")
    scales = {x.scale for x in evidence}
    scenarios = {x.scenario for x in evidence}
    missing_scales = sorted(set(REQUIRED_SCALES) - scales)
    if missing_scales:
        issues.append("missing scales: " + ",".join(missing_scales))
    if len(scenarios) < 3:
        issues.append("at least three distinct scenarios are required")
    covered = set().union(*(set(x.surfaces) for x in evidence)) if evidence else set()
    missing_surfaces = sorted(set(REQUIRED_SURFACES) - covered)
    if missing_surfaces:
        issues.append("missing surfaces: " + ",".join(missing_surfaces))
    return {
        "valid": not issues,
        "evidence_count": len(evidence),
        "scales": sorted(scales),
        "scenarios": sorted(scenarios),
        "surfaces": sorted(covered),
        "issues": issues,
    }

def acceptance_summary(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    result = validate_evidence(rows)
    return {
        "ready": result["valid"],
        "evidence_count": result["evidence_count"],
        "scale_count": len(result["scales"]),
        "scenario_count": len(result["scenarios"]),
        "surface_count": len(result["surfaces"]),
        "issues": result["issues"],
    }
