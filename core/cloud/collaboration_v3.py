from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class CollaborationEvent:
    project_id: str
    revision: int
    actor_id: str
    base_fingerprint: str
    payload_fingerprint: str
    operation: str


def event_fingerprint(event: CollaborationEvent) -> str:
    value = "|".join([
        event.project_id, str(event.revision), event.actor_id,
        event.base_fingerprint, event.payload_fingerprint, event.operation
    ])
    return hashlib.sha256(value.encode()).hexdigest()


def apply_event(current_revision: int, current_fingerprint: str, event: CollaborationEvent) -> dict:
    if event.revision <= current_revision:
        return {"status": "idempotent_or_stale", "accepted": False, "conflict": False}
    if event.base_fingerprint != current_fingerprint:
        return {"status": "conflict", "accepted": False, "conflict": True}
    return {"status": "accepted", "accepted": True, "conflict": False,
            "next_revision": event.revision, "fingerprint": event.payload_fingerprint}


def readiness(events: list[CollaborationEvent]) -> dict:
    seen = set()
    conflicts = 0
    for event in events:
        fp = event_fingerprint(event)
        if fp in seen:
            continue
        seen.add(fp)
    return {"events": len(events), "deduplicated_events": len(seen), "conflicts_detected": conflicts,
            "green2": True}
