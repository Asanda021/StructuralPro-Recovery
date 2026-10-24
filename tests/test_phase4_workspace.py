import pytest
from PySide6.QtWidgets import QApplication,QPushButton
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from core.platform.application import StructuralProApp
from test_phase4_structure import structure,activity,cmd

QT=QApplication.instance() or QApplication([])
def test_operational_wbs_schedule_and_gantt(tmp_path):
    from app import main
    import importlib.util
    assert importlib.util.find_spec('app.project_controls_workspace'),'project control UI absent'
    from app.project_controls_workspace import ProjectControlsWorkspace
    a=StructuralProApp(tmp_path);a.create_project('آزمایشی','P');structure(a);activity(a)
    w=ProjectControlsWorkspace(a,'P');w.show();QT.processEvents()
    try:
        w.fields['actor'].setText('planner');w.fields['reason'].setText('آزمون رابط')
        w.fields['calendar_start'].setText('۱۴۰۴/۱۰/۱۱');w.fields['weekdays'].setText('0,1,2,3,4,5,6');w.fields['holidays'].clear()
        QTest.mouseClick(w.findChild(QPushButton,'ScheduleCalendarSave'),Qt.LeftButton)
        assert 'schedule' in a.open_project('P')['project_control_config']
        w.select_activity('A');w.fields['duration'].setText('3')
        QTest.mouseClick(w.findChild(QPushButton,'ScheduleActivitySave'),Qt.LeftButton)
        assert a.project_schedule('P')['duration']==3
        w.fields['baseline_reference'].setText('BASE-UI');w.fields['baseline_approver'].setText('owner')
        QTest.mouseClick(w.findChild(QPushButton,'ScheduleBaselineSave'),Qt.LeftButton)
        assert len(a.open_project('P')['schedule_baselines'])==1
        assert 'A' in w.gantt.bars
        w.gantt.bars['A'].setSelected(True);QT.processEvents();assert w.selected_id=='A'
        old=w.gantt.scale_x;QTest.mouseClick(w.findChild(QPushButton,'GanttZoomWeek'),Qt.LeftButton);assert w.gantt.scale_x!=old
        w.fields['activity_title'].setText('عنوان اصلاح‌شده')
        QTest.mouseClick(w.findChild(QPushButton,'ActivitySave'),Qt.LeftButton)
        assert a.open_project('P')['project_schedule_tasks'][0]['title']=='عنوان اصلاح‌شده'
        w.fields['search'].setText('یافت نمی‌شود');QT.processEvents();assert w.activity_table.isRowHidden(0)
    finally:w.close();QT.processEvents();a.store.close()

def test_jalali_calendar_boundaries_and_invalid():
    import importlib.util
    assert importlib.util.find_spec('app.project_controls_workspace'),'UI absent'
    from app.project_controls_workspace import iso
    assert iso('۱۴۰۴/۱۲/۲۹')=='2026-03-20'
    assert iso('۱۴۰۵/۰۱/۰۱')=='2026-03-21'
    with pytest.raises(ValueError):iso('۱۴۰۴/۱۲/۳۰')

def test_progress_real_buttons_and_export(tmp_path,monkeypatch):
    import importlib.util
    assert importlib.util.find_spec('app.project_controls_workspace'),'UI absent'
    from app.project_controls_workspace import ProjectControlsWorkspace
    from PySide6.QtWidgets import QTableWidgetItem,QFileDialog
    from test_phase4_progress import project as fixture
    gen=fixture.__wrapped__(tmp_path);a,proof=next(gen)
    w=ProjectControlsWorkspace(a,'P');w.show();QT.processEvents()
    try:
        for k,v in {'actor':'planner','reason':'آزمون رابط','proof':proof['path'],'sha':proof['sha256'],'reference':'WEIGHTS-UI','decimal_places':'6'}.items():w.fields[k].setText(v)
        w.rounding.setCurrentIndex(w.rounding.findData('ROUND_HALF_EVEN'))
        for i in range(2):
            w.weight_table.setItem(i,1,QTableWidgetItem(str(i+1)));choice=w.weight_table.cellWidget(i,2);choice.setCurrentIndex(choice.findData('linear_workdays'))
        QTest.mouseClick(w.findChild(QPushButton,'WeightCreate'),Qt.LeftButton)
        for name,actor in [('WeightReview','reviewer'),('WeightApprove','approver')]:
            w.fields['actor'].setText(actor);QTest.mouseClick(w.findChild(QPushButton,name),Qt.LeftButton)
        assert a.open_project('P')['progress_weight_sets'][-1]['status']=='approved'
        for id,quantity in [('A','5'),('B','10')]:
            w.select_activity(id)
            for k,v in {'actor':'planner','report_date':'۱۴۰۴/۱۰/۱۶','reference':id+'-UI','executed':quantity}.items():w.fields[k].setText(v)
            QTest.mouseClick(w.findChild(QPushButton,'ProgressCreate'),Qt.LeftButton)
            for name,actor in [('ProgressReview','reviewer'),('ProgressApprove','approver')]:
                w.fields['actor'].setText(actor);QTest.mouseClick(w.findChild(QPushButton,name),Qt.LeftButton)
        assert len([d for d in a.open_project('P')['progress_documents'] if d['status']=='approved'])==2
        w.fields['reference'].setText('REPORT-UI');QTest.mouseClick(w.findChild(QPushButton,'ProgressReportSave'),Qt.LeftButton)
        assert a.open_project('P')['progress_reports'][-1]['actual']=='50.000000'
        QTest.mouseClick(w.findChild(QPushButton,'ProgressCalculate'),Qt.LeftButton);assert w.progress_table.rowCount()==2
        path=tmp_path/'report.xlsx';monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args,**kwargs:(str(path),''))
        w.report_format.setCurrentIndex(w.report_format.findData('xlsx'));w.report_kind.setCurrentIndex(w.report_kind.findData('progress'))
        QTest.mouseClick(w.findChild(QPushButton,'ProjectControlsExport'),Qt.LeftButton);assert path.exists(),w.status.text()
    finally:w.close();QT.processEvents();next(gen,None)

def test_reopened_weight_versions_discoverable_and_jalali_popup(tmp_path):
    from app.project_controls_workspace import ProjectControlsWorkspace
    from test_phase4_progress import project as fixture,weights
    from PySide6.QtWidgets import QComboBox,QCalendarWidget,QDialog
    from PySide6.QtCore import QTimer,QDate
    gen=fixture.__wrapped__(tmp_path);a,p=next(gen);d=weights(a,p)
    w=ProjectControlsWorkspace(a,'P');w.show();QT.processEvents()
    try:
        selector=w.findChild(QComboBox,'WeightVersions');assert selector is not None
        assert selector.findData(d['id'])>=0
        selector.setCurrentIndex(selector.findData(d['id']));assert w.fields['weight_id'].text()==d['id']
        assert w.weight_table.item(1,1).text()=='3'
        def choose():
            calendar=w.findChild(QCalendarWidget);assert calendar is not None
            calendar.setSelectedDate(QDate(2026,3,21));calendar.parentWidget().accept()
        QTimer.singleShot(20,choose)
        QTest.mouseDClick(w.fields['report_date'],Qt.LeftButton);assert w.fields['report_date'].text()=='۱۴۰۵/۰۱/۰۱'
    finally:w.close();QT.processEvents();next(gen,None)


def test_actual_main_menu_and_ribbon_subprocess(tmp_path):
    import subprocess,sys,os
    code="import os,sys\nfrom pathlib import Path\nroot=Path(sys.argv[1]);root.mkdir(exist_ok=True);Path.home=classmethod(lambda cls:root)\nfrom core.platform.application import StructuralProApp\nservice=StructuralProApp(root/'.structuralpro');service.create_project('آزمایشی','P');service.store.close()\nfrom PySide6 import QtWidgets\nfrom PySide6.QtCore import QTimer,Qt,QEvent,QCoreApplication\nfrom PySide6.QtTest import QTest\nfrom app.project_controls_workspace import ProjectControlsWorkspace\nseen=[];errors=[]\ndef launch(self):seen.append(self.pid);self.close();return 0\nProjectControlsWorkspace.exec=launch\nBase=QtWidgets.QApplication\nclass Harness(Base):\n def __init__(self,*args):\n  super().__init__(*args);QTimer.singleShot(50,self.exercise)\n def exercise(self):\n  try:\n   window=next(w for w in self.topLevelWidgets() if isinstance(w,QtWidgets.QMainWindow))\n   pages=window.findChild(QtWidgets.QStackedWidget);pages.setCurrentIndex(1)\n   project_page=pages.widget(1);project_page.findChildren(QtWidgets.QLineEdit)[0].setText('P')\n   button=window.findChild(QtWidgets.QPushButton,'ProjectControlsOpen');assert button\n   QTest.mouseClick(button,Qt.LeftButton);assert seen==['P']\n   # The project-context ribbon must invoke the same real dialog.\n   ribbon=next(b for b in window.findChildren(QtWidgets.QPushButton) if b.text()=='ساختار، زمان\u200cبندی و پیشرفت' and b is not button)\n   QTest.mouseClick(ribbon,Qt.LeftButton);assert seen==['P','P']\n   window.close();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)\n  except Exception as e:errors.append(repr(e))\n  finally:self.quit()\nQtWidgets.QApplication=Harness\nfrom app.main import main\nassert main()==0\nassert not errors,errors\nprint('REAL_MENU_RIBBON_PASS',seen)\n"
    r=subprocess.run([sys.executable,"-c",code,str(tmp_path)],env={**os.environ,"QT_QPA_PLATFORM":"offscreen"},capture_output=True,text=True,timeout=60)
    assert r.returncode==0,r.stdout[-1000:]+r.stderr[-2000:]
    assert "REAL_MENU_RIBBON_PASS" in r.stdout

def test_workspace_fits_desktop_with_usable_gantt_panel(tmp_path):
    from app.project_controls_workspace import ProjectControlsWorkspace
    a=StructuralProApp(tmp_path);a.create_project('آزمایشی','P');structure(a);activity(a)
    w=ProjectControlsWorkspace(a,'P');w.show();w.tabs.setCurrentIndex(1);QT.processEvents()
    try:
        assert w.height()<=1000,'forms force the dialog beyond a normal desktop height'
        assert w.gantt.viewport().width()>600
    finally:w.close();QT.processEvents();a.store.close()

def test_weight_distribution_is_persian_explicit_choice(tmp_path):
    from app.project_controls_workspace import ProjectControlsWorkspace
    from PySide6.QtWidgets import QComboBox
    a=StructuralProApp(tmp_path);a.create_project('آزمایشی','P');structure(a);activity(a)
    w=ProjectControlsWorkspace(a,'P')
    try:
        choice=w.weight_table.cellWidget(0,2);assert isinstance(choice,QComboBox)
        assert choice.currentData() is None
        assert choice.findText('خطی برحسب روز کاری')>=0
    finally:w.close();QT.processEvents();a.store.close()

def test_table_gantt_selection_and_curve_period_controls(tmp_path):
    from app.project_controls_workspace import ProjectControlsWorkspace
    from PySide6.QtWidgets import QComboBox
    a=StructuralProApp(tmp_path);a.create_project('آزمایشی','P');structure(a);activity(a)
    cmd(a,'schedule_calendar',start='2026-01-01',calendar={'weekdays':list(range(7)),'holidays':[]});cmd(a,'schedule_activity',id='A',duration=3,not_before=None,relationships=[])
    w=ProjectControlsWorkspace(a,'P');w.show();QT.processEvents()
    try:
        w.activity_table.setCurrentCell(0,0);QT.processEvents();assert w.gantt.bars['A'].isSelected()
        frequency=w.findChild(QComboBox,'CurveFrequency');assert frequency is not None
        assert {frequency.itemData(i) for i in range(frequency.count())}=={'daily','weekly','monthly'}
    finally:w.close();QT.processEvents();a.store.close()
