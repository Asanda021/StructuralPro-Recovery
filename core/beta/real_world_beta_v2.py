"""Evidence-first real-world beta evaluation contracts."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from typing import Sequence
@dataclass(frozen=True)
class BetaCase:
    case_id: str; project_id: str; source: str; expected_quantity: float; measured_quantity: float; unit: str
@dataclass(frozen=True)
class BetaReview:
    case_id: str; reviewer: str; outcome: str; note: str
class BetaEvidenceError(ValueError): pass
def validate_case(case: BetaCase) -> None:
    if not all((case.case_id,case.project_id,case.source,case.unit)) or case.expected_quantity < 0 or case.measured_quantity < 0: raise BetaEvidenceError("invalid beta evidence")
def absolute_error(case: BetaCase) -> float:
    validate_case(case); return abs(case.measured_quantity-case.expected_quantity)
def relative_error(case: BetaCase) -> float:
    validate_case(case)
    if case.expected_quantity == 0: return 0.0 if case.measured_quantity == 0 else float("inf")
    return absolute_error(case)/case.expected_quantity
def aggregate_accuracy(cases: Sequence[BetaCase]) -> dict[str,float]:
    if not cases: raise BetaEvidenceError("no beta cases supplied")
    for c in cases: validate_case(c)
    errors=[relative_error(c) for c in cases]
    finite=[e for e in errors if e != float("inf")]
    return {"case_count":float(len(cases)),"mean_relative_error":sum(finite)/len(finite) if finite else float("inf"),"max_relative_error":max(errors)}
def validate_review(review: BetaReview) -> None:
    if not all((review.case_id,review.reviewer,review.outcome,review.note)) or review.outcome not in {"accepted","rejected","needs_revision"}: raise BetaEvidenceError("invalid review evidence")
def beta_fingerprint(cases: Sequence[BetaCase], reviews: Sequence[BetaReview]) -> str:
    if not cases: raise BetaEvidenceError("empty beta dataset")
    for c in cases: validate_case(c)
    for r in reviews: validate_review(r)
    material="|".join(sorted(f"{c.case_id}:{c.expected_quantity}:{c.measured_quantity}:{c.unit}" for c in cases))+"||"+"|".join(sorted(f"{r.case_id}:{r.outcome}:{r.reviewer}" for r in reviews))
    return sha256(material.encode()).hexdigest()
