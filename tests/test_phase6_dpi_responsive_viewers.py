"""P6 G4: independent logical-DPI toolbar reflow, no invented BOQ authority."""
import hashlib

from PySide6.QtWidgets import QApplication, QPushButton, QWidget
from app.responsive_flow_layout import ResponsiveFlowLayout


def _qt():
    return QApplication.instance() or QApplication([])


def test_flow_shrinks_minimum_width_and_wraps_original_qt_controls():
    qt = _qt()
    widget = QWidget()
    row = ResponsiveFlowLayout(widget)
    buttons = [
        QPushButton("مدل سه‌بعدی واقعی IFC"),
        QPushButton("بررسی هندسه و طبقات مستند"),
        QPushButton("ذخیره نشست بدون تولید متره"),
    ]
    for button in buttons:
        row.addWidget(button)
    try:
        widget.resize(480, 350)
        widget.show()
        qt.processEvents()
        assert row.count() == 3
        assert row.minimumSize().width() < sum(b.sizeHint().width() for b in buttons)
        assert row.heightForWidth(440) > row.heightForWidth(1400)
        assert len({id(row.itemAt(i).widget()) for i in range(3)}) == 3
        assert all(button.parentWidget() is widget for button in buttons)
    finally:
        widget.close()


def test_original_2d_controls_wrap_without_replacing_canvas_or_engineering_values():
    from app.graphical_takeoff import GraphicalTakeoffDialog

    qt = _qt()
    view = GraphicalTakeoffDialog()
    try:
        original_canvas = view.canvas
        original_row_count = view.table.rowCount()
        toolbar = view.layout().itemAt(0).widget()
        groups = [toolbar.layout().itemAt(i).layout() for i in (0, 1)]
        assert all(isinstance(row, ResponsiveFlowLayout) for row in groups)
        header, actions = groups
        assert header.heightForWidth(480) > header.heightForWidth(1350)
        assert actions.heightForWidth(480) > actions.heightForWidth(1350)
        assert actions.count() >= 30
        view.resize(540, 730)
        view.show()
        qt.processEvents()
        assert view.canvas is original_canvas
        assert view.table.rowCount() == original_row_count == 0
        assert view.ifc_3d_button.objectName() == "OpenVerifiedIFC3D"
        assert view.commit_boq_button.isEnabled() is False
    finally:
        view.close()
        qt.processEvents()


def test_original_3d_controls_wrap_while_source_and_no_qto_authority_remain(tmp_path):
    from core.drawings.source_mesh3d import VerifiedScene3D
    from app.ifc_3d_viewport import IFC3DDialog

    qt = _qt()
    source = tmp_path / "p6_display.ifc"
    source.write_text("Explicit geometry test source only", encoding="utf-8")
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    scene = VerifiedScene3D({
        "policy": "ifc_display_geometry_v1",
        "quantity_authority": False,
        "coordinate_system": "IFC world coordinates in metres",
        "source_path": str(source),
        "source_sha256": sha,
        "revision": "R1",
        "elements": [{
            "global_id": "ExplicitMember01", "storey_id": "F1",
            "ifc_type": "IfcWall",
            "vertices_m": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 1.0]],
            "triangles": [[0, 1, 2]],
        }],
    })
    view = IFC3DDialog(scene)
    try:
        root = view.layout()
        top = root.itemAt(0).layout()
        assert isinstance(top, ResponsiveFlowLayout)
        # A 480px logical toolbar can already fit this particular Qt font.
        # Use a genuinely constrained width to assert responsive wrapping.
        assert top.heightForWidth(220) > top.heightForWidth(1400)
        assert view.provenance.wordWrap() is True
        assert view.batch_row.layout().__class__ is ResponsiveFlowLayout
        assert view.storey.currentData() is None
        before = (scene.source_sha256, scene.revision, scene.quantity_authority)
        view.resize(550, 730)
        view.show()
        qt.processEvents()
        assert view.canvas.scene is scene
        assert before == (sha, "R1", False)
        assert view.save_view.isEnabled() is False
    finally:
        view.close()
        qt.processEvents()
