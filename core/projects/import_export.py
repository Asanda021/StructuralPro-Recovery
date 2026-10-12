"""Deterministic project import/export with schema and integrity gates."""
from __future__ import annotations
import hashlib, json
from copy import deepcopy
from .integrity import validate_project

SCHEMA_VERSION = 1

def canonical_json(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",",":"))

def export_project(project: dict) -> str:
    result={"schema_version":SCHEMA_VERSION,"project":deepcopy(project)}
    validate=validate_project(result["project"])
    if not validate["valid"]: raise ValueError("cannot export invalid project")
    return canonical_json(result)

def export_bytes(project): return export_project(project).encode("utf-8")

def import_project(payload, *, allow_unknown_schema=False) -> dict:
    data=json.loads(payload.decode("utf-8") if isinstance(payload,(bytes,bytearray)) else payload)
    if not isinstance(data,dict) or "project" not in data: raise ValueError("invalid project package")
    if data.get("schema_version") != SCHEMA_VERSION and not allow_unknown_schema:
        raise ValueError("unsupported schema version")
    project=deepcopy(data["project"])
    validation=validate_project(project)
    if not validation["valid"]: raise ValueError(f"invalid project: {validation['issues']}")
    return project

def fingerprint(project): return hashlib.sha256(export_bytes(project)).hexdigest()

def round_trip(project):
    restored=import_project(export_project(project))
    return restored, fingerprint(project) == fingerprint(restored)
