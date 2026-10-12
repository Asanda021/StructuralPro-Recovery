"""Deterministic post-release verification gate for StructuralPro."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping

REQUIRED_FIELDS = ("version", "commit", "production_release_fingerprint", "checks")
@dataclass(frozen=True)
class PostReleaseVerification:
    verified: bool
    blockers: tuple[str, ...]
    fingerprint: str

def evaluate_post_release_verification(evidence: Mapping[str, object]) -> PostReleaseVerification:
    errors: list[str] = []
    if not isinstance(evidence, Mapping) or not evidence:
        errors.append("evidence must be a non-empty mapping")
        canonical = {}
    else:
        unknown = sorted(set(evidence) - set(REQUIRED_FIELDS))
        missing = sorted(set(REQUIRED_FIELDS) - set(evidence))
        errors.extend(f"unknown field: {x}" for x in unknown)
        errors.extend(f"missing field: {x}" for x in missing)
        canonical = dict(evidence)
        for name in ("version", "commit", "production_release_fingerprint"):
            value = evidence.get(name)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{name} must be a non-empty string")
        checks = evidence.get("checks")
        if not isinstance(checks, Mapping) or not checks:
            errors.append("checks must be a non-empty mapping")
        else:
            for name, value in checks.items():
                if not isinstance(name, str) or not name.strip():
                    errors.append("check name must be a non-empty string")
                if not isinstance(value, bool):
                    errors.append(f"{name} must be boolean")
                elif value is False:
                    errors.append(f"{name} is not verified")
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return PostReleaseVerification(not errors, tuple(sorted(set(errors))), sha256(payload.encode()).hexdigest())

def require_post_release_verification(evidence: Mapping[str, object]) -> PostReleaseVerification:
    result = evaluate_post_release_verification(evidence)
    if not result.verified:
        raise ValueError("post-release verification failed")
    return result
