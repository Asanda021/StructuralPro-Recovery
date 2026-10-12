"""Deterministic release assurance gate for P971-P1000."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any

_REQUIRED = ("version", "commit", "artifacts", "environment")
_ALLOWED = frozenset(_REQUIRED)
_ARTIFACT_KEYS = frozenset({"name", "sha256"})
_ENV_KEYS = frozenset({"python", "platform"})

@dataclass(frozen=True)
class AssuranceResult:
    valid: bool
    fingerprint: str
    errors: tuple[str, ...]

def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

def assurance_fingerprint(value: Any) -> str:
    return sha256(canonical(value).encode("utf-8")).hexdigest()

def validate_release_manifest(payload: Any) -> AssuranceResult:
    if not isinstance(payload, dict):
        raise ValueError("release manifest must be an object")
    errors: list[str] = []
    errors.extend(f"missing:{k}" for k in _REQUIRED if k not in payload)
    errors.extend(f"unknown:{k}" for k in sorted(set(payload) - _ALLOWED))

    for key in ("version", "commit"):
        if key in payload and (not isinstance(payload[key], str) or not payload[key].strip()):
            errors.append(f"invalid:{key}")

    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("artifacts:non_empty_list_required")
    else:
        names: list[str] = []
        for i, item in enumerate(artifacts):
            if not isinstance(item, dict):
                errors.append(f"artifacts[{i}]:object_required")
                continue
            errors.extend(f"artifacts[{i}]:unknown:{k}" for k in sorted(set(item) - _ARTIFACT_KEYS))
            name, digest = item.get("name"), item.get("sha256")
            if not isinstance(name, str) or not name.strip():
                errors.append(f"artifacts[{i}]:invalid:name")
            else:
                names.append(name)
            if not isinstance(digest, str) or len(digest) != 64 or not all(c in "0123456789abcdef" for c in digest.lower()):
                errors.append(f"artifacts[{i}]:invalid:sha256")
        if len(names) != len(set(names)):
            errors.append("artifacts:duplicate_name")

    environment = payload.get("environment")
    if not isinstance(environment, dict):
        errors.append("environment:object_required")
    else:
        errors.extend(f"environment:unknown:{k}" for k in sorted(set(environment) - _ENV_KEYS))
        for key in _ENV_KEYS:
            if key not in environment or not isinstance(environment[key], str) or not environment[key].strip():
                errors.append(f"environment:invalid:{key}")

    return AssuranceResult(not errors, assurance_fingerprint(payload), tuple(sorted(set(errors))))
