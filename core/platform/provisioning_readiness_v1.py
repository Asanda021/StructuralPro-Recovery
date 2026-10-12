"""Explicit provisioning readiness checks; never fabricates external assets."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from typing import Mapping

@dataclass(frozen=True)
class ProvisioningStatus:
    ready: bool
    missing: tuple[str, ...]
    fingerprint: str

def assess_provisioning(required: Mapping[str, bool]) -> ProvisioningStatus:
    missing = tuple(sorted(k for k, v in required.items() if not v))
    payload = "|".join(f"{k}={bool(required[k])}" for k in sorted(required))
    return ProvisioningStatus(not missing, missing, sha256(payload.encode()).hexdigest())

def require_provisioning(required: Mapping[str, bool]) -> ProvisioningStatus:
    status = assess_provisioning(required)
    if not required or not status.ready:
        raise RuntimeError("required production provisioning is unavailable")
    return status
