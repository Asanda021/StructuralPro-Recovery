"""P1061-P1090 deterministic production-boundary validation."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping

_REQUIRED = ("version", "commit", "runtime", "dependencies", "services", "configuration")
_ALLOWED = set(_REQUIRED)
_SECTION_NAMES = ("dependencies", "services", "configuration")

@dataclass(frozen=True)
class BoundaryValidation:
    valid: bool
    fingerprint: str
    errors: tuple[str, ...]

def _fingerprint(payload: Mapping[str, object]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")
    return sha256(raw).hexdigest()

def _bool_map(name: str, value: object, errors: list[str]) -> dict[str, bool]:
    if not isinstance(value, Mapping) or not value:
        errors.append(f"{name} must be a non-empty mapping")
        return {}
    result: dict[str, bool] = {}
    for key, status in value.items():
        if not isinstance(key, str) or not key.strip():
            errors.append(f"{name} contains an invalid name")
            continue
        if key in result:
            errors.append(f"{name} contains duplicate name: {key}")
            continue
        if type(status) is not bool:
            errors.append(f"{name}.{key} must be boolean")
            continue
        result[key.strip()] = status
        if not status:
            errors.append(f"{name}.{key} is not ready")
    return result

def validate_production_boundary(evidence: Mapping[str, object]) -> BoundaryValidation:
    errors: list[str] = []
    if not isinstance(evidence, Mapping):
        return BoundaryValidation(False, _fingerprint({"evidence": None}), ("evidence must be a mapping",))
    unknown = sorted(set(evidence) - _ALLOWED)
    missing = [key for key in _REQUIRED if key not in evidence]
    errors.extend(f"unknown field: {key}" for key in unknown)
    errors.extend(f"missing field: {key}" for key in missing)

    version = evidence.get("version")
    commit = evidence.get("commit")
    runtime = evidence.get("runtime")
    if not isinstance(version, str) or not version.strip():
        errors.append("version is required")
    if not isinstance(commit, str) or not commit.strip():
        errors.append("commit is required")
    if not isinstance(runtime, str) or not runtime.strip():
        errors.append("runtime is required")

    normalized = {}
    for section in _SECTION_NAMES:
        normalized[section] = _bool_map(section, evidence.get(section), errors)

    payload = {
        "version": version.strip() if isinstance(version, str) else "",
        "commit": commit.strip() if isinstance(commit, str) else "",
        "runtime": runtime.strip() if isinstance(runtime, str) else "",
        **normalized,
    }
    return BoundaryValidation(not errors, _fingerprint(payload), tuple(sorted(set(errors))))

def require_production_boundary(evidence: Mapping[str, object]) -> BoundaryValidation:
    result = validate_production_boundary(evidence)
    if not result.valid:
        raise ValueError("production boundary validation failed: " + "; ".join(result.errors))
    return result
