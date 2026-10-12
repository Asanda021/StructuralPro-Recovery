"""Deterministic final release acceptance gates for StructuralPro."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from typing import Mapping

@dataclass(frozen=True)
class AcceptanceResult:
    passed: bool
    blockers: tuple[str, ...]
    fingerprint: str

def evaluate_release_acceptance(checks: Mapping[str, bool]) -> AcceptanceResult:
    blockers = tuple(sorted(k for k, v in checks.items() if not v))
    payload = "|".join(f"{k}={bool(checks[k])}" for k in sorted(checks))
    fp = sha256(payload.encode("utf-8")).hexdigest()
    return AcceptanceResult(not blockers, blockers, fp)

def require_complete_acceptance(checks: Mapping[str, bool]) -> AcceptanceResult:
    result = evaluate_release_acceptance(checks)
    if not checks or not result.passed:
        raise ValueError("release acceptance is incomplete or failed")
    return result
