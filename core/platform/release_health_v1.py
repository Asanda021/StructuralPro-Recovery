"""Deterministic, privacy-preserving post-release health gate."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Mapping


@dataclass(frozen=True)
class ReleaseHealth:
    healthy: bool
    blockers: tuple[str, ...]
    fingerprint: str


def assess_release_health(checks: Mapping[str, bool]) -> ReleaseHealth:
    blockers = tuple(sorted(k for k, v in checks.items() if not v))
    payload = "|".join(f"{k}={bool(checks[k])}" for k in sorted(checks))
    return ReleaseHealth(not blockers and bool(checks), blockers, sha256(payload.encode()).hexdigest())


def require_release_health(checks: Mapping[str, bool]) -> ReleaseHealth:
    status = assess_release_health(checks)
    if not status.healthy:
        raise RuntimeError("release health is incomplete")
    return status
