"""Append-only audit trail for project mutations."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from copy import deepcopy

@dataclass(frozen=True)
class AuditRecord:
    timestamp: str
    action: str
    entity: str
    entity_id: str
    before: object = None
    after: object = None
    actor: str | None = None

    def to_dict(self): return asdict(self)

class AuditTrail:
    ACTIONS = {"create","update","delete","restore","import","export"}
    def __init__(self, records=None):
        self._records=[dict(r) for r in (records or [])]
    def record(self, action, entity, entity_id="", before=None, after=None, actor=None, timestamp=None):
        if action not in self.ACTIONS: raise ValueError(f"unsupported audit action: {action}")
        rec=AuditRecord(timestamp or datetime.now(timezone.utc).isoformat(), action, str(entity), str(entity_id), deepcopy(before), deepcopy(after), actor)
        self._records.append(rec.to_dict()); return rec.to_dict()
    def list(self): return deepcopy(self._records)
    def export(self): return self.list()
    def __len__(self): return len(self._records)
