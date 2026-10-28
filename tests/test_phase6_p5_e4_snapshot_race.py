"""E4 actual Qt race regressions: no stale search snapshot can open a route."""
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from core.platform.application import StructuralProApp
from app.project_search_panel import ProjectSearchDialog
import app.project_search_panel as search_module


def qt():
    return QApplication.instance() or QApplication([])


def test_e4_search_does_not_publish_snapshot_after_concurrent_change(tmp_path, monkeypatch):
    app = qt()
    service = StructuralProApp(tmp_path / "db")
    service.create_project("Project E4 Snapshot", "P")
    panel = ProjectSearchDialog(service, "P")
    panel.query.setText("Project E4 Snapshot")
    original = search_module.search_project
    invoked = []
    def concurrent_search(project, query, *, limit=100):
        result = original(project, query, limit=limit)
        if not invoked:
            invoked.append(True)
            service.add_project_floor("P", "Later", level="F2")
        return result
    monkeypatch.setattr(search_module, "search_project", concurrent_search)
    try:
        assert panel.run_search() == []
        assert invoked == [True]
        assert panel.digest is None and panel.results == []
        assert panel.list.count() == 0
        assert "نسخه" in panel.status.text()
        assert not service.open_project("P")["boq"]
    finally:
        panel.close()
        service.store.close()
        app.processEvents()


def test_e4_record_click_cannot_dispatch_stale_unchanged_identity(tmp_path, monkeypatch):
    app = qt()
    service = StructuralProApp(tmp_path / "db")
    service.create_project("Project E4 Identity", "P")
    dispatched = []
    panel = ProjectSearchDialog(service, "P", initial_query="Project E4 Identity",
                                on_navigate=lambda *args: dispatched.append(args))
    panel.show()
    panel.list.setCurrentRow(0)
    original = search_module.search_project
    invoked = []
    def concurrent_search(project, query, *, limit=100):
        result = original(project, query, limit=limit)
        if not invoked:
            invoked.append(True)
            # Identity and original search result remain byte-for-byte equal.
            service.add_project_floor("P", "Another floor", level="F2")
        return result
    monkeypatch.setattr(search_module, "search_project", concurrent_search)
    try:
        assert panel.open_button.isEnabled()
        QTest.mouseClick(panel.open_button, Qt.MouseButton.LeftButton)
        assert invoked == [True] and not dispatched
        assert panel.digest is None and panel.list.count() == 0
        assert "نسخه" in panel.status.text()
        assert not service.open_project("P")["boq"]
    finally:
        panel.close()
        service.store.close()
        app.processEvents()


def test_e4_ifc_button_rechecks_digest_after_original_record_returns(tmp_path, monkeypatch):
    app = qt()
    service = StructuralProApp(tmp_path / "db")
    service.create_project("P", "P")
    service.add_project_floor("P", "Level 1", level="F1")
    service.add_project_member("P", "B1", "F1", "column")
    opened = []
    panel = ProjectSearchDialog(service, "P", initial_query="B1",
                                on_open_model=lambda *args: opened.append(args))
    panel.show()
    member_rows = [i for i, row in enumerate(panel.results)
                   if row["kind"] == "member" and row["entity_id"] == "B1"]
    assert len(member_rows) == 1
    panel.list.setCurrentRow(member_rows[0])
    original = panel.open_record
    def concurrent_record(*, navigate=True):
        record = original(navigate=navigate)
        if record is not None:
            service.add_project_floor("P", "Race floor", level="F2")
        return record
    monkeypatch.setattr(panel, "open_record", concurrent_record)
    try:
        assert panel.model_button.isEnabled()
        QTest.mouseClick(panel.model_button, Qt.MouseButton.LeftButton)
        assert not opened
        assert "نسخه" in panel.status.text()
        assert not service.open_project("P")["boq"]
    finally:
        panel.close()
        service.store.close()
        app.processEvents()
