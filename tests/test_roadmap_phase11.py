from core.performance.project_performance import project_performance_snapshot
from core.projects.store import ProjectStore
from core.recovery.recovery import export_project, import_project, verify_database

def test_phase11_large_project_snapshot_and_recovery(tmp_path):
    database = tmp_path / "projects.db"
    store = ProjectStore(database)
    project = {"id": "P11", "name": "پروژه پایداری",
               "takeoffs": [{"id": str(i)} for i in range(10000)], "boq": [{"id": "B1"}]}
    try:
        store.save("P11", project)
        snapshot = project_performance_snapshot(store.get("P11"))
        assert snapshot["total_collection_rows"] == 10001
        assert snapshot["largest_collection"] == "takeoffs"
        assert snapshot["large_project"] is True
        backup = tmp_path / "P11.spbackup.json"
        metadata = export_project(store.get("P11"), backup)
        restored = import_project(backup)
        assert len(metadata["sha256"]) == 64
        assert restored["id"] == "P11"
        assert len(restored["takeoffs"]) == 10000
    finally:
        store.close()
    assert verify_database(database)["ok"] is True
