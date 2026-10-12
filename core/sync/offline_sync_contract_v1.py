"""Deterministic offline sync contract with fail-closed conflict handling."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from typing import Any, Literal

ConflictPolicy = Literal["reject", "manual_review"]

@dataclass(frozen=True)
class SyncEnvelope:
    operation_id: str
    project_id: str
    base_revision: str
    client_revision: str
    payload: dict[str, Any]
    conflict_policy: ConflictPolicy = "manual_review"

    def validate(self) -> None:
        if not all(isinstance(x, str) and x.strip() for x in (self.operation_id, self.project_id, self.base_revision, self.client_revision)):
            raise ValueError("sync identity fields are required")
        if not isinstance(self.payload, dict):
            raise ValueError("payload must be an object")
        if self.conflict_policy not in ("reject", "manual_review"):
            raise ValueError("unsupported conflict policy")

    def canonical(self) -> str:
        self.validate()
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def fingerprint(self) -> str:
        return sha256(self.canonical().encode()).hexdigest()

@dataclass(frozen=True)
class SyncDecision:
    status: Literal["accepted", "conflict"]
    reason: str
    envelope_fingerprint: str

def decide_sync(envelope: SyncEnvelope, *, server_revision: str) -> SyncDecision:
    envelope.validate()
    fp = envelope.fingerprint()
    if envelope.base_revision != server_revision:
        return SyncDecision("conflict", "base revision differs; server state must not be overwritten", fp)
    return SyncDecision("accepted", "base revision matches", fp)
