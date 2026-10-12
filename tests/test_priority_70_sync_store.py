from pathlib import Path

import pytest

from core.sync_store import JsonSyncStore
from core.sync_engine import SyncRecord


def _record(version=1):
    return SyncRecord(
        record_id=f"dev:building:P1:{version}",
        entity_type="building",
        entity_id="P1",
        operation="upsert",
        payload={"name": "Demo", "version": version},
        base_version=version - 1,
        version=version,
        device_id="dev-1",
        timestamp="2026-10-03T00:00:00+00:00",
    )


def test_sync_store_round_trip_and_fingerprint(tmp_path: Path):
    store = JsonSyncStore(tmp_path / "sync.json")
    rows = [_record()]
    store.save(rows)
    assert store.load() == rows
    assert len(store.fingerprint()) == 64


def test_sync_store_rejects_tampering(tmp_path: Path):
    path = tmp_path / "sync.json"
    store = JsonSyncStore(path)
    store.save([_record()])
    text = path.read_text(encoding="utf-8").replace("Demo", "Tampered")
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        store.load()


def test_sync_store_rejects_unknown_schema(tmp_path: Path):
    path = tmp_path / "sync.json"
    path.write_text('{"schema_version":99,"records":[],"sha256":"x"}', encoding="utf-8")
    with pytest.raises(ValueError, match="schema"):
        JsonSyncStore(path).load()


def test_sync_store_rejects_non_sync_records(tmp_path: Path):
    with pytest.raises(TypeError, match="SyncRecord"):
        JsonSyncStore(tmp_path / "sync.json").save([{"record_id": "x"}])
