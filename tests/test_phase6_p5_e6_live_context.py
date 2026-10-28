"""Existing group apply/migration must respect the actual IFC viewer context."""
from copy import deepcopy
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QLineEdit, QScrollArea, QLabel, QTableWidget
from app.graphical_takeoff import GraphicalTakeoffDialog
from core.platform.application import StructuralProApp
from test_phase2_priority5_complete import case


@pytest.mark.parametrize("action", ["apply", "migrate"])
@pytest.mark.parametrize("change", ["project", "revision", "source"])
def test_group_mutation_refuses_changed_viewer_without_writes(tmp_path, action, change):
    qt = QApplication.instance() or QApplication([])
    service, args, allocation, _ = case(tmp_path, crosswalks="dxf" if action == "migrate" else None)
    source = service.open_project("P")["ifc_identity_reviews"][-1]["document"]["source_path"]
    view = GraphicalTakeoffDialog(app_service=service, project_id="P")
    view.show()
    view.open_drawing(source)
    view.ifc_revision.setText("R2")
    QTest.mouseClick(view.ifc_inspect_button, Qt.MouseButton.LeftButton)
    dialog = view._ifc_inspector

    def click(name):
        button = dialog.findChild(QPushButton, name)
        assert button is not None
        dialog.findChild(QScrollArea).ensureWidgetVisible(button)
        qt.processEvents()
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)

    try:
        dialog.findChild(QLineEdit, "ifc_author").setText("author")
        if action == "apply":
            dialog.findChild(QLineEdit, "ifc_group_allocation").setText(str(allocation))
            click("ifc_group_preview")
            assert dialog.findChild(QTableWidget, "ifc_group_quantities").rowCount() == 3
            assert "انجام نشد" not in dialog.findChild(QLabel, "ifc_review_outcome").text()
        else:
            dialog.findChild(QLineEdit, "ifc_group_crosswalk_document").setText(str(tmp_path / "crosswalk-group.json"))
        before = deepcopy(service.open_project("P"))
        token = service.store.current_digest("P")
        revision_count = service.store.db.execute("SELECT count(*) FROM revisions").fetchone()[0]
        if change == "project":
            view.project_id_input.setText("OTHER")
        elif change == "revision":
            view.ifc_revision.setText("R99")
        else:
            view.open_drawing(str(tmp_path / "beams-R1.ifc"))
        click("ifc_group_confirm")
        click("ifc_group_" + action)
        assert service.open_project("P") == before, "Stale IFC review mutated stored ownership/crosswalk"
        assert service.store.current_digest("P") == token
        assert service.store.db.execute("SELECT count(*) FROM revisions").fetchone()[0] == revision_count
        assert "انجام نشد" in dialog.findChild(QLabel, "ifc_review_outcome").text()
        assert service.store.integrity_check()["ok"]
    finally:
        view.close()
        service.store.close()
        qt.processEvents()
    reopened = StructuralProApp(tmp_path / "app")
    try:
        assert reopened.open_project("P") == before
    finally:
        reopened.store.close()
