"""E4 Qt callback contracts: explicit denial and post-callback CAS are fail-closed.

A successful legacy destination may return None. Do not mistake None for False.
"""
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from core.platform.application import StructuralProApp
from app.project_search_panel import ProjectSearchDialog


@pytest.mark.parametrize("kind", ["record", "ifc"])
@pytest.mark.parametrize("outcome", ["none_success", "explicit_false", "exception", "changed_after_callback"])
def test_e4_callback_contract_is_fail_closed(tmp_path, kind, outcome):
    qt = QApplication.instance() or QApplication([])
    app = StructuralProApp(tmp_path / "db")
    app.create_project("Callback project E4", "P")
    if kind == "ifc":
        app.add_project_floor("P", "Level one", level="F1")
        app.add_project_member("P", "B1", "F1", "column")
    before = app.store.current_digest("P")
    called = []

    def callback(*args):
        called.append(args)
        if outcome == "explicit_false":
            return False
        if outcome == "exception":
            raise ValueError("Destination explicitly denied")
        if outcome == "changed_after_callback":
            app.add_project_floor("P", "Concurrent floor", level="F2")
        # The original main.py callback convention deliberately returns None.
        return None

    panel = ProjectSearchDialog(
        app, "P",
        initial_query="B1" if kind == "ifc" else "Callback project E4",
        on_open_model=callback if kind == "ifc" else None,
        on_navigate=callback if kind == "record" else None,
    )
    try:
        matches = [
            i for i, result in enumerate(panel.results)
            if (result["kind"], result["entity_id"]) ==
            (("member", "B1") if kind == "ifc" else ("project", "P"))
        ]
        assert len(matches) == 1
        panel.show()
        panel.list.setCurrentRow(matches[0])
        qt.processEvents()
        button = panel.model_button if kind == "ifc" else panel.open_button
        assert button.isEnabled()
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        assert called == ([("P", "B1")] if kind == "ifc" else [("projects", "P", "P")])
        if outcome == "none_success":
            assert panel.digest == before
            assert "مسدود" not in panel.status.text()
            assert "باز نشد" not in panel.status.text()
            assert panel.detail.toPlainText()
        else:
            assert panel.digest is None, "Denied/stale destination must revoke the search selection"
            assert panel.list.count() == 0
            assert "مسدود" in panel.status.text() or "باز نشد" in panel.status.text()
            assert panel.detail.toPlainText() == ""
        assert not app.open_project("P")["boq"]
        if outcome == "changed_after_callback":
            assert app.store.current_digest("P") != before
        else:
            assert app.store.current_digest("P") == before
    finally:
        panel.close()
        app.store.close()
        qt.processEvents()
