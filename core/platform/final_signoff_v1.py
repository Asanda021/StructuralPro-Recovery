"""Deterministic final sign-off gate for StructuralPro."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping

REQUIRED_FIELDS = (
    "version",
    "acceptance_fingerprint",
    "release_health_fingerprint",
    "production_boundary_fingerprint",
    "release_candidate_fingerprint",
    "release_preparation_fingerprint",
    "production_release_fingerprint",
    "post_release_verification_fingerprint",
    "checks",
)

@dataclass(frozen=True)
class FinalSignOff:
    signed_off: bool
    blockers: tuple[str, ...]
    fingerprint: str

def evaluate_final_signoff(evidence: Mapping[str, object]) -> FinalSignOff:
    errors: list[str] = []
    if not isinstance(evidence, Mapping) or not evidence:
        errors.append("evidence must be a non-empty mapping")
        canonical = {}
    else:
        unknown = sorted(set(evidence) - set(REQUIRED_FIELDS))
        missing = sorted(set(REQUIRED_FIELDS) - set(evidence))
        errors.extend(f"unknown field: {name}" for name in unknown)
        errors.extend(f"missing field: {name}" for name in missing)
        canonical = dict(evidence)
        for name in REQUIRED_FIELDS[:-1]:
            value = evidence.get(name)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{name} must be a non-empty string")
        checks = evidence.get("checks")
        if not isinstance(checks, Mapping) or not checks:
            errors.append("checks must be a non-empty mapping")
        else:
            for name, value in checks.items():
                if not isinstance(name, str) or not name.strip():
                    errors.append("check names must be non-empty strings")
                if not isinstance(value, bool):
                    errors.append(f"{name} must be boolean")
                elif value is False:
                    errors.append(f"{name} is not signed off")
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return FinalSignOff(
        signed_off=not errors,
        blockers=tuple(sorted(set(errors))),
        fingerprint=sha256(payload.encode("utf-8")).hexdigest(),
    )

def require_final_signoff(evidence: Mapping[str, object]) -> FinalSignOff:
    result = evaluate_final_signoff(evidence)
    if not result.signed_off:
        raise ValueError("final sign-off failed")
    return result
