"""P1001-P1030 deterministic release-health gate.

This boundary converts post-release checks into a strict, reproducible health
decision without network access or mutation of engineering quantities.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping


@dataclass(frozen=True)
class ReleaseHealthV2:
    healthy: bool
    blockers: tuple[str, ...]
    fingerprint: str


def _fingerprint(checks: Mapping[str, bool]) -> str:
    payload = json.dumps(
        dict(sorted(checks.items())),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def assess_release_health_v2(checks: Mapping[str, object]) -> ReleaseHealthV2:
    """Fail closed on malformed health evidence."""
    errors: list[str] = []
    if not isinstance(checks, Mapping) or not checks:
        return ReleaseHealthV2(False, ("checks must be a non-empty mapping",), sha256(b"{}").hexdigest())

    normalized: dict[str, bool] = {}
    for name, value in checks.items():
        if not isinstance(name, str) or not name.strip():
            errors.append("check names must be non-empty strings")
            continue
        if not isinstance(value, bool):
            errors.append(f"{name}: status must be boolean")
            continue
        normalized[name.strip()] = value

    if len(normalized) != len(checks):
        errors.append("check names must be unique after normalization")

    blockers = sorted(
        {*(name for name, ok in normalized.items() if not ok), *errors}
    )
    return ReleaseHealthV2(
        healthy=not blockers and bool(normalized),
        blockers=tuple(blockers),
        fingerprint=_fingerprint(normalized),
    )


def require_release_health_v2(checks: Mapping[str, object]) -> ReleaseHealthV2:
    result = assess_release_health_v2(checks)
    if not result.healthy:
        raise RuntimeError("release health is incomplete")
    return result
