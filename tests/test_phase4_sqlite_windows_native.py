"""Native Windows SQLite locking and verified persistence, not POSIX rename semantics."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

from core.projects.store import ProjectStore
from core.recovery.recovery import backup_database, require_project_history_consistency


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows NTFS file-sharing semantics")


def test_windows_live_connection_blocks_rename_and_preserves_committed_revisions(tmp_path: Path):
    db = tmp_path / "projects.db"
    moved = tmp_path / "projects.live"
    store = ProjectStore(db)
    try:
        assert store.save("P", {"name": "SYNTHETIC", "exact": "0.000000000000000001"})["version"] == 1
        # Win32 normally does not grant delete-sharing on an open SQLite handle.
        # The POSIX DBMOVED fault injector cannot assume a rename succeeds here.
        with pytest.raises(PermissionError) as error:
            db.rename(moved)
        assert error.value.winerror == 32
        assert db.is_file() and not moved.exists()

        row = store.get("P")
        assert row["_meta"]["version"] == 1
        row["marker"] = "after-denied-rename"
        assert store.save("P", row)["version"] == 2
        assert store.integrity_check()["ok"]
    finally:
        store.close()

    with sqlite3.connect(db) as connection:
        require_project_history_consistency(connection)
        assert connection.execute("SELECT version FROM projects WHERE id='P'").fetchone()[0] == 2

    verified_backup = tmp_path / "verified.db"
    backup_database(db, verified_backup)
    restored = ProjectStore(verified_backup)
    try:
        row = restored.get("P")
        assert row["_meta"]["version"] == 2
        assert row["exact"] == "0.000000000000000001"
        assert row["marker"] == "after-denied-rename"
    finally:
        restored.close()


def test_windows_closed_database_can_be_moved_then_reopened_safely(tmp_path: Path):
    db = tmp_path / "projects.db"
    moved = tmp_path / "projects.moved"
    store = ProjectStore(db)
    try:
        assert store.save("P", {"name": "SYNTHETIC", "marker": "committed"})["version"] == 1
    finally:
        store.close()

    db.rename(moved)
    assert moved.is_file() and not db.exists()
    moved.rename(db)

    restored = ProjectStore(db)
    try:
        assert restored.get("P")["marker"] == "committed"
        assert restored.get("P")["_meta"]["version"] == 1
        assert restored.integrity_check()["ok"]
    finally:
        restored.close()
