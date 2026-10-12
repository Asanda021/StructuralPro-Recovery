"""P122 collaboration primitives: revision-safe edits and append-only audit events."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json

@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    project_id: str
    actor_id: str
    action: str
    revision: int
    payload_digest: str
    created_at: str

class RevisionConflict(RuntimeError): pass

def digest(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return sha256(raw).hexdigest()

class CollaborationStore:
    def __init__(self):
        self._revisions = {}
        self._events = []
    def revision(self, project_id: str) -> int:
        return self._revisions.get(project_id, 0)
    def commit(self, project_id: str, actor_id: str, expected_revision: int, action: str, payload: object) -> AuditEvent:
        current = self.revision(project_id)
        if expected_revision != current:
            raise RevisionConflict(f"expected revision {expected_revision}, current {current}")
        new_revision = current + 1
        self._revisions[project_id] = new_revision
        event = AuditEvent(
            event_id=sha256(f"{project_id}:{new_revision}:{actor_id}:{action}".encode()).hexdigest()[:16],
            project_id=project_id, actor_id=actor_id, action=action, revision=new_revision,
            payload_digest=digest(payload),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._events.append(event)
        return event
    def events(self, project_id: str):
        return tuple(e for e in self._events if e.project_id == project_id)
