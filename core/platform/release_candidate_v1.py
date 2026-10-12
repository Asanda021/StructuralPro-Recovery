"""Deterministic release-candidate gate for StructuralPro."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping

REQUIRED_FIELDS = (
    "version",
    "commit",
    "acceptance_fingerprint",
    "release_health_fingerprint",
    "production_boundary_fingerprint",
    "artifacts",
)

@dataclass(frozen=True)
class ReleaseCandidate:
    ready: bool
    blockers: tuple[str, ...]
    fingerprint: str

def evaluate_release_candidate(evidence: Mapping[str, object]) -> ReleaseCandidate:
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
        for name in ("version", "commit", "acceptance_fingerprint", "release_health_fingerprint", "production_boundary_fingerprint"):
            value = evidence.get(name)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{name} must be a non-empty string")
        artifacts = evidence.get("artifacts")
        if not isinstance(artifacts, Mapping) or not artifacts:
            errors.append("artifacts must be a non-empty mapping")
        else:
            for name, digest in artifacts.items():
                if not isinstance(name, str) or not name.strip():
                    errors.append("artifact name must be a non-empty string")
                if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest.lower()):
                    errors.append(f"{name} must be a lowercase SHA-256")
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    fingerprint = sha256(payload.encode("utf-8")).hexdigest()
    return ReleaseCandidate(not errors, tuple(sorted(set(errors))), fingerprint)

def require_release_candidate(evidence: Mapping[str, object]) -> ReleaseCandidate:
    result = evaluate_release_candidate(evidence)
    if not result.ready:
        raise ValueError("release candidate gate failed")
    return result
