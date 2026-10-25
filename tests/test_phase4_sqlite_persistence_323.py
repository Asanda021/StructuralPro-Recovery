"""Regression: 323 large transactions through the real ProjectStore.

This deterministic stress test does not establish the historical SQLite root cause.
"""
import json
import sqlite3
from core.projects.store import ProjectStore


def test_323_full_project_store_transactions_persist_and_reopen(tmp_path):
    path = tmp_path / "projects.db"
    store = ProjectStore(path)
    payload = {"name": "SYNTHETIC persistence test", "text": "a" * 373950}
    try:
        for index in range(1, 324):
            if index > 1:
                payload = store.get("P")
            payload["text"] = ("a" * 373950) + f"/revision-{index:05d}"
            result = store.save("P", payload)
            assert result["version"] == index
            if index in (1, 64, 128, 192, 256, 323):
                with sqlite3.connect(path) as separate:
                    assert separate.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                    main = separate.execute(
                        "SELECT version,CAST(payload AS BLOB) FROM projects WHERE id='P'"
                    ).fetchone()
                    latest = separate.execute(
                        "SELECT CAST(payload AS BLOB) FROM revisions "
                        "WHERE project_id='P' AND version=?", (index,)
                    ).fetchone()[0]
                    assert main[0] == index and main[1] == latest
        assert store.get("P")["_meta"]["version"] == 323
    finally:
        store.close()
    reopened = ProjectStore(path)
    try:
        project = reopened.get("P")
        assert project["_meta"]["version"] == 323
        assert project["text"].endswith("/revision-00323")
        assert reopened.integrity_check()["ok"] is True
        with sqlite3.connect(path) as separate:
            assert separate.execute("SELECT count(*) FROM revisions").fetchone()[0] == 323
            committed = separate.execute("SELECT payload FROM projects WHERE id='P'").fetchone()[0]
            assert json.loads(committed)["text"] == project["text"]
    finally:
        reopened.close()
