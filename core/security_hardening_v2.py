"""Evidence-first security and production-hardening contracts for StructuralPro."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Sequence
ALLOWED_ROLES=frozenset({"owner","admin","editor","reviewer","viewer"})
@dataclass(frozen=True)
class SecurityPrincipal:
    user_id: str; project_id: str; role: str
@dataclass(frozen=True)
class BackupArtifact:
    project_id: str; backup_id: str; content_sha256: str; created_at: str
@dataclass(frozen=True)
class AuditEvent:
    project_id: str; actor_id: str; action: str; timestamp: str; evidence: str
class SecurityHardeningError(ValueError): pass
def authorize(principal: SecurityPrincipal, project_id: str, required_roles: Sequence[str]) -> bool:
    if not principal.user_id or not principal.project_id or principal.project_id != project_id: raise SecurityHardeningError("project identity mismatch")
    if principal.role not in ALLOWED_ROLES or not required_roles or any(r not in ALLOWED_ROLES for r in required_roles): raise SecurityHardeningError("invalid role authorization input")
    return principal.role in set(required_roles)

def require_authorized(principal: SecurityPrincipal, project_id: str, required_roles: Sequence[str]) -> bool:
    """Fail-closed authorization boundary for state-changing operations.

    ``authorize`` remains a predicate for compatibility with existing callers;
    mutation boundaries should use this function so an ignored false return
    cannot accidentally grant access.
    """
    if not authorize(principal, project_id, required_roles):
        raise PermissionError("role is not authorized for this project operation")
    return True

def validate_project_file(
    principal: SecurityPrincipal,
    project_id: str,
    project_root: str | Path,
    path: str | Path,
    expected_sha256: str,
) -> Path:
    """Verify that an evidence file belongs to one project and matches provenance."""
    require_authorized(principal, project_id, tuple(ALLOWED_ROLES))
    root=Path(project_root)
    candidate=Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise SecurityHardeningError("project evidence must be a regular non-symlink file")
    try:
        resolved_root=root.resolve(strict=True)
        resolved=candidate.resolve(strict=True)
        resolved.relative_to(resolved_root)
    except (OSError, ValueError) as exc:
        raise SecurityHardeningError("project file isolation violation") from exc
    digest=str(expected_sha256 or "").lower()
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise SecurityHardeningError("invalid project file digest")
    actual=sha256()
    with resolved.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            actual.update(chunk)
    if actual.hexdigest() != digest:
        raise SecurityHardeningError("project file integrity mismatch")
    return resolved
def validate_backup(artifact: BackupArtifact, payload: bytes) -> bool:
    if not artifact.project_id or not artifact.backup_id or not artifact.created_at: raise SecurityHardeningError("incomplete backup evidence")
    if len(artifact.content_sha256) != 64: raise SecurityHardeningError("invalid backup digest")
    if sha256(payload).hexdigest() != artifact.content_sha256: raise SecurityHardeningError("backup integrity mismatch")
    return True
def validate_audit_event(event: AuditEvent) -> bool:
    if not all((event.project_id,event.actor_id,event.action,event.timestamp,event.evidence)): raise SecurityHardeningError("incomplete audit evidence")
    return True
def enforce_rate_limit(events: Sequence[AuditEvent], actor_id: str, limit: int) -> bool:
    if limit < 1 or not actor_id: raise SecurityHardeningError("invalid rate-limit input")
    return sum(e.actor_id == actor_id for e in events) < limit
def recovery_fingerprint(project_id: str, backups: Sequence[BackupArtifact], recovery_target: str) -> str:
    if not project_id or not recovery_target or not backups: raise SecurityHardeningError("recovery evidence is incomplete")
    if any(b.project_id != project_id for b in backups): raise SecurityHardeningError("backup project isolation violation")
    material="|".join(sorted(f"{b.backup_id}:{b.content_sha256}" for b in backups))
    return sha256(f"{project_id}|{recovery_target}|{material}".encode()).hexdigest()
