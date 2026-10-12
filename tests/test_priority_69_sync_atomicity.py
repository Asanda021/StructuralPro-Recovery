from pathlib import Path
from core.sync.manager import SyncManager
from core.sync.offline_queue import OfflineQueue


class Provider:
    def __init__(self, fail=False):
        self.fail = fail

    def push(self, records):
        if self.fail:
            raise RuntimeError("offline")
        return {"pushed": 1, "acknowledged_ids": [records[0]["record_id"]]}

    def pull(self, project_id):
        return []


class LegacyProvider:
    def push(self, records):
        return {"pushed": len(records)}

    def pull(self, project_id):
        return []


def test_sync_acknowledges_only_pushed_records(tmp_path: Path):
    q = OfflineQueue(tmp_path / "queue.json")
    q.enqueue({"record_id": "a", "project_id": "p"})
    q.enqueue({"record_id": "b", "project_id": "p"})
    result = SyncManager(Provider(), q).sync("p")
    assert result["uploaded"] == 1
    assert [r["record_id"] for r in q.peek()] == ["b"]


def test_push_failure_preserves_queue(tmp_path: Path):
    q = OfflineQueue(tmp_path / "queue.json")
    q.enqueue({"record_id": "a", "project_id": "p"})
    result = SyncManager(Provider(True), q).sync("p")
    assert result["status"] == "synced"
    assert result["errors"] == ["push_failed:RuntimeError"]
    assert q.peek()[0]["record_id"] == "a"


def test_legacy_provider_fallback_acknowledges_exact_pushed_rows(tmp_path: Path):
    q = OfflineQueue(tmp_path / "queue.json")
    q.enqueue({"project_id": "p", "version": 1, "payload": {"name": "A"}})
    q.enqueue({"project_id": "p", "version": 2, "payload": {"name": "B"}})
    result = SyncManager(LegacyProvider(), q).sync("p")
    assert result["uploaded"] == 2
    assert q.peek() == []
