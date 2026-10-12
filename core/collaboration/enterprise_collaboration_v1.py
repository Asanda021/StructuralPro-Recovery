"""Deterministic enterprise collaboration boundary with evidence and revision safety."""
from dataclasses import dataclass, asdict
from hashlib import sha256
import json


ALLOWED_ROLES = {"viewer", "editor", "reviewer", "approver"}
ALLOWED_STATUSES = {"draft", "review", "approved", "rejected"}


@dataclass(frozen=True)
class CollaborationChange:
    change_id: str
    project_id: str
    actor_id: str
    role: str
    revision: str
    source_ids: tuple[str, ...]
    payload_hash: str
    status: str = "draft"


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def validate_change(change: CollaborationChange) -> None:
    if not all((change.change_id, change.project_id, change.actor_id, change.revision, change.payload_hash)):
        raise ValueError("change identity, revision and payload hash are required")
    if not change.source_ids:
        raise ValueError("collaboration change requires source evidence")
    if change.role not in ALLOWED_ROLES:
        raise ValueError("invalid collaboration role")
    if change.status not in ALLOWED_STATUSES:
        raise ValueError("invalid collaboration status")


def transition(change: CollaborationChange, target: str) -> CollaborationChange:
    validate_change(change)
    if target not in ALLOWED_STATUSES:
        raise ValueError("invalid target status")
    if target == "approved" and change.role not in {"approver"}:
        raise ValueError("approval requires approver role")
    return CollaborationChange(**{**asdict(change), "status": target})


def fingerprint(change: CollaborationChange) -> str:
    validate_change(change)
    return sha256(_canonical(asdict(change)).encode("utf-8")).hexdigest()
