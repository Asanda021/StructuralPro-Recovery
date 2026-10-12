"""Priority 23 recovery regression tests."""
import json, sqlite3
from core.projects.store import ProjectStore
from core.recovery.recovery import backup_database, verify_database, export_project, import_project, RecoveryError

def test_database_backup_and_integrity(tmp_path):
    db=tmp_path/"projects.db"; store=ProjectStore(db)
    store.save("P23",{"id":"P23","name":"Recovery"})
    backup=tmp_path/"backup.db"; info=backup_database(db,backup)
    assert info["size"]>0 and verify_database(db)["ok"]
    restored=sqlite3.connect(backup)
    assert restored.execute("select count(*) from projects").fetchone()[0]==1
    restored.close(); store.close()

def test_project_export_import_roundtrip(tmp_path):
    project={"id":"P23","name":"Demo","takeoffs":[{"id":"1"}]}
    path=tmp_path/"P23.spbackup.json"
    info=export_project(project,path)
    assert len(info["sha256"])==64
    assert import_project(path)==project

def test_invalid_backup_is_rejected(tmp_path):
    p=tmp_path/"bad.json"; p.write_text(json.dumps({"format":"wrong"}),encoding="utf-8")
    try: import_project(p); assert False
    except RecoveryError: pass
