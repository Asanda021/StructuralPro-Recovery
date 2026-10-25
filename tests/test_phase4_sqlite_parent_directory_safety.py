"""Regression for replacing a SQLite parent directory, not merely its DB file.

Uses only disposable POSIX tmp_path fixtures. No user databases touched and
no historical actor is inferred from the synthetic swaps.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.projects.store import ProjectStore

pytestmark = pytest.mark.skipif(os.name != "posix", reason="requires POSIX directory renames and hard links")


def _make_store(tmp_path: Path) -> tuple[ProjectStore, Path, Path]:
    directory = tmp_path / "project" / "engineering" / "db"
    directory.mkdir(parents=True)
    db = directory / "projects.db"
    store = ProjectStore(db)
    store.save("P", {"name": "synthetic", "history": ["12.5", "45", "75"], "exact": "0.000000000000000001"})
    assert store.get("P")["_meta"]["version"] == 1
    return store, directory, db


def _swap_directory(directory: Path, replacement: Path) -> Path:
    parked = directory.with_name("db-held")
    assert not parked.exists()
    directory.rename(parked)
    replacement.rename(directory)
    return parked


def test_parent_replaced_with_different_db_fails_closed(tmp_path):
    store, directory, db = _make_store(tmp_path)
    candidate = directory.with_name("db-candidate")
    candidate.mkdir()
    fresh = ProjectStore(candidate / "projects.db")
    fresh.save("P", {"name": "replacement", "marker": "stale"})
    fresh.close()
    parked = _swap_directory(directory, candidate)
    try:
        assert (parked / "projects.db").stat().st_ino != db.stat().st_ino
        for action in (
            lambda: store.get("P"), store.list, lambda: store.revisions("P"),
            lambda: store.save("P", {"name": "unsafe"}),
            lambda: store.backup(tmp_path / "forbidden.db"), store.integrity_check,
        ):
            with pytest.raises(RuntimeError, match="database identity changed"):
                action()
        assert not (tmp_path / "forbidden.db").exists()
        assert ProjectStore(db).get("P")["marker"] == "stale"
        # Even after restoring the pathname, the displaced store remains unsafe.
        directory.rename(directory.with_name("replacement-held"))
        parked.rename(directory)
        with pytest.raises(RuntimeError, match="database identity changed"):
            store.get("P")
    finally:
        store.close()


def test_parent_swap_with_same_database_inode_must_still_be_rejected(tmp_path):
    """A hardlinked SQLite file can preserve dev/inode across parent rename.

    File-only identity checks accept the new *directory* even though SQLite
    companion journal / WAL / lock paths are now different.
    """
    store, directory, db = _make_store(tmp_path)
    original_inode = db.stat().st_ino
    candidate = directory.with_name("db-candidate")
    candidate.mkdir()
    os.link(db, candidate / "projects.db")
    parked = _swap_directory(directory, candidate)
    try:
        assert db.stat().st_ino == (parked / "projects.db").stat().st_ino == original_inode
        with pytest.raises(RuntimeError, match="database identity changed"):
            store.get("P")
        with pytest.raises(RuntimeError, match="database identity changed"):
            store.backup(tmp_path / "forbidden.db")
        assert not (tmp_path / "forbidden.db").exists()
    finally:
        store.close()


def test_same_inode_parent_swap_during_connect_must_reject_open(tmp_path, monkeypatch):
    store, directory, db = _make_store(tmp_path)
    store.close()
    candidate = directory.with_name("db-candidate")
    candidate.mkdir()
    os.link(db, candidate / "projects.db")
    original_inode = db.stat().st_ino
    connect = __import__("sqlite3").connect
    ran = []

    def racing_connect(*args, **kwargs):
        opened = connect(*args, **kwargs)
        if Path(args[0]) == db and not ran:
            _swap_directory(directory, candidate)
            ran.append(True)
        return opened

    import sqlite3
    monkeypatch.setattr(sqlite3, "connect", racing_connect)
    try:
        with pytest.raises(RuntimeError, match="database identity changed"):
            ProjectStore(db)
    finally:
        monkeypatch.setattr(sqlite3, "connect", connect)
    assert ran and db.stat().st_ino == original_inode
