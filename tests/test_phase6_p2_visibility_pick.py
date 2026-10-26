import pytest
from core.drawings.source_mesh3d import VerifiedScene3D
from test_phase6_p2_source_mesh3d import real_contract


def test_isolated_geometry_is_the_only_pick_target(tmp_path):
    scene = VerifiedScene3D(real_contract(tmp_path))
    face = scene.visible_faces(800, 600, selected_id='IFC-DUCT-02')[0]
    point = tuple(sum(p[i] for p in face.points)/3 for i in (0, 1))
    assert scene.pick(*point, 800, 600, selected_id='IFC-WALL-01') is None


def test_scene_refuses_changed_source_after_open(tmp_path):
    contract = real_contract(tmp_path)
    scene = VerifiedScene3D(contract)
    from pathlib import Path
    Path(contract['source_path']).write_bytes(b'changed while viewer is open')
    with pytest.raises(ValueError, match='تغییر'):
        scene.validate_source()


def test_section_intersections_use_exact_source_edges_and_hidden_types_are_not_pickable(tmp_path):
    scene = VerifiedScene3D(real_contract(tmp_path))
    scene.set_section(1.5)
    triangles = scene._clip_triangle(((0., 0., 0.), (2., 0., 0.), (0., 0., 3.)))
    assert len(triangles) == 2
    points = set(p for tri in triangles for p in tri)
    assert points == {(0., 0., 0.), (2., 0., 0.), (1., 0., 1.5), (0., 0., 1.5)}
    assert {f.global_id for f in scene.visible_faces(800, 600)} == {'IFC-WALL-01'}
    scene.hidden_types.add('IfcWall')
    assert scene.visible_faces(800, 600) == ()
    scene.set_section(None)
    scene.hidden_storeys.add('Level-02')
    assert scene.visible_faces(800, 600) == ()


def test_qt_section_filter_transparency_buttons(tmp_path):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt, QPoint
    from app.ifc_3d_viewport import IFC3DDialog
    qt = QApplication.instance() or QApplication([])
    dialog = IFC3DDialog(VerifiedScene3D(real_contract(tmp_path)))
    dialog.show()
    qt.processEvents()
    try:
        dialog.section_height.setValue(1.5)
        QTest.mouseClick(dialog.section, Qt.LeftButton,
                         pos=QPoint(dialog.section.width()-8, dialog.section.height()//2))
        assert dialog.scene.section_z == 1.5
        assert len(dialog.canvas._faces()) == 2
        QTest.mouseClick(dialog.transparency, Qt.LeftButton,
                         pos=QPoint(dialog.transparency.width()-8, dialog.transparency.height()//2))
        assert dialog.canvas.transparent
        dialog.type_filter.setCurrentIndex(dialog.type_filter.findData('IfcDuctSegment'))
        assert dialog.canvas._faces() == ()
    finally:
        dialog.close()


def test_qt_isolated_click_and_invalidated_source(tmp_path):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from app.ifc_3d_viewport import IFC3DCanvas
    from pathlib import Path
    qt = QApplication.instance() or QApplication([])
    contract = real_contract(tmp_path)
    scene = VerifiedScene3D(contract)
    canvas = IFC3DCanvas(scene)
    canvas.resize(800, 600)
    canvas.show()
    qt.processEvents()
    try:
        canvas.choose_member('IFC-WALL-01')
        canvas.isolate_selection = True
        seen = []
        canvas.memberSelected.connect(seen.append)
        face = scene.visible_faces(800, 600, selected_id='IFC-DUCT-02')[0]
        x, y = (sum(p[i] for p in face.points)/3 for i in (0, 1))
        QTest.mouseClick(canvas, Qt.LeftButton, pos=QPoint(round(x), round(y)))
        assert seen == []
        assert canvas.selected_id == 'IFC-WALL-01'
        Path(contract['source_path']).write_bytes(b'changed source')
        canvas.check_source()
        assert canvas._faces() == ()
        assert canvas.selected_id is None
        assert 'تغییر' in canvas.source_error
    finally:
        canvas.close()
        qt.processEvents()


def test_source_worker_invalidates_scene_without_ui_thread_hashing(tmp_path):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from app.ifc_3d_viewport import IFC3DCanvas
    from pathlib import Path
    qt = QApplication.instance() or QApplication([])
    contract = real_contract(tmp_path)
    canvas = IFC3DCanvas(VerifiedScene3D(contract))
    Path(contract['source_path']).write_bytes(b'changed')
    canvas.schedule_source_check()
    task = canvas._source_check
    canvas.schedule_source_check()
    assert canvas._source_check is task
    for _ in range(100):
        qt.processEvents()
        if canvas.source_error:
            break
        QTest.qWait(10)
    assert canvas.source_error
    assert canvas._faces() == ()
    canvas.close()


def test_floor_visibility_checkbox_tracks_selected_floor_without_changing_other_floors(tmp_path):
    from PySide6.QtWidgets import QApplication
    from app.ifc_3d_viewport import IFC3DDialog
    qt=QApplication.instance() or QApplication([])
    dialog=IFC3DDialog(VerifiedScene3D(real_contract(tmp_path)))
    try:
        assert not dialog.hide_floor.isEnabled()  # All floors cannot be hidden ambiguously.
        ix1=dialog.storey.findData('Level-01')
        ix2=dialog.storey.findData('Level-02')
        dialog.storey.setCurrentIndex(ix1)
        assert dialog.hide_floor.isEnabled() and not dialog.hide_floor.isChecked()
        dialog.hide_floor.setChecked(True)
        assert dialog.scene.hidden_storeys == {'Level-01'}
        dialog.storey.setCurrentIndex(ix2)
        assert not dialog.hide_floor.isChecked()
        assert dialog.scene.hidden_storeys == {'Level-01'}
        dialog.hide_floor.setChecked(True)
        assert dialog.scene.hidden_storeys == {'Level-01', 'Level-02'}
        dialog.storey.setCurrentIndex(ix1)
        assert dialog.hide_floor.isChecked()
        dialog.hide_floor.setChecked(False)
        assert dialog.scene.hidden_storeys == {'Level-02'}
        dialog.storey.setCurrentIndex(0)
        assert not dialog.hide_floor.isEnabled() and not dialog.hide_floor.isChecked()
        assert dialog.scene.hidden_storeys == {'Level-02'}
    finally:
        dialog.close()
        qt.processEvents()
