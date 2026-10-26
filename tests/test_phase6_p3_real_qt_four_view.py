"""Native Qt 2D / 3D / reviewed tree / BOQ selection, provenance and cancellation."""
import os
from pathlib import Path

from test_phase6_p3_real_project_bridge import reviewed


def test_real_qt_3d_to_tree_and_back_clear_without_silent_boq_update(tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app,path,proof,proposal=reviewed(tmp_path)
    qt=QApplication.instance() or QApplication([])
    workspace=GraphicalTakeoffDialog(app_service=app,project_id="P")
    workspace.show()
    workspace.open_drawing(str(path))
    workspace.ifc_revision.setText('R1')
    panel_view=workspace.open_verified_crossview()
    assert panel_view is not None,workspace.status.text()
    panel=workspace._verified_selection_panel
    gid=proposal["global_id"]
    digest=app.store.current_digest('P')
    workspace.open_ifc_3d()
    for _ in range(2000):
        qt.processEvents()
        if workspace._ifc_3d_dialog is not None or workspace._ifc_3d_loader is None:
            break
        QTest.qWait(10)
    model=workspace._ifc_3d_dialog
    assert model is not None,workspace.status.text()
    model.memberSelected.emit(gid)
    assert workspace._ifc_selected_global_id==gid
    assert panel.members.selectedItems()[0].text(0)=='B1'
    assert model.canvas.selected_id==gid
    panel._lookup('tree','B1')
    assert model.canvas.selected_id==gid
    # Full native Windows capture: actual 3D, reviewed project tree, 2D source.
    folder=os.environ.get('STRUCTURALPRO_P6_P3_SCREENSHOT_DIR')
    if folder:
        target=Path(folder);target.mkdir(parents=True,exist_ok=True)
        qt.processEvents()
        assert model.grab().save(str(target/'p6-p3-3d-native.png'))
        assert panel.grab().save(str(target/'p6-p3-reviewed-tree-boq-native.png'))
        assert workspace.grab().save(str(target/'p6-p3-source2d-native.png'))
    QTest.mouseClick(panel.clear_button,Qt.MouseButton.LeftButton)
    assert workspace._ifc_selected_global_id==''
    assert model.canvas.selected_id is None
    assert not panel.members.selectedItems()
    assert not panel.boq.selectionModel().selectedRows()
    assert all(not x.isSelected() for rows in workspace._ifc_handle_items.values() for x in rows)
    assert app.store.current_digest('P')==digest
    model.close()
    panel_view.close()
    workspace.close()
    qt.processEvents()
    app.store.close()


def test_changed_active_project_blocks_tree_navigation_and_revokes_panel(tmp_path):
    from PySide6.QtWidgets import QApplication
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app,path,proof,proposal=reviewed(tmp_path)
    qt=QApplication.instance() or QApplication([])
    workspace=GraphicalTakeoffDialog(app_service=app,project_id="P")
    workspace.show()
    workspace.open_drawing(str(path))
    workspace.ifc_revision.setText('R1')
    dialog=workspace.open_verified_crossview()
    assert dialog is not None,workspace.status.text()
    panel=workspace._verified_selection_panel
    original=app.store.current_digest('P')
    workspace.highlight_ifc_member(proposal["global_id"])
    assert workspace._ifc_selected_global_id==proposal["global_id"]
    assert panel.members.selectedItems()
    workspace.project_id_input.setText('ANOTHER-PROJECT')
    selections=[]
    panel.oneGlobalIdSelected.connect(selections.append)
    assert panel._lookup('tree','B1') is None
    assert not selections
    assert workspace._ifc_selected_global_id == ''
    assert not panel.members.selectedItems()
    assert all(not item.isSelected() for rows in workspace._ifc_handle_items.values()
               for item in rows)
    assert 'نامعتبر' in panel.detail.text()
    assert app.store.current_digest('P')==original
    dialog.close();workspace.close();qt.processEvents();app.store.close()
