"""Deterministic provenance contract for external production dependencies."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json


@dataclass(frozen=True)
class DependencyRecord:
    name: str
    version: str
    source: str
    license_id: str
    checksum: str


def evaluate_dependency_provenance(
    records: list[DependencyRecord],
    required_names: set[str],
) -> dict[str, object]:
    reasons: list[str] = []
    by_name: dict[str, DependencyRecord] = {}
    for record in records:
        if not all((record.name, record.version, record.source, record.license_id, record.checksum)):
            reasons.append("incomplete_dependency_record")
            continue
        if record.name in by_name:
            reasons.append(f"duplicate_dependency:{record.name}")
        by_name[record.name] = record

    missing = sorted(required_names - set(by_name))
    reasons.extend(f"missing_dependency:{name}" for name in missing)
    payload = {
        "ready": not reasons,
        "required_names": sorted(required_names),
        "recorded_names": sorted(by_name),
        "missing_names": missing,
        "reasons": reasons,
    }
    payload["fingerprint"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return payload
