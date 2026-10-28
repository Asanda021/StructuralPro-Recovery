"""E6 history-preview CAS consistency with original Qt and SQLite authority."""
from copy import deepcopy
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit, QTableWidget, QLabel, QPushButton, QScrollArea
from core.platform.application import StructuralProApp
from test_phase2_priority5_complete import case


@pytest.mark.parametrize("previous_preview", [False, True])
def test_history_preview_revokes_stale_snapshot_and_prior_confirmation(
        tmp_path, monkeypatch, previous_preview):
    """The old snapshot must not acquire a NEW CAS token mid-preview."""
    from app.graphical_takeoff import GraphicalTakeoffDialog
    from PySide6.QtWidgets import QComboBox

    qt = QApplication.instance() or QApplication([])
    service, args, _, _ = case(tmp_path)
    service.apply_ifc_quantity_transfer("P", **args)
    source = service.open_project("P")["ifc_identity_reviews"][-1]["document"]["source_path"]
    view = GraphicalTakeoffDialog(app_service=service, project_id="P")
    view.show()
    view.open_drawing(source)
    view.ifc_revision.setText("R2")
    QTest.mouseClick(view.ifc_inspect_button, Qt.MouseButton.LeftButton)
    inspector = view._ifc_inspector
    inspector.findChild(QLineEdit, "ifc_author").setText("author")
    inspector.findChild(QLineEdit, "ifc_history_reason").setText(
        "Independent synthetic compensation review"
    )
    table = inspector.findChild(QTableWidget, "ifc_group_quantities")
    status = inspector.findChild(QLabel, "ifc_review_outcome")
    confirm = inspector.findChild(QPushButton, "ifc_group_confirm")
    assert inspector.findChild(QComboBox, "ifc_history_action").currentData() == "undo"

    def click(name):
        button = inspector.findChild(QPushButton, name)
        assert button is not None
        inspector.findChild(QScrollArea).ensureWidgetVisible(button)
        qt.processEvents()
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)

    original_open = service.open_project
    try:
        if previous_preview:
            click("ifc_history_preview")
            assert table.rowCount() > 0
            assert "انجام نشد" not in status.text(), status.text()
            click("ifc_group_confirm")
            assert confirm.isChecked()
        original = deepcopy(original_open("P"))
        old_token = service.store.current_digest("P")
        writes = []

        def raced_open(pid):
            snapshot = original_open(pid)
            if pid == "P" and not writes:
                writes.append(pid)
                # The transfer itself stays byte-identical; only an unrelated
                # real SQLite write changes the project CAS generation.
                service.add_project_floor("P", "Concurrent floor", level="F9")
            return snapshot

        monkeypatch.setattr(service, "open_project", raced_open)
        click("ifc_history_preview")
        assert writes == ["P"]
        assert service.store.current_digest("P") != old_token
        assert "انجام نشد" in status.text(), status.text()
        assert table.rowCount() == 0, "Prior owner preview must be cleared"
        assert not confirm.isChecked(), "Previous consent must be revoked"
        current = original_open("P")
        assert current["boq"] == original["boq"]
        assert current["manual_formula_amendments"] == original["manual_formula_amendments"]
        assert service.store.integrity_check()["ok"]
    finally:
        monkeypatch.setattr(service, "open_project", original_open)
        view.close()
        service.store.close()
        qt.processEvents()
