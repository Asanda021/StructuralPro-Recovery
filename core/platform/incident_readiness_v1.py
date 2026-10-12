"""P731-P740 deterministic incident-readiness boundary.

Offline-first: no telemetry, network calls, or engineering-result mutation.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping

SEVERITIES = ("low", "medium", "high", "critical")
STATUSES = ("open", "contained", "resolved")
REQUIRED_CHECKS = ("backup_available", "integrity_check", "safe_mode_available")

@dataclass(frozen=True)
class IncidentReadiness:
    ready: bool
    severity: str
    status: str
    blockers: tuple[str, ...]
    fingerprint: str

def assess_incident_readiness(
    checks: Mapping[str, bool], *, severity: str = "medium", status: str = "open"
) -> IncidentReadiness:
    if severity not in SEVERITIES:
        raise ValueError("invalid severity")
    if status not in STATUSES:
        raise ValueError("invalid status")
    blockers = tuple(name for name in REQUIRED_CHECKS if not bool(checks.get(name, False)))
    payload = {
        "severity": severity, "status": status, "blockers": blockers,
        "ready": not blockers,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return IncidentReadiness(not blockers, severity, status, blockers, sha256(raw).hexdigest())

def require_incident_readiness(checks: Mapping[str, bool], **kwargs) -> IncidentReadiness:
    result = assess_incident_readiness(checks, **kwargs)
    if not result.ready:
        raise RuntimeError("incident readiness gate failed: " + ",".join(result.blockers))
    return result
