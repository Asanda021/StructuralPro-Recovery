"""Deterministic integration boundary for AEC exchange contracts."""
from dataclasses import dataclass, asdict
from hashlib import sha256
import json


ALLOWED_FORMATS = {"json", "csv", "xlsx", "ifc", "dxf", "pdf"}
ALLOWED_STATUSES = {"draft", "validated", "rejected"}


@dataclass(frozen=True)
class IntegrationEnvelope:
    envelope_id: str
    project_id: str
    source_id: str
    revision: str
    format: str
    payload_hash: str
    status: str = "draft"


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def validate(envelope: IntegrationEnvelope) -> None:
    if not all((envelope.envelope_id, envelope.project_id, envelope.source_id, envelope.revision, envelope.payload_hash)):
        raise ValueError("integration identity, revision and payload hash are required")
    if envelope.format not in ALLOWED_FORMATS:
        raise ValueError("unsupported integration format")
    if envelope.status not in ALLOWED_STATUSES:
        raise ValueError("invalid integration status")


def validate_envelope(envelope: IntegrationEnvelope) -> IntegrationEnvelope:
    validate(envelope)
    return IntegrationEnvelope(**{**asdict(envelope), "status": "validated"})


def fingerprint(envelope: IntegrationEnvelope) -> str:
    validate(envelope)
    return sha256(_canonical(asdict(envelope)).encode("utf-8")).hexdigest()
