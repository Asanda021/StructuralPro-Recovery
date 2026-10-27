"""E5 real native Qt dock saved outside SQLite and project identity."""
from PySide6.QtWidgets import QApplication,QMainWindow
from PySide6.QtCore import Qt,QSettings
from core.platform.application import StructuralProApp
from app.workspace_docks import WorkspaceDockController


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
