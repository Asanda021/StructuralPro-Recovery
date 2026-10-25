"""Phase 5 transaction-failure behavior against a real SQLite database."""
from __future__ import annotations

import sqlite3
import subprocess
import sys

import pytest

from core.projects.store import ProjectStore


def test_lost_commit_acknowledgement_quarantines_connection(tmp_path, monkeypatch):
    """A commit that may have landed must never leave the live store usable."""
    path = tmp_path / "projects.db"
    original_connect = sqlite3.connect
    state = {"armed": False}

    class AckLossConnection(sqlite3.Connection):
        def commit(self):
            result = super().commit()
            if state["armed"]:
                state["armed"] = False
                raise sqlite3.OperationalError("simulated lost commit acknowledgement")
            return result

    def connect(*args, **kwargs):
        kwargs["factory"] = AckLossConnection
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", connect)
    store = ProjectStore(path)
    monkeypatch.setattr(sqlite3, "connect", original_connect)
    store.save("P", {"name": "synthetic", "marker": "acknowledged"})
    project = store.get("P")
    project["marker"] = "commit-outcome-unknown"
    state["armed"] = True

    with pytest.raises(sqlite3.OperationalError, match="lost commit acknowledgement"):
        store.save("P", project)
    with pytest.raises(RuntimeError, match="uncertain|identity changed"):
        store.get("P")
    with pytest.raises(RuntimeError, match="uncertain|identity changed"):
        store.save("P", project)
    store.close()

    # A fresh connection may inspect the durable outcome. The failed call itself
    # made no success claim; callers must reconcile against verified evidence.
    reopened = ProjectStore(path)
    try:
        assert reopened.get("P")["marker"] == "commit-outcome-unknown"
        assert reopened.get("P")["_meta"]["version"] == 2
        assert reopened.integrity_check()["ok"]
    finally:
        reopened.close()


def test_busy_before_write_reservation_is_retryable_after_lock_release(tmp_path):
    """SQLITE_BUSY at BEGIN IMMEDIATE has a known no-write outcome."""
    path = tmp_path / "projects.db"
    store = ProjectStore(path)
    store.save("P", {"name": "synthetic", "marker": 1})
    store.db.execute("PRAGMA busy_timeout=0")
    blocker = sqlite3.connect(path)
    blocker.execute("BEGIN IMMEDIATE")
    try:
        project = store.get("P")
        project["marker"] = 2
        with pytest.raises(sqlite3.OperationalError) as error:
            store.save("P", project)
        assert error.value.sqlite_errorcode == sqlite3.SQLITE_BUSY
    finally:
        blocker.rollback()
        blocker.close()

    assert store.save("P", project)["version"] == 2
    assert store.get("P")["marker"] == 2
    store.close()


def test_rollback_failure_quarantines_connection(tmp_path, monkeypatch):
    """If rollback itself fails, no later operation may trust the connection."""
    path = tmp_path / "projects.db"
    original_connect = sqlite3.connect
    state = {"armed": False}

    class RollbackFailureConnection(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            if state["armed"] and sql.startswith("INSERT OR REPLACE INTO revisions("):
                raise sqlite3.OperationalError("simulated write failure")
            return super().execute(sql, *args, **kwargs)

        def rollback(self):
            if state["armed"]:
                state["armed"] = False
                raise sqlite3.OperationalError("simulated rollback failure")
            return super().rollback()

    def connect(*args, **kwargs):
        kwargs["factory"] = RollbackFailureConnection
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", connect)
    store = ProjectStore(path)
    monkeypatch.setattr(sqlite3, "connect", original_connect)
    store.save("P", {"name": "synthetic", "marker": 1})
    project = store.get("P")
    project["marker"] = 2
    state["armed"] = True

    with pytest.raises(sqlite3.OperationalError, match="rollback failure"):
        store.save("P", project)
    with pytest.raises(RuntimeError, match="quarantined"):
        store.get("P")
    store.close()

    reopened = ProjectStore(path)
    try:
        assert reopened.get("P")["marker"] == 1
        assert reopened.get("P")["_meta"]["version"] == 1
    finally:
        reopened.close()


def test_process_death_inside_transaction_does_not_publish_partial_revision(tmp_path):
    """An OS-level process exit before COMMIT leaves the acknowledged revision intact."""
    path = tmp_path / "projects.db"
    store = ProjectStore(path)
    store.save("P", {"name": "synthetic", "marker": "acknowledged"})
    store.close()

    child = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os,sqlite3,sys; "
                "db=sqlite3.connect(sys.argv[1]); "
                "db.execute('BEGIN IMMEDIATE'); "
                "db.execute(\"UPDATE projects SET version=2,payload='{\\\"name\\\":\\\"partial\\\"}' WHERE id='P'\"); "
                "os._exit(73)"
            ),
            str(path),
        ],
        check=False,
    )
    assert child.returncode == 73

    reopened = ProjectStore(path)
    try:
        project = reopened.get("P")
        assert project["marker"] == "acknowledged"
        assert project["_meta"]["version"] == 1
        assert reopened.integrity_check()["ok"]
    finally:
        reopened.close()
