"""P361-P370 deterministic operational-evidence archive boundary."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .operational_evidence_snapshot_v1 import validate_snapshot, verify_snapshot

SCHEMA_VERSION = "v1"
REQUIRED_KEYS = frozenset({
    "schema_version", "app_version", "snapshot", "archive_sha256",
})


def _canonical(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def archive_from_snapshot(snapshot: Mapping[str, Any], *, archive_id: str) -> dict[str, Any]:
    if not verify_snapshot(snapshot):
        raise ValueError("cannot archive invalid snapshot")
    identifier = str(archive_id).strip()
    if not identifier:
        raise ValueError("archive_id is required")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "app_version": str(snapshot["app_version"]),
        "archive_id": identifier,
        "snapshot": dict(snapshot),
    }
    payload["archive_sha256"] = hashlib.sha256(_canonical(payload)).hexdigest()
    return payload


def validate_archive(archive: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(archive, Mapping):
        return ["archive must be a mapping"]
    missing = sorted(REQUIRED_KEYS - set(archive))
    if missing:
        errors.append(f"missing keys: {','.join(missing)}")
    if archive.get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported schema_version")
    if not str(archive.get("app_version", "")).strip():
        errors.append("app_version is required")
    if not str(archive.get("archive_id", "")).strip():
        errors.append("archive_id is required")
    snapshot = archive.get("snapshot")
    if not isinstance(snapshot, Mapping):
        errors.append("snapshot must be a mapping")
    elif not verify_snapshot(snapshot):
        errors.append("snapshot integrity verification failed")
    digest = archive.get("archive_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        errors.append("invalid archive_sha256")
    return errors


def verify_archive(archive: Mapping[str, Any]) -> bool:
    if validate_archive(archive):
        return False
    stored = archive["archive_sha256"]
    payload = {k: archive[k] for k in archive if k != "archive_sha256"}
    return stored == hashlib.sha256(_canonical(payload)).hexdigest()


def serialize_archive(archive: Mapping[str, Any]) -> str:
    if not verify_archive(archive):
        raise ValueError("cannot serialize invalid archive")
    return json.dumps(dict(archive), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def restore_archive(serialized: str) -> dict[str, Any]:
    try:
        value = json.loads(serialized)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid archive JSON") from exc
    if not verify_archive(value):
        raise ValueError("archive integrity verification failed")
    return dict(value)


def retention_key(archive: Mapping[str, Any]) -> tuple[str, str]:
    if not verify_archive(archive):
        raise ValueError("invalid archive")
    return str(archive["app_version"]), str(archive["archive_id"])


def replay_archive(archive: Mapping[str, Any], snapshot: Mapping[str, Any]) -> bool:
    if not verify_archive(archive) or not verify_snapshot(snapshot):
        return False
    return dict(archive["snapshot"]) == dict(snapshot)
