"""Production hardening gate: deterministic, fail-closed and network-free."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any

@dataclass(frozen=True)
class HardeningResult:
    valid: bool
    fingerprint: str
    errors: tuple[str, ...] = ()

def canonical(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

def harden_payload(payload: dict[str, Any], *, required: tuple[str, ...] = ()) -> HardeningResult:
    if not isinstance(payload, dict):
        raise ValueError("production payload must be an object")
    errors = tuple(f"missing:{key}" for key in required if key not in payload)
    return HardeningResult(not errors, sha256(canonical(payload).encode()).hexdigest(), errors)

def validate_no_unknown(payload: dict[str, Any], allowed: tuple[str, ...]) -> HardeningResult:
    if not isinstance(payload, dict):
        raise ValueError("production payload must be an object")
    errors = tuple(f"unknown:{key}" for key in sorted(set(payload) - set(allowed)))
    return HardeningResult(not errors, sha256(canonical(payload).encode()).hexdigest(), errors)

def tamper_fingerprint(payload: dict[str, Any]) -> str:
    return sha256(canonical(payload).encode()).hexdigest()
