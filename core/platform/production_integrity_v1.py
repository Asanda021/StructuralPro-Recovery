"""Production integrity evidence gate for P941-P970.
Deterministic, fail-closed and network-free.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any

_ALLOWED = frozenset({"build_id", "version", "commit", "checks"})
_REQUIRED = ("build_id", "version", "commit", "checks")
_CHECK_KEYS = frozenset({"name", "status"})

def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

def fingerprint(value: Any) -> str:
    return sha256(canonical(value).encode("utf-8")).hexdigest()

@dataclass(frozen=True)
class IntegrityResult:
    valid: bool
    fingerprint: str
    errors: tuple[str, ...] = ()

def validate_release_evidence(payload: dict[str, Any]) -> IntegrityResult:
    if not isinstance(payload, dict):
        raise ValueError("release evidence must be an object")
    errors: list[str] = []
    errors.extend(f"missing:{key}" for key in _REQUIRED if key not in payload)
    errors.extend(f"unknown:{key}" for key in sorted(set(payload) - _ALLOWED))
    checks = payload.get("checks")
    if not isinstance(checks, list) or not checks:
        errors.append("checks:non_empty_list_required")
    else:
        names: list[str] = []
        for index, check in enumerate(checks):
            if not isinstance(check, dict):
                errors.append(f"checks[{index}]:object_required")
                continue
            errors.extend(f"checks[{index}]:unknown:{key}" for key in sorted(set(check) - _CHECK_KEYS))
            if "name" not in check:
                errors.append(f"checks[{index}]:missing:name")
            elif not isinstance(check["name"], str) or not check["name"].strip():
                errors.append(f"checks[{index}]:invalid:name")
            else:
                names.append(check["name"])
            if check.get("status") != "success":
                errors.append(f"checks[{index}]:status_not_success")
        if len(names) != len(set(names)):
            errors.append("checks:duplicate_name")
    for key in ("build_id", "version", "commit"):
        if key in payload and (not isinstance(payload[key], str) or not payload[key].strip()):
            errors.append(f"invalid:{key}")
    return IntegrityResult(not errors, fingerprint(payload), tuple(sorted(set(errors))))

def evidence_fingerprint(payload: dict[str, Any]) -> str:
    return fingerprint(payload)
