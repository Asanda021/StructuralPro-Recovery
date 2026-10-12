"""Priority 45 — persistence and data-integrity audit."""
from pathlib import Path
from core.projects.backup import BackupManager

def _project():
    return {"id":"P45","name":"پروژه پایدار","takeoffs":[],"boq":[]}

def test_backup_create_is_collision_safe(tmp_path, monkeypatch):
    monkeypatch.setattr("core.projects.backup.time.strftime", lambda *_: "20261002_120000")
    manager=BackupManager(tmp_path)
    first=manager.create(_project(),"P45")
    second=manager.create(_project(),"P45")
    assert first != second
    assert first.exists() and second.exists()

def test_package_restore_rejects_manifest_project_mismatch(tmp_path):
    manager=BackupManager(tmp_path)
    package=manager.create_package(_project(),"P45")
    import zipfile, json
    broken=tmp_path/"broken.spbackup"
    with zipfile.ZipFile(package) as src, zipfile.ZipFile(broken,"w") as dst:
        payload=src.read("project.json")
        manifest=json.loads(src.read("manifest.json"))
        manifest["project_id"]="OTHER"
        dst.writestr("project.json",payload)
        dst.writestr("manifest.json",json.dumps(manifest))
    import pytest
    with pytest.raises(ValueError, match="identifier mismatch"):
        manager.restore_package(broken)
