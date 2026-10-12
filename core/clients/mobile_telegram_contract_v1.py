"""Production-safe mobile/Telegram client contracts for StructuralPro.

Client layers are transport adapters only. They never invent engineering values.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from typing import Any, Literal

Channel = Literal["android", "telegram", "web"]
MAX_PAYLOAD_BYTES = 256_000

@dataclass(frozen=True)
class ClientEnvelope:
    request_id: str
    project_id: str
    revision: str
    channel: Channel
    operation: str
    payload: dict[str, Any]
    evidence_refs: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.request_id.strip() or not self.project_id.strip() or not self.revision.strip():
            raise ValueError("request_id, project_id and revision are required")
        if not self.operation.strip():
            raise ValueError("operation is required")
        if not isinstance(self.payload, dict):
            raise ValueError("payload must be an object")
        raw = json.dumps(self.payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        if len(raw) > MAX_PAYLOAD_BYTES:
            raise ValueError("payload exceeds client limit")
        if any(not ref.strip() for ref in self.evidence_refs):
            raise ValueError("evidence_refs must be non-empty strings")

    def canonical(self) -> str:
        self.validate()
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def fingerprint(self) -> str:
        return sha256(self.canonical().encode()).hexdigest()

@dataclass(frozen=True)
class ClientCapabilities:
    client_version: str
    protocol_version: str
    offline_queue: bool
    attachments: bool
    rtl: bool
    max_attachment_bytes: int

    def validate(self) -> None:
        if not self.client_version or not self.protocol_version:
            raise ValueError("client and protocol versions are required")
        if self.max_attachment_bytes <= 0:
            raise ValueError("max_attachment_bytes must be positive")

def accept_envelope(envelope: ClientEnvelope, *, supported_protocol: str) -> str:
    envelope.validate()
    if supported_protocol != "1":
        raise ValueError("unsupported protocol")
    return envelope.fingerprint()
