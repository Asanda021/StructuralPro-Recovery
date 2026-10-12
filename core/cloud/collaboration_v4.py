"""P65 — fail-closed collaboration policy and deterministic merge primitives."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json

ROLES = {"owner", "admin", "editor", "reviewer", "viewer"}
OPS = {"create", "update", "review", "approve", "archive", "restore"}
ROLE_OPS = {
    "owner": OPS,
    "admin": OPS - {"approve"},
    "editor": {"create", "update"},
    "reviewer": {"review", "approve"},
    "viewer": {"review"},
}

@dataclass(frozen=True)
class Event:
    project_id: str
    revision: int
    actor_id: str
    role: str
    base_fingerprint: str
    payload: dict
    operation: str

def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)

def fingerprint(payload: dict) -> str:
    return sha256(canonical_json(payload).encode("utf-8")).hexdigest()

def validate_event(e: Event) -> None:
    if not e.project_id or not e.actor_id or e.revision < 1:
        raise ValueError("invalid event identity")
    if e.role not in ROLES or e.operation not in OPS:
        raise ValueError("invalid role/operation")
    if e.operation not in ROLE_OPS[e.role]:
        raise ValueError("role is not authorized for operation")
    if len(e.base_fingerprint) != 64 or any(c not in "0123456789abcdef" for c in e.base_fingerprint.lower()):
        raise ValueError("invalid base fingerprint")
    if not isinstance(e.payload, dict):
        raise ValueError("event payload must be an object")

def apply_event(current_revision: int, current_fingerprint: str, e: Event) -> dict:
    validate_event(e)
    if current_revision < 0 or len(current_fingerprint) != 64:
        raise ValueError("invalid current state")
    if e.revision <= current_revision:
        return {"status": "stale_or_duplicate", "accepted": False, "conflict": False}
    if e.base_fingerprint != current_fingerprint:
        return {"status": "conflict", "accepted": False, "conflict": True, "requires_review": True}
    return {
        "status": "accepted",
        "accepted": True,
        "conflict": False,
        "revision": e.revision,
        "fingerprint": fingerprint(e.payload),
        "requires_review": e.operation == "review",
    }

def three_way(base: dict, local: dict, remote: dict) -> dict:
    result = dict(base)
    conflicts = []
    for key in set(base) | set(local) | set(remote):
        b, l, r = base.get(key), local.get(key), remote.get(key)
        if l == r:
            result[key] = l
        elif l == b:
            result[key] = r
        elif r == b:
            result[key] = l
        else:
            conflicts.append(key)
    return {"merged": result, "conflicts": sorted(conflicts), "requires_review": bool(conflicts)}
