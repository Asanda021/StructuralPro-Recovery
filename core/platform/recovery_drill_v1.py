"""P741-P750 deterministic recovery-drill boundary.

Composes existing backup/restore integrity evidence without performing I/O.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from .backup_integrity_v1 import BackupEvidence, RestoreEvidence, ProjectIntegrityEvidence, restore_allowed

@dataclass(frozen=True)
class RecoveryDrill:
    passed: bool
    backup_id: str
    project_id: str
    blockers: tuple[str, ...]
    fingerprint: str

def assess_recovery_drill(
    backup: BackupEvidence,
    restore: RestoreEvidence,
    integrity: ProjectIntegrityEvidence,
    *,
    project_id: str,
) -> RecoveryDrill:
    blockers = []
    if not restore_allowed(backup, restore, integrity, project_id):
        if project_id.strip() != backup.project_id: blockers.append("project_mismatch")
        if restore.backup_id != backup.backup_id: blockers.append("backup_mismatch")
        if backup.result != "accepted": blockers.append("backup_rejected")
        if restore.result != "accepted": blockers.append("restore_rejected")
        if integrity.project_id != project_id: blockers.append("integrity_project_mismatch")
        if not integrity.passed: blockers.append("integrity_failed")
        if integrity.revision != restore.resulting_revision: blockers.append("revision_mismatch")
    blockers = tuple(dict.fromkeys(blockers))
    payload = {
        "backup_id": backup.backup_id, "project_id": project_id,
        "blockers": blockers, "passed": not blockers,
    }
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return RecoveryDrill(not blockers, backup.backup_id, project_id, blockers, digest)

def require_recovery_drill(*args, **kwargs) -> RecoveryDrill:
    result = assess_recovery_drill(*args, **kwargs)
    if not result.passed:
        raise RuntimeError("recovery drill failed: " + ",".join(result.blockers))
    return result
