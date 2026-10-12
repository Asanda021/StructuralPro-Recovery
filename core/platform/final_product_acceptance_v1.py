"""Deterministic final product acceptance gate for StructuralPro."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping

REQUIRED_CHECKS = (
    "core_functionality",
    "domain_outputs",
    "ui_surfaces",
    "data_integrity",
    "release_artifacts",
    "production_boundary",
    "release_health",
)

@dataclass(frozen=True)
class FinalAcceptance:
    accepted: bool
    blockers: tuple[str, ...]
    fingerprint: str

def evaluate_final_product_acceptance(checks: Mapping[str, bool]) -> FinalAcceptance:
    errors: list[str] = []
    if not isinstance(checks, Mapping) or not checks:
        errors.append("checks must be a non-empty mapping")
        canonical = {}
    else:
        invalid_names = [name for name in checks if not isinstance(name, str) or not name.strip()]
        if invalid_names:
            return FinalAcceptance(False, ("check name must be a non-empty string",),
                                   sha256(b"invalid-check-names").hexdigest())
        unknown = sorted(set(checks) - set(REQUIRED_CHECKS))
        missing = sorted(set(REQUIRED_CHECKS) - set(checks))
        errors.extend(f"unknown check: {name}" for name in unknown)
        errors.extend(f"missing check: {name}" for name in missing)
        canonical = dict(checks)
        for name in sorted(checks):
            if not isinstance(name, str) or not name.strip():
                errors.append("check name must be a non-empty string")
            elif not isinstance(checks[name], bool):
                errors.append(f"{name} must be boolean")
            elif checks[name] is False:
                errors.append(f"{name} is not accepted")
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    fingerprint = sha256(payload.encode("utf-8")).hexdigest()
    return FinalAcceptance(not errors, tuple(sorted(set(errors))), fingerprint)

def require_final_product_acceptance(checks: Mapping[str, bool]) -> FinalAcceptance:
    result = evaluate_final_product_acceptance(checks)
    if not result.accepted:
        raise ValueError("final product acceptance failed")
    return result
