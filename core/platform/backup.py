"""Deterministic offline project backup and restore contract."""
from __future__ import annotations
from copy import deepcopy
import hashlib, json
from typing import Any, Mapping

SCHEMA_VERSION = "v1"

def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")

def create_backup(project_id: str, revision: int, payload: Mapping[str, Any]) -> dict[str, Any]:
    if not project_id.strip(): raise ValueError("project_id is required")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0: raise ValueError("revision must be a non-negative integer")
    if not isinstance(payload, Mapping): raise TypeError("payload must be a mapping")
    body = {"schema_version": SCHEMA_VERSION, "project_id": project_id, "revision": revision, "payload": deepcopy(dict(payload))}
    body["sha256"] = hashlib.sha256(_canonical(body)).hexdigest()
    return body

def validate_backup(backup: Mapping[str, Any]) -> list[str]:
    if not isinstance(backup, Mapping): return ["backup must be a mapping"]
    errors=[]
    if backup.get("schema_version") != SCHEMA_VERSION: errors.append("unsupported schema_version")
    if not str(backup.get("project_id","")).strip(): errors.append("project_id is required")
    if isinstance(backup.get("revision"), bool) or not isinstance(backup.get("revision"), int) or backup.get("revision", -1) < 0: errors.append("invalid revision")
    if not isinstance(backup.get("payload"), Mapping): errors.append("payload must be a mapping")
    digest=backup.get("sha256")
    if not isinstance(digest,str) or len(digest)!=64: errors.append("invalid sha256")
    if not errors:
        body={k:v for k,v in backup.items() if k!="sha256"}
        try:
            expected = hashlib.sha256(_canonical(body)).hexdigest()
        except (TypeError, ValueError, OverflowError):
            errors.append("backup payload is not finite JSON")
        else:
            if expected.casefold()!=digest.casefold(): errors.append("backup integrity mismatch")
    return errors

def restore_backup(backup: Mapping[str, Any], *, expected_project_id: str | None = None) -> dict[str, Any]:
    errors=validate_backup(backup)
    if errors: raise ValueError("; ".join(errors))
    if expected_project_id is not None and backup["project_id"] != expected_project_id:
        raise ValueError("project_id mismatch")
    return deepcopy(dict(backup["payload"]))
