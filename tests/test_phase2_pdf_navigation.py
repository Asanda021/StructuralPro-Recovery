"""Native navigation must never add engineering geometry."""
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from app.graphical_takeoff import GraphicalTakeoffDialog
from test_phase2_pdf_roof import fixture

_qt = None


def test_pdf_pan_drag_fit_and_highlight_preserve_measurements(tmp_path):
    global _qt
    _qt = QApplication.instance() or QApplication([])
    app, session, item, record = fixture(tmp_path)
    dialog = GraphicalTakeoffDialog(pdf_path=str(tmp_path/'plan.pdf'), app_service=app, project_id='P')
    dialog.session = session
    dialog.canvas.session = session
    dialog.refresh()
    dialog.resize(1100, 800)
    dialog.show()
    _qt.processEvents()
    try:
        assert hasattr(dialog, 'pan'), 'PDF window needs an operational Pan control'
        QTest.mouseClick(dialog.pan, Qt.LeftButton)
        assert dialog.canvas.mode == 'pan'
        dialog.canvas.scale_view(4)
        view = dialog.canvas.viewport()
        before = session.to_dict()
        points = list(dialog.canvas.points)
        bar = dialog.canvas.horizontalScrollBar()
        bar.setValue((bar.minimum()+bar.maximum())//2)
        initial = bar.value()
        start = view.rect().center()
        QTest.mousePress(view, Qt.LeftButton, pos=start)
        QTest.mouseMove(view, start+QPoint(80, 0), 30)
        QTest.mouseRelease(view, Qt.LeftButton, pos=start+QPoint(80, 0))
        assert bar.value() != initial
        assert dialog.canvas.points == points
        assert session.to_dict() == before
        zoom = dialog.canvas.transform().m11()
        QTest.mouseClick(dialog.fit, Qt.LeftButton)
        assert dialog.canvas.transform().m11() < zoom
        cell = dialog.table.item(0, 0)
        QTest.mouseClick(dialog.table.viewport(), Qt.LeftButton,
                         pos=dialog.table.visualItemRect(cell).center())
        assert dialog.canvas._highlighted_item_id == item.id
        assert session.to_dict() == before
        assert not app.open_project('P')['boq']
    finally:
        dialog.close()
        app.store.close()
