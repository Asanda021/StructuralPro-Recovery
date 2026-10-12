"""Deterministic native DWG/DXF production boundary.

This module deliberately treats CAD files as evidence-bearing artifacts.
It does not infer geometry, dimensions, quantities, layers, or engineering
values from opaque payloads. Native production is represented by validated
metadata plus an immutable artifact fingerprint.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any, Mapping


SUPPORTED_DXF_VERSIONS = frozenset({"AC1027", "AC1032"})  # R2013 / R2018
SUPPORTED_FORMATS = frozenset({"DXF", "DWG"})


@dataclass(frozen=True)
class CadArtifactRecord:
    project_id: str
    revision: str
    source_id: str
    discipline: str
    format: str
    version: str
    external_id: str
    artifact_fingerprint: str
    metadata: tuple[tuple[str, str], ...] = ()


def _canonical(record: CadArtifactRecord) -> str:
    payload = asdict(record)
    payload["metadata"] = list(record.metadata)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def validate_record(record: CadArtifactRecord) -> None:
    required = {
        "project_id": record.project_id,
        "revision": record.revision,
        "source_id": record.source_id,
        "discipline": record.discipline,
        "format": record.format,
        "version": record.version,
        "external_id": record.external_id,
        "artifact_fingerprint": record.artifact_fingerprint,
    }
    if any(not isinstance(value, str) or not value.strip() for value in required.values()):
        raise ValueError("CAD record identity fields must be non-empty strings")
    if record.format not in SUPPORTED_FORMATS:
        raise ValueError("Unsupported CAD format")
    if record.format == "DXF" and record.version not in SUPPORTED_DXF_VERSIONS:
        raise ValueError("Unsupported DXF version")
    if record.format == "DWG" and not record.version.startswith("AC"):
        raise ValueError("DWG version must use an ACxxxx identifier")
    if not isinstance(record.metadata, tuple):
        raise ValueError("metadata must be an immutable tuple")


def canonical_record(record: CadArtifactRecord) -> str:
    validate_record(record)
    return _canonical(record)


def record_fingerprint(record: CadArtifactRecord) -> str:
    """Fingerprint validated metadata, not unparsed CAD geometry."""
    return hashlib.sha256(canonical_record(record).encode("utf-8")).hexdigest()


def round_trip_verify(
    original: CadArtifactRecord,
    returned: CadArtifactRecord,
) -> bool:
    """Fail-closed verification for an exported/re-imported CAD boundary."""
    try:
        validate_record(original)
        validate_record(returned)
    except ValueError:
        return False

    if (
        original.project_id != returned.project_id
        or original.revision != returned.revision
        or original.source_id != returned.source_id
        or original.external_id != returned.external_id
        or original.format != returned.format
        or original.version != returned.version
        or original.discipline != returned.discipline
    ):
        return False

    return record_fingerprint(original) == record_fingerprint(returned)


def build_artifact_fingerprint(payload: bytes) -> str:
    """Return a deterministic SHA-256 for the exact CAD artifact bytes."""
    if not isinstance(payload, bytes) or not payload:
        raise ValueError("CAD artifact payload must be non-empty bytes")
    return hashlib.sha256(payload).hexdigest()


def metadata_from_mapping(values: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    """Normalize export metadata without interpreting engineering meaning."""
    if not isinstance(values, Mapping):
        raise ValueError("metadata must be a mapping")
    normalized = []
    for key, value in values.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("metadata keys must be non-empty strings")
        if isinstance(value, (dict, list, set, tuple)):
            raise ValueError("metadata values must be scalar")
        normalized.append((key, str(value)))
    return tuple(sorted(normalized))
