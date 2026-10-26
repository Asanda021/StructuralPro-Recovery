"""Phase 6 P2 actual IFC -> verified 3D canvas -> existing 2D source identity."""
import hashlib

import pytest


def test_real_ifc_source_drives_true_3d_coordinates_and_storeys(tmp_path):
    pytest.importorskip('ifcopenshell')
    from test_phase2_priority5_ifc import model_file
    from core.bim.ifc import DeepIFCAdapter
    from core.drawings.source_mesh3d import VerifiedScene3D
    path=tmp_path/'building.ifc'
    model, elements=model_file(path)
    contract=DeepIFCAdapter().read_display_contract(path, revision='R1')
    scene=VerifiedScene3D(contract)
    assert scene.source_sha256==hashlib.sha256(path.read_bytes()).hexdigest()
    assert scene.revision=='R1' and scene.quantity_authority is False
    assert {x.global_id for x in scene.meshes}=={x.GlobalId for x in elements}
    assert len(scene.visible_faces(960,680))>0
    assert len(scene.storeys)>0
    assert any(face.ifc_type.upper() in ('IFCWALL','IFCDOOR','IFCWINDOW')
               for face in scene.visible_faces(960,680))
    old=len(scene.visible_faces(960,680))
    scene.orbit(.6,.15)
    assert len(scene.visible_faces(960,680))==old


def test_real_qt_ifc_3d_button_opens_document_and_syncs_selection(tmp_path):
    pytest.importorskip('ifcopenshell')
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from test_phase2_priority5_ifc import model_file
    from app.graphical_takeoff import GraphicalTakeoffDialog
    from app.ifc_3d_viewport import IFC3DCanvas
    p=tmp_path/'building.ifc'
    _,elements=model_file(p)
    qt=QApplication.instance() or QApplication([])
    dialog=GraphicalTakeoffDialog()
    dialog.show()
    dialog.open_drawing(str(p))
    dialog.ifc_revision.setText('R1')
    assert dialog.ifc_3d_button.isVisible()
    before=list(dialog.session.items)
    QTest.mouseClick(dialog.ifc_3d_button, Qt.MouseButton.LeftButton)
    view=dialog._ifc_3d_dialog
    canvas=view.findChild(IFC3DCanvas,'VerifiedIFC3DCanvas')
    assert canvas is not None
    assert canvas.scene.quantity_authority is False
    assert view.storey.count()>1
    gid=elements[0].GlobalId
    dialog.highlight_ifc_member(gid)
    assert canvas.selected_id==gid
    old=canvas.scene.visible_faces(740,450)
    canvas.scene.orbit(.15,.2)
    canvas.update()
    assert canvas.scene.visible_faces(740,450)!=old
    assert before==dialog.session.items==[]
    view.close()
    dialog.close()
    qt.processEvents()


def test_ifc_3d_refuses_missing_revision_and_does_not_mutate_data(tmp_path):
    pytest.importorskip('ifcopenshell')
    from PySide6.QtWidgets import QApplication
    from test_phase2_priority5_ifc import model_file
    from app.graphical_takeoff import GraphicalTakeoffDialog
    p=tmp_path/'building.ifc'
    model_file(p)
    qt=QApplication.instance() or QApplication([])
    dialog=GraphicalTakeoffDialog()
    dialog.open_drawing(str(p))
    dialog.ifc_revision.setText('')
    before=list(dialog.session.items)
    assert dialog.open_ifc_3d() is None
    assert 'سه‌بعدی' in dialog.status.text()
    assert dialog.session.items==before
    dialog.close()
    qt.processEvents()
