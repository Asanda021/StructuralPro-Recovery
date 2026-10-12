"""P56 final regression and real-world evidence contracts."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

ArtifactKind = Literal["pdf", "dwg", "dxf", "image", "ifc", "boq", "report"]

@dataclass(frozen=True)
class ProjectArtifact:
    project_id: str
    kind: ArtifactKind
    source: str
    sha256: str
    observed_at: str

@dataclass(frozen=True)
class QuantityCheck:
    item: str
    human_quantity: float
    system_quantity: float
    unit: str
    @property
    def absolute_error(self) -> float:
        return abs(self.system_quantity - self.human_quantity)
    @property
    def relative_error(self) -> float | None:
        if self.human_quantity == 0:
            return 0.0 if self.system_quantity == 0 else None
        return self.absolute_error / abs(self.human_quantity)

@dataclass(frozen=True)
class RealWorldEvaluation:
    project_id: str
    artifact_count: int
    check_count: int
    absolute_error_total: float
    relative_error_mean: float | None
    fingerprint: str

def validate_artifacts(artifacts: tuple[ProjectArtifact, ...]) -> None:
    if not artifacts:
        raise ValueError("real-world evaluation requires explicit project artifacts")
    for artifact in artifacts:
        if not all((artifact.project_id.strip(), artifact.kind, artifact.source.strip(), artifact.sha256.strip(), artifact.observed_at.strip())):
            raise ValueError("incomplete project artifact evidence")
        if len(artifact.sha256) != 64:
            raise ValueError("artifact sha256 must be a 64-character hex digest")
        try:
            int(artifact.sha256, 16)
        except ValueError as exc:
            raise ValueError("artifact sha256 must be hexadecimal") from exc

def evaluate_project(project_id: str, artifacts: tuple[ProjectArtifact, ...], checks: tuple[QuantityCheck, ...]) -> RealWorldEvaluation:
    if not project_id.strip():
        raise ValueError("project_id is required")
    validate_artifacts(artifacts)
    if not checks:
        raise ValueError("real-world evaluation requires explicit quantity checks")
    for check in checks:
        if not check.item.strip() or not check.unit.strip():
            raise ValueError("quantity check requires item and unit")
        if check.human_quantity < 0 or check.system_quantity < 0:
            raise ValueError("quantities cannot be negative")
    relative = [c.relative_error for c in checks if c.relative_error is not None]
    material = "|".join(f"{a.project_id}:{a.kind}:{a.source}:{a.sha256}:{a.observed_at}" for a in sorted(artifacts, key=lambda x: (x.project_id, x.kind, x.source)))
    material += "|" + "|".join(f"{c.item}:{c.human_quantity}:{c.system_quantity}:{c.unit}" for c in sorted(checks, key=lambda x: (x.item, x.unit)))
    fingerprint = sha256(material.encode()).hexdigest()
    return RealWorldEvaluation(project_id, len(artifacts), len(checks), sum(c.absolute_error for c in checks), sum(relative) / len(relative) if relative else None, fingerprint)
