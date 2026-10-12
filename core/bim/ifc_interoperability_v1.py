"""Fail-closed IFC interoperability contract; no geometry or quantity invention."""
from dataclasses import dataclass, asdict
from hashlib import sha256
import json

SUPPORTED_IFC_VERSIONS = {"IFC4", "IFC4X3"}

@dataclass(frozen=True)
class InterchangeRecord:
    project_id: str
    revision: str
    source_id: str
    discipline: str
    ifc_version: str
    external_id: str
    element_type: str
    properties: tuple = ()
    quantities: tuple = ()

def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def validate_record(record: InterchangeRecord):
    required=(record.project_id, record.revision, record.source_id, record.discipline,
              record.ifc_version, record.external_id, record.element_type)
    if not all(required):
        raise ValueError("IFC interchange identity fields are required")
    if record.ifc_version not in SUPPORTED_IFC_VERSIONS:
        raise ValueError("unsupported IFC version")
    if not isinstance(record.properties, tuple) or not isinstance(record.quantities, tuple):
        raise ValueError("properties and quantities must be immutable tuples")

def canonical_record(record):
    validate_record(record)
    return _canonical(asdict(record))

def record_fingerprint(record):
    return sha256(canonical_record(record).encode("utf-8")).hexdigest()

def round_trip_verify(source: InterchangeRecord, returned: InterchangeRecord):
    validate_record(source); validate_record(returned)
    if source.external_id != returned.external_id:
        raise ValueError("round-trip external identity mismatch")
    if source.project_id != returned.project_id or source.revision != returned.revision:
        raise ValueError("round-trip project/revision mismatch")
    if record_fingerprint(source) != record_fingerprint(returned):
        raise ValueError("round-trip fingerprint mismatch")
    return True
