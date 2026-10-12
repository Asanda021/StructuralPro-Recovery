"""P1031-P1060 deterministic release-health attestation boundary."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping
from .release_health_v2 import assess_release_health_v2

@dataclass(frozen=True)
class HealthAttestation:
    valid: bool
    version: str
    commit: str
    fingerprint: str
    errors: tuple[str, ...]

def _fp(payload: Mapping[str, object]) -> str:
    raw=json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return sha256(raw).hexdigest()

def attest_release_health(
    version: str, commit: str, checks: Mapping[str, object]
) -> HealthAttestation:
    errors=[]
    if not isinstance(version, str) or not version.strip():
        errors.append("version is required")
    if not isinstance(commit, str) or not commit.strip():
        errors.append("commit is required")
    health=assess_release_health_v2(checks)
    errors.extend(health.blockers)
    payload={
        "version": version if isinstance(version,str) else "",
        "commit": commit if isinstance(commit,str) else "",
        "checks": dict(sorted(checks.items())) if isinstance(checks, Mapping) else {},
        "health_fingerprint": health.fingerprint,
        "valid": not errors,
    }
    return HealthAttestation(
        valid=not errors,
        version=payload["version"],
        commit=payload["commit"],
        fingerprint=_fp(payload),
        errors=tuple(sorted(set(errors))),
    )
