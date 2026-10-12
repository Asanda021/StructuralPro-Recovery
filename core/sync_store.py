"""Atomic, integrity-checked JSON persistence for the offline sync outbox."""
from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

from .sync_engine import SyncRecord

_SCHEMA_VERSION = 1


def _canonical_records(records: list[SyncRecord]) -> str:
    return json.dumps(
        [record.to_dict() for record in records],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _digest(records: list[SyncRecord]) -> str:
    return hashlib.sha256(_canonical_records(records).encode("utf-8")).hexdigest()


class JsonSyncStore:
    def __init__(self, path):
        self.path = Path(path)

    def save(self, records):
        rows = list(records)
        if not all(isinstance(record, SyncRecord) for record in rows):
            raise TypeError("sync store accepts SyncRecord values only")

        document = {
            "schema_version": _SCHEMA_VERSION,
            "records": [record.to_dict() for record in rows],
            "sha256": _digest(rows),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(
            json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        temp.replace(self.path)

    def load(self):
        if not self.path.exists():
            return []

        document: Any = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or document.get("schema_version") != _SCHEMA_VERSION:
            raise ValueError("unsupported sync store schema")
        rows = document.get("records")
        expected = document.get("sha256")
        if not isinstance(rows, list) or not isinstance(expected, str):
            raise ValueError("invalid sync store envelope")

        records = [SyncRecord.from_dict(row) for row in rows]
        actual = _digest(records)
        if not hmac.compare_digest(actual, expected):
            raise ValueError("sync store integrity check failed")
        return records

    def fingerprint(self):
        return _digest(self.load())
