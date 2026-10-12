"""Deterministic project editing lease/lock contract."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

@dataclass(frozen=True)
class ProjectLock:
    project_id: str
    owner_id: str
    acquired_at: str
    expires_at: str

def acquire_lock(project_id: str, owner_id: str, *, now: datetime, ttl_seconds: int = 300, existing: ProjectLock | None = None) -> ProjectLock:
    if not project_id.strip() or not owner_id.strip(): raise ValueError("project_id and owner_id are required")
    if now.tzinfo is None: raise ValueError("now must be timezone-aware")
    if ttl_seconds < 1: raise ValueError("ttl_seconds must be positive")
    if existing and existing.project_id == project_id and datetime.fromisoformat(existing.expires_at) > now and existing.owner_id != owner_id:
        raise RuntimeError("project is locked by another owner")
    end=now+timedelta(seconds=ttl_seconds)
    return ProjectLock(project_id,owner_id,now.isoformat(),end.isoformat())

def is_lock_active(lock: ProjectLock, *, now: datetime) -> bool:
    return lock.project_id.strip() != "" and datetime.fromisoformat(lock.expires_at) > now

def release_lock(lock: ProjectLock, *, owner_id: str) -> None:
    if lock.owner_id != owner_id: raise PermissionError("only lock owner can release")
