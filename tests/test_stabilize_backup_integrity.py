"""Backup and database-integrity regression for P10–P12.

Runs on standard SQLite, with no Windows GUI or network.
"""
from __future__ import annotations

import pytest

from core.projects.store import ProjectStore
from core.recovery.recovery import (
    backup_database, verify_database, export_project, import_project, RecoveryError,
)


def test_sqlite_backup_preserves_project_and_reopens(tmp_path):
    source = tmp_path / "projects.sqlite"
    store = ProjectStore(source)
    store.save("P1", {"id": "P1", "name": "پروژه آزمون",
                       "takeoffs": [], "boq": []})
    assert store.integrity_check()["ok"]
    backup = tmp_path / "backup.sqlite"
    result = store.backup(backup)
    assert result["size"] > 0
    assert verify_database(backup)["ok"]
    reopened = ProjectStore(backup)
    assert reopened.get("P1")["name"] == "پروژه آزمون"
    reopened.close()
    store.close()


def test_sqlite_backup_refuses_overwriting_original(tmp_path):
    db = tmp_path / "source.sqlite"
    store = ProjectStore(db)
    store.save("P1", {"id": "P1", "name": "آزمون"})
    with pytest.raises(RecoveryError):
        backup_database(db, db)
    store.close()


def test_project_json_backup_can_be_imported_without_losing_items(tmp_path):
    file = tmp_path / "project.json"
    original = {"id": "P1", "name": "پروژه",
                "takeoffs": [{"id": "q1", "source_id": "A"}]}
    result = export_project(original, file)
    assert result["sha256"]
    assert import_project(file) == original


def test_corrupted_json_backup_rejected(tmp_path):
    file = tmp_path / "invalid.json"
    file.write_text("not a valid project backup", encoding="utf-8")
    with pytest.raises(RecoveryError):
        import_project(file)
