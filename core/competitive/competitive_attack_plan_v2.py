"""Evidence-first competitive benchmark contracts for StructuralPro."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from typing import Sequence
@dataclass(frozen=True)
class CompetitorEvidence:
    competitor: str; capability: str; source: str; observed: str; date: str
@dataclass(frozen=True)
class BenchmarkDimension:
    name: str; weight: float
class CompetitivePlanError(ValueError): pass
def validate_evidence(e: CompetitorEvidence) -> None:
    if not all((e.competitor,e.capability,e.source,e.observed,e.date)): raise CompetitivePlanError("incomplete competitor evidence")
def validate_dimensions(dimensions: Sequence[BenchmarkDimension]) -> None:
    if not dimensions or any(not d.name or d.weight < 0 for d in dimensions): raise CompetitivePlanError("invalid benchmark dimensions")
def build_matrix(evidence: Sequence[CompetitorEvidence], dimensions: Sequence[BenchmarkDimension]) -> dict[str,list[CompetitorEvidence]]:
    validate_dimensions(dimensions)
    if not evidence: raise CompetitivePlanError("no competitor evidence")
    for e in evidence: validate_evidence(e)
    return {name:[e for e in evidence if e.capability == name] for name in (d.name for d in dimensions)}
def plan_fingerprint(evidence: Sequence[CompetitorEvidence], dimensions: Sequence[BenchmarkDimension]) -> str:
    matrix=build_matrix(evidence,dimensions)
    material="|".join(sorted(f"{e.competitor}:{e.capability}:{e.source}:{e.observed}:{e.date}" for e in evidence))+"||"+"|".join(sorted(f"{d.name}:{d.weight}" for d in dimensions))
    return sha256(material.encode()).hexdigest()
def unsupported_claims(evidence: Sequence[CompetitorEvidence], claims: Sequence[tuple[str,str]]) -> list[tuple[str,str]]:
    known={(e.competitor,e.capability) for e in evidence}
    return [claim for claim in claims if claim not in known]
