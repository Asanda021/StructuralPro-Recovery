"""P351-P360 deterministic operational-evidence snapshot/replay boundary."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from .operational_evidence_v1 import OperationalEvidence

SCHEMA_VERSION = "v1"
REQUIRED_KEYS = frozenset({
    "schema_version", "app_version", "ready", "checks", "errors",
    "fingerprint",
})


def _canonical(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def snapshot_from_evidence(
    evidence: OperationalEvidence, *, app_version: str
) -> dict[str, Any]:
    version = str(app_version).strip()
    if not version:
        raise ValueError("app_version is required")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "app_version": version,
        "ready": bool(evidence.ready),
        "checks": [[str(name), bool(ok)] for name, ok in evidence.checks],
        "errors": [str(error) for error in evidence.errors],
        "fingerprint": str(evidence.fingerprint),
    }
    payload["snapshot_sha256"] = hashlib.sha256(_canonical(payload)).hexdigest()
    return payload


def validate_snapshot(snapshot: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(snapshot, Mapping):
        return ["snapshot must be a mapping"]
    missing = sorted(REQUIRED_KEYS - set(snapshot))
    if missing:
        errors.append(f"missing keys: {','.join(missing)}")
    if snapshot.get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported schema_version")
    if not str(snapshot.get("app_version", "")).strip():
        errors.append("app_version is required")
    if not isinstance(snapshot.get("ready"), bool):
        errors.append("ready must be bool")
    checks = snapshot.get("checks")
    if not isinstance(checks, list):
        errors.append("checks must be a list")
    else:
        for i, item in enumerate(checks):
            if not isinstance(item, list) or len(item) != 2:
                errors.append(f"checks[{i}] must be [name, bool]")
            elif not isinstance(item[0], str) or not isinstance(item[1], bool):
                errors.append(f"checks[{i}] has invalid types")
    if not isinstance(snapshot.get("errors"), list) or any(
        not isinstance(x, str) for x in snapshot.get("errors", [])
    ):
        errors.append("errors must be a list of strings")
    if not isinstance(snapshot.get("fingerprint"), str) or not snapshot.get("fingerprint"):
        errors.append("fingerprint is required")
    digest = snapshot.get("snapshot_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        errors.append("invalid snapshot_sha256")
    return errors


def verify_snapshot(snapshot: Mapping[str, Any]) -> bool:
    if validate_snapshot(snapshot):
        return False
    stored = snapshot.get("snapshot_sha256")
    payload = {k: snapshot[k] for k in snapshot if k != "snapshot_sha256"}
    return stored == hashlib.sha256(_canonical(payload)).hexdigest()


def serialize_snapshot(snapshot: Mapping[str, Any]) -> str:
    if not verify_snapshot(snapshot):
        raise ValueError("cannot serialize invalid snapshot")
    return json.dumps(dict(snapshot), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def restore_snapshot(serialized: str) -> dict[str, Any]:
    try:
        value = json.loads(serialized)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid snapshot JSON") from exc
    if not verify_snapshot(value):
        raise ValueError("snapshot integrity verification failed")
    return dict(value)


def replay_matches(snapshot: Mapping[str, Any], evidence: OperationalEvidence) -> bool:
    if not verify_snapshot(snapshot):
        return False
    expected = snapshot_from_evidence(evidence, app_version=str(snapshot["app_version"]))
    return expected == dict(snapshot)
