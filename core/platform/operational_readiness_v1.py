"""Deterministic support, backup and operational readiness boundary."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from typing import Mapping

@dataclass(frozen=True)
class OperationalStatus:
    ready: bool
    blockers: tuple[str, ...]
    fingerprint: str

def assess_operational_readiness(checks: Mapping[str, bool]) -> OperationalStatus:
    blockers = tuple(sorted(k for k, v in checks.items() if not v))
    payload = "|".join(f"{k}={bool(checks[k])}" for k in sorted(checks))
    return OperationalStatus(not blockers, blockers, sha256(payload.encode()).hexdigest())

def require_operational_readiness(checks: Mapping[str, bool]) -> OperationalStatus:
    status = assess_operational_readiness(checks)
    if not checks or not status.ready:
        raise RuntimeError("operational readiness is incomplete")
    return status
