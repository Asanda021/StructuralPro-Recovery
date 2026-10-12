"""Deterministic production-release gate for StructuralPro."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping

REQUIRED_FIELDS = ("version", "commit", "release_preparation_fingerprint", "tag", "deployment")
@dataclass(frozen=True)
class ProductionRelease:
    released: bool
    blockers: tuple[str, ...]
    fingerprint: str

def evaluate_production_release(evidence: Mapping[str, object]) -> ProductionRelease:
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
        for name in ("version", "commit", "release_preparation_fingerprint", "tag"):
            value = evidence.get(name)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{name} must be a non-empty string")
        deployment = evidence.get("deployment")
        if not isinstance(deployment, Mapping) or not deployment:
            errors.append("deployment must be a non-empty mapping")
        else:
            for key in ("environment", "status", "commit"):
                value = deployment.get(key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"deployment.{key} must be a non-empty string")
            if isinstance(deployment.get("status"), str) and deployment["status"] != "released":
                errors.append("deployment.status must be released")
            if isinstance(deployment.get("commit"), str) and deployment["commit"] != evidence.get("commit"):
                errors.append("deployment.commit must match commit")
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return ProductionRelease(not errors, tuple(sorted(set(errors))), sha256(payload.encode()).hexdigest())

def require_production_release(evidence: Mapping[str, object]) -> ProductionRelease:
    result = evaluate_production_release(evidence)
    if not result.released:
        raise ValueError("production release gate failed")
    return result
