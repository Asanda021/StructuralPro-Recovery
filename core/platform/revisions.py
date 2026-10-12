"""Immutable project revisions and deterministic snapshot comparison."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
import hashlib, json
from typing import Any, Mapping

def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value),ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()

def snapshot_digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload)).hexdigest()

@dataclass(frozen=True)
class Revision:
    revision_id: int
    parent_id: int | None
    message: str
    digest: str
    payload: dict[str, Any]

def create_revision(payload: Mapping[str, Any], revision_id: int, *, parent_id: int | None = None, message: str = "") -> Revision:
    if not isinstance(revision_id,int) or revision_id < 0: raise ValueError("revision_id must be non-negative")
    if parent_id is not None and (not isinstance(parent_id,int) or parent_id < 0): raise ValueError("parent_id must be non-negative")
    if not message.strip(): raise ValueError("message is required")
    data=deepcopy(dict(payload))
    return Revision(revision_id,parent_id,message,snapshot_digest(data),data)

def verify_revision(revision: Revision) -> bool:
    return snapshot_digest(revision.payload)==revision.digest

def compare_revisions(left: Revision, right: Revision) -> dict[str, Any]:
    if not verify_revision(left) or not verify_revision(right): raise ValueError("invalid revision integrity")
    return {"same": left.digest==right.digest, "left_revision":left.revision_id, "right_revision":right.revision_id, "left_digest":left.digest, "right_digest":right.digest}
