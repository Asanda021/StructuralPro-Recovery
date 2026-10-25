"""Fail closed if projects.db is replaced while the store is opening.

The Linux rename fixture is synthetic. It does NOT attribute the historical
DBMOVED incident to any actor or establish native Windows behavior.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path

import pytest

from core.projects.store import ProjectStore


pytestmark = pytest.mark.skipif(
    os.name != "posix", reason="POSIX rename of an open SQLite file is needed for this fault injection"
)


def _prepare(path: Path, marker: str) -> None:
    store = ProjectStore(path)
    try:
        store.save("P", {"name": "synthetic", "marker": marker})
    finally:
        store.close()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_replacement_during_connect_cannot_pin_replacement_inode(tmp_path, monkeypatch):
    """Detect connect -> stat TOCTOU rather than reading old data as new DB."""
    db = tmp_path / "projects.db"
    replacement = tmp_path / "replacement.db"
    held = tmp_path / "held.db"
    _prepare(db, "original")
    _prepare(replacement, "replacement")
    before_original = _sha(db)
    before_replacement = _sha(replacement)
    real_connect = sqlite3.connect
    swapped = []

    def replace_during_connect(*args, **kwargs):
        connection = real_connect(*args, **kwargs)
        if Path(args[0]) == db and not swapped:
            db.rename(held)
            replacement.rename(db)
            swapped.append(True)
        return connection

    monkeypatch.setattr(sqlite3, "connect", replace_during_connect)
    opened = None
    try:
        with pytest.raises(RuntimeError, match="database identity changed"):
            opened = ProjectStore(db)
    finally:
        monkeypatch.setattr(sqlite3, "connect", real_connect)
        if opened is not None:
            opened.close()

    assert swapped
    assert _sha(held) == before_original
    assert _sha(db) == before_replacement
    store = ProjectStore(db)
    try:
        assert store.get("P")["marker"] == "replacement"
    finally:
        store.close()


def test_replacement_during_startup_commit_refused(tmp_path, monkeypatch):
    """Another swap after the initial checks must also be rejected."""
    db = tmp_path / "projects.db"
    replacement = tmp_path / "replacement.db"
    held = tmp_path / "held.db"
    _prepare(db, "original")
    _prepare(replacement, "replacement")
    original = _sha(db)
    replacement_hash = _sha(replacement)
    real_connect = sqlite3.connect
    swapped = []

    class RaceConnection(sqlite3.Connection):
        def commit(self):
            value = super().commit()
            if not swapped:
                db.rename(held)
                replacement.rename(db)
                swapped.append(True)
            return value

    def racing_connect(*args, **kwargs):
        kwargs["factory"] = RaceConnection
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", racing_connect)
    opened = None
    try:
        with pytest.raises(RuntimeError, match="database identity changed"):
            opened = ProjectStore(db)
    finally:
        monkeypatch.setattr(sqlite3, "connect", real_connect)
        if opened is not None:
            opened.close()

    assert swapped
    assert _sha(held) == original
    assert _sha(db) == replacement_hash
    store = ProjectStore(db)
    try:
        assert store.get("P")["marker"] == "replacement"
    finally:
        store.close()
