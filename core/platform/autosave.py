"""Deterministic local autosave and crash-recovery contract."""
from __future__ import annotations
from copy import deepcopy
from typing import Any, Mapping
from .backup import create_backup, validate_backup

def create_autosave(project_id: str, revision: int, payload: Mapping[str, Any]) -> dict[str, Any]:
    backup=create_backup(project_id,revision,payload)
    backup["kind"]="autosave"
    return backup

def validate_autosave(snapshot: Mapping[str, Any]) -> list[str]:
    if snapshot.get("kind")!="autosave": return ["invalid autosave kind"]
    return validate_backup({k:v for k,v in snapshot.items() if k!="kind"})

def recover_autosave(snapshot: Mapping[str, Any], *, expected_project_id: str) -> dict[str, Any]:
    errors=validate_autosave(snapshot)
    if errors: raise ValueError("; ".join(errors))
    if snapshot["project_id"]!=expected_project_id: raise ValueError("project_id mismatch")
    return deepcopy(dict(snapshot["payload"]))
