"""Phase 5 backup-package evidence and isolated restore tests."""
from __future__ import annotations

import hashlib
import json
import zipfile

import pytest

from core.projects.backup import BackupManager


def _project(version: int = 7) -> dict:
    return {
        "id": "P5-BACKUP",
        "name": "ساختمان پنج‌طبقه آزمون",
        "schema_version": 3,
        "floors": [{"id": f"F{i}", "project_id": "P5-BACKUP"} for i in range(1, 6)],
        "boq": [],
        "resources": [],
        "daily_reports": [],
        "_meta": {"id": "P5-BACKUP", "version": version, "updated_at": 1.0},
    }


def test_new_package_manifest_carries_verifiable_restore_evidence(tmp_path):
    manager = BackupManager(tmp_path / "backups")
    package = manager.create_package(_project(), "P5-BACKUP")
    with zipfile.ZipFile(package) as archive:
        payload = archive.read("project.json")
        manifest = json.loads(archive.read("manifest.json"))

    assert manifest["format"] == "StructuralProBackup"
    assert manifest["version"] == 2
    assert manifest["project_id"] == "P5-BACKUP"
    assert manifest["schema_version"] == 3
    assert manifest["revision"] == 7
    assert manifest["created_at"].endswith("Z")
    assert manifest["producer"] == "StructuralPro"
    assert manifest["health"] == {"project_validation": "passed"}
    assert manifest["files"] == [
        {
            "path": "project.json",
            "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    ]
    restored = manager.restore_package(
        package, expected_project_id="P5-BACKUP", minimum_revision=7
    )
    assert restored == _project()


def test_package_publish_race_never_overwrites_competing_file(tmp_path, monkeypatch):
    root = tmp_path / "backups"
    manager = BackupManager(root)
    monkeypatch.setattr("core.projects.backup.time.strftime", lambda *_: "20261025_120000")
    target = root / "P5-BACKUP_20261025_120000.spbackup"
    original_close = zipfile.ZipFile.close
    raced = []

    def close_and_claim_destination(archive):
        original_close(archive)
        if not raced:
            target.write_bytes(b"competing backup owner")
            raced.append(True)

    monkeypatch.setattr(zipfile.ZipFile, "close", close_and_claim_destination)
    with pytest.raises(ValueError, match="destination appeared"):
        manager.create_package(_project(), "P5-BACKUP")

    assert raced
    assert target.read_bytes() == b"competing backup owner"
    assert not list(root.glob("*.tmp"))


def test_restore_rejects_stale_or_forged_revision_evidence(tmp_path):
    manager = BackupManager(tmp_path / "backups")
    package = manager.create_package(_project(7), "P5-BACKUP")
    with pytest.raises(ValueError, match="older than"):
        manager.restore_package(package, minimum_revision=8)

    forged = tmp_path / "forged.spbackup"
    with zipfile.ZipFile(package) as source, zipfile.ZipFile(forged, "w") as target:
        payload = source.read("project.json")
        manifest = json.loads(source.read("manifest.json"))
        manifest["revision"] = 99
        target.writestr("project.json", payload)
        target.writestr("manifest.json", json.dumps(manifest))
    with pytest.raises(ValueError, match="revision evidence mismatch"):
        manager.restore_package(forged)


def test_restore_rejects_forged_schema_evidence(tmp_path):
    manager = BackupManager(tmp_path / "backups")
    package = manager.create_package(_project(), "P5-BACKUP")
    forged = tmp_path / "forged-schema.spbackup"
    with zipfile.ZipFile(package) as source, zipfile.ZipFile(forged, "w") as target:
        payload = source.read("project.json")
        manifest = json.loads(source.read("manifest.json"))
        manifest["schema_version"] = 99
        target.writestr("project.json", payload)
        target.writestr("manifest.json", json.dumps(manifest))
    with pytest.raises(ValueError, match="schema evidence mismatch"):
        manager.restore_package(forged)


def test_restore_materializes_only_into_new_isolated_directory(tmp_path):
    manager = BackupManager(tmp_path / "backups")
    package = manager.create_package(_project(7), "P5-BACKUP")
    isolated = tmp_path / "restore-stage"

    receipt = manager.restore_package_to(
        package,
        isolated,
        expected_project_id="P5-BACKUP",
        minimum_revision=7,
    )
    restored_path = isolated / "project.json"
    assert restored_path.is_file()
    assert json.loads(restored_path.read_text(encoding="utf-8")) == _project(7)
    assert receipt["project_id"] == "P5-BACKUP"
    assert receipt["revision"] == 7
    assert receipt["sha256"] == hashlib.sha256(restored_path.read_bytes()).hexdigest()

    with pytest.raises(ValueError, match="must not exist"):
        manager.restore_package_to(package, isolated)


def test_backup_write_failure_leaves_no_publishable_package(tmp_path, monkeypatch):
    manager = BackupManager(tmp_path / "backups")
    original = zipfile.ZipFile.writestr
    calls = []

    def no_space(archive, *args, **kwargs):
        if not calls:
            calls.append(True)
            raise OSError("No space left on device")
        return original(archive, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "writestr", no_space)
    with pytest.raises(OSError, match="No space"):
        manager.create_package(_project(), "P5-BACKUP")
    assert calls
    assert not list((tmp_path / "backups").glob("*.spbackup"))
    assert not list((tmp_path / "backups").glob("*.tmp"))


def test_interrupted_isolated_restore_removes_owned_staging_directory(tmp_path, monkeypatch):
    manager = BackupManager(tmp_path / "backups")
    package = manager.create_package(_project(), "P5-BACKUP")
    isolated = tmp_path / "restore-stage"
    original = type(isolated).write_bytes

    def fail_write(path, payload):
        if path.name == ".project.json.tmp":
            raise OSError("simulated restore interruption")
        return original(path, payload)

    monkeypatch.setattr(type(isolated), "write_bytes", fail_write)
    with pytest.raises(OSError, match="restore interruption"):
        manager.restore_package_to(package, isolated)
    assert not isolated.exists()


def test_verified_source_documents_restore_inside_staging_only(tmp_path):
    manager = BackupManager(tmp_path / "backups")
    source = tmp_path / "source.txt"
    source.write_text("مدرک منشأ معتبر", encoding="utf-8")
    package = manager.create_package(
        _project(),
        "P5-BACKUP",
        attachments={"sources/source.txt": source},
    )
    stage = tmp_path / "stage"
    manager.restore_package_to(package, stage)
    assert (stage / "sources/source.txt").read_bytes() == source.read_bytes()

    with pytest.raises(ValueError, match="unsafe backup member path"):
        manager.create_package(
            _project(),
            "P5-BACKUP",
            attachments={"../escape.txt": source},
        )


def test_tampered_source_document_and_forged_member_path_are_rejected(tmp_path):
    manager = BackupManager(tmp_path / "backups")
    source = tmp_path / "source.txt"
    source.write_bytes(b"trusted source")
    package = manager.create_package(
        _project(), "P5-BACKUP", attachments={"sources/source.txt": source}
    )

    tampered = tmp_path / "tampered.spbackup"
    with zipfile.ZipFile(package) as src, zipfile.ZipFile(tampered, "w") as dst:
        for info in src.infolist():
            content = src.read(info.filename)
            if info.filename == "sources/source.txt":
                content = b"tampered source"
            dst.writestr(info, content)
    with pytest.raises(ValueError, match="file manifest mismatch"):
        manager.restore_package(tampered)

    escaped = tmp_path / "escaped.spbackup"
    with zipfile.ZipFile(package) as src, zipfile.ZipFile(escaped, "w") as dst:
        manifest = json.loads(src.read("manifest.json"))
        source_entry = next(x for x in manifest["files"] if x["path"].startswith("sources/"))
        source_entry["path"] = "../escape.txt"
        dst.writestr("project.json", src.read("project.json"))
        dst.writestr("../escape.txt", src.read("sources/source.txt"))
        dst.writestr("manifest.json", json.dumps(manifest))
    with pytest.raises(ValueError, match="unsafe backup member path"):
        manager.restore_package(escaped)
