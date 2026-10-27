"""E5 real native Qt dock saved outside SQLite and project identity."""
from PySide6.QtWidgets import QApplication,QMainWindow
from PySide6.QtCore import Qt,QSettings
from core.platform.application import StructuralProApp
from app.workspace_docks import WorkspaceDockController


def test_real_ifc_2d_3d_docks_share_selection_and_close_on_project_change(tmp_path):
    from test_phase6_p3_real_project_bridge import reviewed
    from app.graphical_takeoff import GraphicalTakeoffDialog
    from PySide6.QtTest import QTest
    service,path,proof,proposal=reviewed(tmp_path)
    qt=QApplication.instance() or QApplication([])
    window=QMainWindow();window.resize(1200,900);window.show();current=['P']
    ctrl=WorkspaceDockController(window,QSettings(str(tmp_path/'ui.ini'),QSettings.IniFormat),service,lambda:current[0])
    view=GraphicalTakeoffDialog(window,app_service=service,project_id='P')
    try:
        assert hasattr(ctrl,'attach_view'), 'real IFC viewers are not dockable'
        ctrl.attach_view('2d',view,'P')
        view.open_drawing(str(path));view.ifc_revision.setText('R1')
        panel=view.open_verified_crossview();assert panel is not None
        before=service.store.current_digest('P')
        view.open_ifc_3d()
        for _ in range(1000):
            qt.processEvents()
            if view._ifc_3d_dialog is not None or view._ifc_3d_loader is None:break
            QTest.qWait(10)
        model=view._ifc_3d_dialog;assert model is not None,view.status.text()
        assert ctrl.view_docks['3d'].widget().widget() is model
        assert window.width()<=1200, 'legacy viewer forces workspace beyond requested screen width'
        model.memberSelected.emit(proposal['global_id'])
        assert model.canvas.selected_id==proposal['global_id']
        dock=ctrl.view_docks['3d'];dock.setFloating(True);qt.processEvents()
        dock.close();dock.toggleViewAction().trigger();qt.processEvents()
        assert model.canvas.selected_id==proposal['global_id']
        assert view._ifc_selected_global_id==proposal['global_id']
        dock.resize(500,400);dock.move(-10000,-10000);ctrl._clamp_floating()
        assert dock.x()>=dock.screen().availableGeometry().left()
        import os
        folder=os.environ.get('STRUCTURALPRO_E5_SCREENSHOTS')
        if folder:
            from pathlib import Path
            target=Path(folder);target.mkdir(parents=True,exist_ok=True)
            assert window.grab().save(str(target/'workspace.png'))
            assert dock.grab().save(str(target/'model-dock.png'))
        assert before==service.store.current_digest('P')
        replacement=GraphicalTakeoffDialog(window,app_service=service,project_id='P')
        ctrl.attach_view('2d',replacement,'P')
        assert '3d' not in ctrl.views, 'old 3D remains linked to replaced 2D document'
        current[0]='OTHER';ctrl.validate_views()
        assert not ctrl.views
        assert all(d.widget() is None and not d.isVisible() for d in ctrl.view_docks.values())
    finally:window.close();service.store.close();qt.processEvents()


def test_failed_restore_clears_visible_previous_project(tmp_path):
    from PySide6.QtWidgets import QTableWidgetItem
    qt=QApplication.instance() or QApplication([])
    service=StructuralProApp(tmp_path/'db');service.create_project('اول','P')
    current=['P'];window=QMainWindow();window.show()
    ctrl=WorkspaceDockController(window,QSettings(str(tmp_path/'ui.ini'),QSettings.IniFormat),service,lambda:current[0])
    try:
        ctrl.toggle_boq();ctrl.boq_table.setRowCount(1)
        ctrl.boq_table.setItem(0,0,QTableWidgetItem('پروژه قبلی'))
        current[0]='missing'
        assert not ctrl.restore()
        assert not ctrl.boq_dock.isVisible()
        assert ctrl.boq_table.rowCount()==0
    finally:window.close();service.store.close();qt.processEvents()


def test_existing_2d_view_dock_retains_canvas_and_invalidates_on_revision(tmp_path):
    from app.graphical_takeoff import GraphicalTakeoffDialog
    qt=QApplication.instance() or QApplication([])
    service=StructuralProApp(tmp_path/'db');service.create_project('اول','P')
    window=QMainWindow();window.resize(1100,800);window.show()
    ctrl=WorkspaceDockController(window,QSettings(str(tmp_path/'ui.ini'),QSettings.IniFormat),service,lambda:'P')
    view=GraphicalTakeoffDialog(window,app_service=service,project_id='P')
    try:
        assert hasattr(ctrl,'attach_view'), 'existing viewers have no workspace dock handoff'
        dock=ctrl.attach_view('2d',view,'P')
        canvas=view.canvas;scene=canvas.scene;before=service.store.current_digest('P')
        from PySide6.QtWidgets import QGraphicsItem
        item=scene.addRect(0,0,10,10)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        item.setSelected(True)
        dock.setFloating(True);qt.processEvents()
        dock.setFloating(False);dock.close();dock.toggleViewAction().trigger();qt.processEvents()
        assert dock.widget().widget() is view and view.canvas is canvas and canvas.scene is scene
        assert scene.selectedItems()==[item]
        assert ctrl.save();assert ctrl.restore()
        assert before==service.store.current_digest('P')
        service.add_project_floor('P','دوم',level='F2')
        ctrl.validate_views()
        assert not dock.isVisible() and dock.widget() is None
    finally:window.close();service.store.close();qt.processEvents()


def test_saved_view_layout_restores_after_new_controller_and_source_open(tmp_path):
    from app.graphical_takeoff import GraphicalTakeoffDialog
    qt=QApplication.instance() or QApplication([])
    service=StructuralProApp(tmp_path/'db');service.create_project('چینش','P')
    prefs=QSettings(str(tmp_path/'ui.ini'),QSettings.IniFormat)
    first=QMainWindow();first.show()
    ctrl=WorkspaceDockController(first,prefs,service,lambda:'P')
    view=GraphicalTakeoffDialog(first,app_service=service,project_id='P')
    dock=ctrl.attach_view('2d',view,'P');dock.setFloating(True)
    qt.processEvents();assert ctrl.save()
    first.close()
    second=QMainWindow();second.show()
    restored=WorkspaceDockController(second,prefs,service,lambda:'P')
    try:
        assert restored.restore()
        new_view=GraphicalTakeoffDialog(second,app_service=service,project_id='P')
        reopened=restored.attach_view('2d',new_view,'P');qt.processEvents()
        assert reopened.isFloating(), 'saved viewer placement lost when dock is created after restoreState'
    finally:first.close();second.close();service.store.close();qt.processEvents()


def test_failed_project_switch_clears_previous_boq(tmp_path):
    from PySide6.QtWidgets import QTableWidgetItem
    qt=QApplication.instance() or QApplication([])
    service=StructuralProApp(tmp_path/'db')
    service.create_project('آزمایشی','P')
    current=['P']
    window=QMainWindow()
    ctrl=WorkspaceDockController(window,QSettings(str(tmp_path/'ui.ini'),QSettings.IniFormat),service,lambda:current[0])
    try:
        ctrl.boq_table.setRowCount(1)
        ctrl.boq_table.setItem(0,1,QTableWidgetItem('اطلاعات پروژه قبلی'))
        current[0]='missing'
        ctrl.refresh()
        assert ctrl.boq_table.rowCount()==0
        assert ctrl.tree.topLevelItemCount()==0
    finally:
        window.close();service.store.close();qt.processEvents()


def test_real_project_dock_show_hide_save_restore_without_boq_change(tmp_path):
    qt=QApplication.instance() or QApplication([])
    service=StructuralProApp(tmp_path/"project")
    service.create_project("نمونه","P")
    service.add_project_floor("P","اول",level="F1")
    service.add_project_member("P","M1","F1","wall")
    settings=QSettings(str(tmp_path/"ui.ini"),QSettings.Format.IniFormat)
    win=QMainWindow()
    ctrl=WorkspaceDockController(win,settings,service,lambda:"P")
    win.show()
    try:
        digest=service.store.current_digest("P")
        ctrl.refresh()
        assert ctrl.tree.topLevelItemCount()==1
        assert ctrl.tree.topLevelItem(0).childCount()==1
        ctrl.toggle()
        assert ctrl.dock.isVisible()
        assert ctrl.save()
        ctrl.dock.hide()
        assert ctrl.restore()
        assert ctrl.dock.isVisible()
        ctrl.reset()
        assert not ctrl.dock.isVisible()
        assert settings.value("e5/project/P/window-state") is None
        assert service.store.current_digest("P")==digest
    finally:
        win.close();service.store.close();qt.processEvents()


def test_layout_not_saved_for_missing_project(tmp_path):
    qt=QApplication.instance() or QApplication([])
    service=StructuralProApp(tmp_path/"project")
    win=QMainWindow();settings=QSettings(str(tmp_path/"ui.ini"),QSettings.Format.IniFormat)
    ctrl=WorkspaceDockController(win,settings,service,lambda:"NO_PROJECT")
    assert not ctrl.save()
    assert not ctrl.restore()
    assert not ctrl.dock.isVisible()
    win.close();service.store.close();qt.processEvents()

def test_two_independent_docks_save_and_restore_without_project_mutation(tmp_path):
    qt=QApplication.instance() or QApplication([])
    app=StructuralProApp(tmp_path/"db")
    app.create_project("پروژه","P")
    prefs=QSettings(str(tmp_path/"ui.ini"),QSettings.Format.IniFormat)
    window=QMainWindow();window.show()
    docks=WorkspaceDockController(window,prefs,app,lambda:"P")
    try:
        before=app.store.current_digest("P")
        docks.toggle();docks.toggle_boq()
        assert docks.dock.isVisible() and docks.boq_dock.isVisible()
        assert docks.boq_table.rowCount()==0
        assert docks.save()
        docks.dock.hide();docks.boq_dock.hide()
        assert docks.restore()
        assert docks.dock.isVisible() and docks.boq_dock.isVisible()
        docks.reset()
        assert not docks.dock.isVisible() and not docks.boq_dock.isVisible()
        assert before==app.store.current_digest("P")
    finally:window.close();app.store.close();qt.processEvents()
