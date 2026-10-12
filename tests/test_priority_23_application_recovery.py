"""Priority 23 application integration tests."""
from core.platform.application import StructuralProApp

def test_reliability_status_and_project_backup(tmp_path):
    app=StructuralProApp(tmp_path)
    app.create_project("Demo","P23")
    status=app.project_reliability_status("P23")
    assert status["integrity"]["ok"] is True
    assert status["revision_count"] == 1
    assert status["recoverable"] is True
    export=tmp_path/"P23.spbackup.json"
    info=app.export_project_backup("P23",export)
    restored=app.import_project_backup(export)
    assert len(info["sha256"])==64 and restored["id"]=="P23"

def test_database_backup_api(tmp_path):
    app=StructuralProApp(tmp_path)
    app.create_project("Demo","P23")
    backup=tmp_path/"recovery.db"
    result=app.backup_project_database(backup)
    assert result["size"]>0
