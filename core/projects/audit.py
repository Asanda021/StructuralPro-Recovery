"""Append-only audit trail for project mutations."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from copy import deepcopy
from core.platform.audit_integrity import GENESIS, event_digest, verify_chain
from core.security_hardening_v2 import SecurityPrincipal, require_authorized

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
    ACTIONS = {"create","update","delete","restore","import","export","open","authorize"}
    def __init__(self, records=None):
        self._records=[dict(r) for r in (records or [])]
    def record(self, action, entity, entity_id="", before=None, after=None, actor=None, timestamp=None):
        if action not in self.ACTIONS: raise ValueError(f"unsupported audit action: {action}")
        rec=AuditRecord(timestamp or datetime.now(timezone.utc).isoformat(), action, str(entity), str(entity_id), deepcopy(before), deepcopy(after), actor)
        self._records.append(rec.to_dict()); return rec.to_dict()
    def record_controlled(
        self, *, action, entity, entity_id, principal: SecurityPrincipal,
        project_id, required_roles, revision_before, revision_after, reference,
        status="success", before=None, after=None, timestamp=None,
    ):
        """Append a role-bound, revision-aware and tamper-evident audit event.

        Authorization failures are themselves recorded as failed attempts.  No
        successful revision may skip an intermediate version, and a failed
        operation cannot claim a resulting revision.
        """
        if action not in self.ACTIONS:
            raise ValueError(f"unsupported audit action: {action}")
        if status not in {"success", "failure"}:
            raise ValueError("audit status must be success or failure")
        if not str(reference or "").strip():
            raise ValueError("audit reference is required")
        for value in (revision_before, revision_after):
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 1):
                raise ValueError("invalid audit revision")
        if status == "failure" and revision_after is not None:
            raise ValueError("failed audit event cannot claim a resulting revision")
        if (status == "success" and revision_before is not None
                and revision_after is not None
                and revision_after not in {revision_before, revision_before + 1}):
            raise ValueError("invalid audit revision transition")
        if self._records and not all("hash" in item and "previous_hash" in item for item in self._records):
            raise ValueError("legacy unsealed records cannot be extended as a controlled audit chain")

        observed_status=status
        authorization_error=None
        try:
            require_authorized(principal, str(project_id), tuple(required_roles))
        except (PermissionError, ValueError) as exc:
            observed_status="failure"
            revision_after=None
            authorization_error=exc
        event={
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
            "action": action,
            "entity": str(entity),
            "entity_id": str(entity_id),
            "before": deepcopy(before),
            "after": deepcopy(after),
            "actor": principal.user_id,
            "actor_role": principal.role,
            "project_id": str(project_id),
            "revision_before": revision_before,
            "revision_after": revision_after,
            "reference": str(reference),
            "status": observed_status,
        }
        previous=self._records[-1]["hash"] if self._records else GENESIS
        digest=event_digest(event, previous)
        event["previous_hash"]=previous
        event["hash"]=digest
        self._records.append(event)
        if authorization_error is not None:
            raise authorization_error
        return deepcopy(event)
    def verify(self): return verify_chain(self._records)
    def list(self): return deepcopy(self._records)
    def export(self): return self.list()
    def __len__(self): return len(self._records)
