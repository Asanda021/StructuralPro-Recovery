"""P751-P760 deterministic release rollback decision boundary."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping

@dataclass(frozen=True)
class RollbackDecision:
    allowed: bool
    current_version: str
    target_version: str
    blockers: tuple[str, ...]
    fingerprint: str

def assess_rollback(
    current_version: str,
    target_version: str,
    *,
    target_known_good: bool,
    backup_verified: bool,
    migration_path_available: bool,
    engineering_regression_free: bool,
) -> RollbackDecision:
    if not current_version.strip() or not target_version.strip():
        raise ValueError("versions are required")
    blockers = []
    if current_version == target_version: blockers.append("same_version")
    if not target_known_good: blockers.append("target_not_known_good")
    if not backup_verified: blockers.append("backup_not_verified")
    if not migration_path_available: blockers.append("migration_path_unavailable")
    if not engineering_regression_free: blockers.append("engineering_regression_detected")
    payload = {
        "current_version": current_version, "target_version": target_version,
        "blockers": tuple(blockers), "allowed": not blockers,
    }
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return RollbackDecision(not blockers, current_version, target_version, tuple(blockers), digest)

def require_rollback(*args, **kwargs) -> RollbackDecision:
    result = assess_rollback(*args, **kwargs)
    if not result.allowed:
        raise RuntimeError("rollback gate failed: " + ",".join(result.blockers))
    return result
