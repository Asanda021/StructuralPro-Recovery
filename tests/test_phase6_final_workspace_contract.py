"""Existing panels and real preset navigation, never duplicate business forms."""
from PySide6.QtCore import Qt,QSettings
from PySide6.QtWidgets import QApplication,QMainWindow,QTabWidget,QWidget,QLineEdit,QStackedWidget
import pytest
from app.workspace_docks import WorkspaceDockController
from core.platform.application import StructuralProApp


def test_existing_report_and_revision_panels_keep_identity_across_docking_and_reset(tmp_path):
    qt=QApplication.instance() or QApplication([])
    service=StructuralProApp(tmp_path/'db');service.create_project('Explicit layout fixture','P')
    window=QMainWindow();tabs=QTabWidget();window.setCentralWidget(tabs);window.show()
    report=QLineEdit('existing report input');revision=QLineEdit('existing revision input')
    tabs.addTab(report,'گزارش');tabs.addTab(revision,'اصلاحیه')
    ctrl=WorkspaceDockController(window,QSettings(str(tmp_path/'ui.ini'),QSettings.IniFormat),service,lambda:'P')
    before=service.store.current_digest('P')
    try:
        assert hasattr(ctrl,'register_panel'), 'E5 original report/revision panels are not dockable'
        a=ctrl.register_panel('report',report,tabs,0,'گزارش',invalidate=report.clear)
        b=ctrl.register_panel('revision',revision,tabs,1,'اصلاحیه')
        assert tabs.count()==2 and tabs.widget(0) is not report and tabs.widget(1) is not revision
        a.show();b.show();a.setFloating(True);qt.processEvents()
        assert a.widget().widget() is report and b.widget().widget() is revision
        assert report.text()=='existing report input' and revision.text()=='existing revision input'
        assert ctrl.save() and ctrl.restore()
        ctrl.reset();qt.processEvents()
        assert not a.isFloating() and not a.isVisible() and not b.isVisible()
        tabs.setCurrentIndex(1);qt.processEvents();assert b.isVisible()
        assert service.store.current_digest('P')==before
        service.add_project_floor('P','Explicit new floor',level='F1')
        after=service.store.current_digest('P')
        ctrl.validate_views();qt.processEvents()
        assert not a.isVisible() and report.text()==''
        assert service.store.current_digest('P')==after
    finally:window.close();service.store.close();qt.processEvents()


def test_four_presets_navigate_original_pages_and_never_create_project_data(tmp_path):
    qt=QApplication.instance() or QApplication([])
    service=StructuralProApp(tmp_path/'db');service.create_project('Explicit presets fixture','P')
    window=QMainWindow();stack=QStackedWidget();window.setCentralWidget(stack);window.show()
    pages={mode:QWidget() for mode in ['manual','drawing','financial','report']}
    for p in pages.values():stack.addWidget(p)
    current=['P']
    ctrl=WorkspaceDockController(window,QSettings(str(tmp_path/'ui.ini'),QSettings.IniFormat),service,lambda:current[0])
    before=service.store.current_digest('P')
    try:
        assert hasattr(ctrl,'configure_presets'), 'E5 has no four real workspace presets'
        ctrl.configure_presets(lambda mode:stack.setCurrentWidget(pages[mode]))
        for mode in pages:
            ctrl.preset.setCurrentIndex(ctrl.preset.findData(mode));ctrl.preset_apply.click();qt.processEvents()
            assert stack.currentWidget() is pages[mode]
            assert ctrl.boq_dock.isVisible()==(mode=='financial')
        with pytest.raises(ValueError):ctrl.apply_preset('unknown')
        current[0]='missing';assert not ctrl.apply_preset('manual')
        assert service.store.current_digest('P')==before
    finally:window.close();service.store.close();qt.processEvents()
