"""Invalid Qt item identities and reentrant callbacks cannot approve old results."""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from app.project_search_panel import ProjectSearchDialog
from core.platform.application import StructuralProApp


@pytest.mark.parametrize("index", [-1, True, 1])
def test_invalid_result_index_cannot_dispatch_another_real_record(tmp_path, index):
    qt = QApplication.instance() or QApplication([])
    service = StructuralProApp(tmp_path / "db")
    service.create_project("E4 identity project", "P")
    service.add_project_floor("P", "E4 first floor", level="F1")
    service.add_project_floor("P", "E4 second floor", level="F2")
    calls = []
    panel = ProjectSearchDialog(service, "P", initial_query="E4",
                                on_navigate=lambda *args: calls.append(args))
    before = service.open_project("P")
    token = service.store.current_digest("P")
    try:
        assert len(panel.results) == 3
        panel.show()
        panel.list.setCurrentRow(0)
        panel.list.currentItem().setData(Qt.ItemDataRole.UserRole, index)
        QTest.mouseClick(panel.open_button, Qt.MouseButton.LeftButton)
        assert not calls, "An invalid result index dispatched a different stored record"
        assert panel.digest is None and not panel.detail.toPlainText()
        assert service.open_project("P") == before
        assert service.store.current_digest("P") == token
    finally:
        panel.close()
        service.store.close()
        qt.processEvents()


@pytest.mark.parametrize("kind", ["record", "ifc"])
def test_callback_refresh_cannot_replace_the_original_navigation_cas(tmp_path, kind):
    qt = QApplication.instance() or QApplication([])
    service = StructuralProApp(tmp_path / "db")
    service.create_project("E4 callback project", "P")
    service.add_project_floor("P", "First", level="F1")
    service.add_project_member("P", "B1", "F1", "column")
    calls = []

    def callback(*args):
        calls.append(args)
        service.add_project_floor("P", "Concurrent", level="F2")
        # A callback can reenter Qt and refresh the same search dialog.
        panel.run_search()
        return None

    panel = ProjectSearchDialog(service, "P", initial_query="B1" if kind == "ifc" else "E4 callback",
        on_navigate=callback if kind == "record" else None,
        on_open_model=callback if kind == "ifc" else None)
    token = service.store.current_digest("P")
    try:
        panel.show()
        panel.list.setCurrentRow(0)
        QTest.mouseClick(panel.model_button if kind == "ifc" else panel.open_button,
                         Qt.MouseButton.LeftButton)
        assert len(calls) == 1
        assert service.store.current_digest("P") != token
        assert panel.digest is None, "Callback refresh replaced the original CAS token"
        assert not panel.detail.toPlainText()
        assert not panel.open_button.isEnabled() and not panel.model_button.isEnabled()
        assert not service.open_project("P")["boq"]
    finally:
        panel.close()
        service.store.close()
        qt.processEvents()
