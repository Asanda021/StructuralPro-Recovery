import json,time
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from core.projects.management import ProjectManagement

def test_large_cpm_and_responsive_gantt(tmp_path):
    from app.project_controls_workspace import GanttView
    qt=QApplication.instance() or QApplication([])
    n=1000;tasks=[{'id':f'T{i:04d}','duration':1} for i in range(n)]
    links=[{'pred':f'T{i-1:04d}','succ':f'T{i:04d}','type':'FS','lag':0} for i in range(1,n)]
    start=time.monotonic();result=ProjectManagement.calculate_cpm(tasks,links,start='2026-01-01',calendar={'weekdays':[0,1,2,3,4],'holidays':[]});elapsed=time.monotonic()-start
    assert result['duration']==n and len(result['critical_ids'])==n and elapsed<5
    view=GanttView();view.show();qt.processEvents();ticks=[];timer=QTimer();timer.timeout.connect(lambda:ticks.append(time.monotonic()));timer.start(10)
    try:
        QTest.qWait(30);before=time.monotonic();view.render(result);qt.processEvents();QTest.qWait(40)
        assert len(view.bars)==n;gap=max(b-a for a,b in zip(ticks,ticks[1:]));assert gap<.5
        receipt={'activities':n,'cpm_elapsed_s':elapsed,'ui_render_s':time.monotonic()-before,'max_event_gap_s':gap,'event_gap_limit_s':.5,'cpm_limit_s':5,'oracle_duration':n,'all_retained':True}
        (tmp_path/'project-controls-performance.json').write_text(json.dumps(receipt,indent=2))
    finally:timer.stop();view.close();qt.processEvents()
